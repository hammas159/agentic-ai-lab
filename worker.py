"""The worker: consumes `jobs.requested`, runs the measurement, streams the result back.

One process, one GPU, one job at a time. That is not a limitation to work around - it is
the actual constraint, and making it explicit is better than letting ten web processes
each start a run and discover the constraint by thrashing VRAM.

    python worker.py              # all apps
    python worker.py --apps localizer kill-rate

What it does per message:

1. mark the job running in Redis, so the page shows it moved off the queue
2. call the app's own `runner`, which streams progress through `emit`
3. publish each tick to Redis pub/sub (the browser's SSE feed) and to `jobs.progress`
4. write the result to Redis and publish a final record to `jobs.completed`

Step 4 is the one that matters after a crash. Redis keys expire; `jobs.completed` does not,
so an hour of GPU time survives a restart, a flushed cache or a schema change.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import signal
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from apps._platform import bus, cache  # noqa: E402

APPS_DIR = ROOT / "apps"


def load_runners() -> dict[str, object]:
    """Import every apps/NN_name/app.py and index its runner by theme slug.

    The directories are digit-prefixed so they sort in the order the README lists them,
    which is not an importable module name - hence loading by file path.
    """
    runners: dict[str, object] = {}
    for path in sorted(APPS_DIR.glob("[0-9][0-9]_*/app.py")):
        name = f"aal_{path.parent.name}"
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            print(f"  !! {path.parent.name} failed to import: {exc}")
            continue
        slug = getattr(module, "SLUG", None) or module.app.title.lower().replace(" ", "-")
        runners[slug] = module.runner
        print(f"  loaded {path.parent.name:22} -> {slug}")
    return runners


async def handle(job_id: str, app: str, params: dict, runner) -> None:
    async def emit(done: int, total: int, note: str = "") -> None:
        await cache.update_job(job_id, progress=done, total=total)
        await cache.publish_progress(
            job_id, {"done": done, "total": total, "note": note, "status": "running"}
        )
        await bus.emit_progress(job_id, app, done, total, note)

    await cache.update_job(job_id, status="running")
    try:
        result = await runner(params, emit)
        await cache.update_job(job_id, status="done", result=result)
        await cache.publish_progress(job_id, {"status": "done"})
        # The durable record. Everything above this line is recoverable from it.
        await bus.emit_completed(job_id, app, result)
        print(f"  done {job_id} ({app})")
    except Exception as exc:
        traceback.print_exc()
        await cache.update_job(job_id, status="error", error=str(exc)[:400])
        await cache.publish_progress(job_id, {"status": "error", "note": str(exc)[:200]})
        print(f"  FAILED {job_id} ({app}): {exc}")


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apps", nargs="*", help="only consume jobs for these slugs")
    ap.add_argument("--group", default="workers")
    args = ap.parse_args()

    print("loading apps...")
    runners = load_runners()
    if args.apps:
        runners = {k: v for k, v in runners.items() if k in set(args.apps)}
    if not runners:
        print("no runners loaded")
        return 1
    print(f"serving {len(runners)} apps: {', '.join(sorted(runners))}\n")

    if not await bus.available():
        print("Kafka is not reachable. Start it with:")
        print("  docker compose up -d")
        return 1

    consumer = bus.consumer(bus.TOPIC_REQUESTED, group=args.group, from_beginning=False)
    await consumer.start()
    print(f"consuming {bus.TOPIC_REQUESTED} as group {args.group!r}. ctrl-c to stop.\n")

    stopping = asyncio.Event()

    def _stop(*_):
        stopping.set()

    with contextlib_suppress():
        signal.signal(signal.SIGINT, _stop)
        signal.signal(signal.SIGTERM, _stop)

    try:
        while not stopping.is_set():
            batch = await consumer.getmany(timeout_ms=1000, max_records=1)
            for records in batch.values():
                for rec in records:
                    ev = rec.value
                    app = ev.get("app", "")
                    runner = runners.get(app)
                    if runner is None:
                        continue  # another worker owns this app
                    print(f"  picked {ev['job_id']} ({app})")
                    await handle(ev["job_id"], app, ev.get("params", {}), runner)
    finally:
        await consumer.stop()
        await bus.close()
    return 0


class contextlib_suppress:
    """signal.signal raises on some Windows shells; not worth failing the worker for."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return True


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
