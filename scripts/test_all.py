"""Run every sub-project's test suite and report the total.

    python scripts/test_all.py            # everything
    python scripts/test_all.py projects   # just projects/

This repository is a monorepo of independent packages: each of `projects/*` and
`products/*` has its own `pyproject.toml` with its own `pythonpath = ["src"]`,
and each is meant to be runnable on its own. That is a deliberate shape - the
projects claim zero runtime dependencies and are checked that way - but it has
one sharp edge: running `pytest` at the repository root does NOT run them. It
tries to collect them, cannot import their `src` packages, and stops with
dozens of collection errors that look like a broken repository rather than a
layout doing what it was designed to do.

So the root `pyproject.toml` now tells pytest not to descend into them, and
this script is how you run them all. Each suite runs in its own process, from
its own directory, exactly as it would if that package were cloned alone.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TREES = ("projects", "products")


def suites(trees: tuple[str, ...]) -> list[Path]:
    found = []
    for tree in trees:
        base = ROOT / tree
        if not base.is_dir():
            continue
        for entry in sorted(base.iterdir()):
            if entry.is_dir() and (entry / "tests").is_dir():
                found.append(entry)
    return found


def run(package: Path) -> tuple[str, int, str]:
    """Return (outcome, test_count, detail) for one package."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=package, capture_output=True, text=True, errors="replace",
        timeout=900, check=False,
    )
    blob = proc.stdout + proc.stderr
    passed = failed = errors = 0
    for line in blob.splitlines():
        # pytest's summary line, e.g. "32 passed in 1.56s" or "1 failed, 4 passed"
        if " passed" in line or " failed" in line or " error" in line:
            for token, target in (("passed", "p"), ("failed", "f"), ("error", "e")):
                if token in line:
                    for part in line.replace(",", " ").split():
                        if part.isdigit():
                            nxt = line.split(part, 1)[1].lstrip().split()[:1]
                            if nxt and nxt[0].startswith(token):
                                value = int(part)
                                if target == "p":
                                    passed = max(passed, value)
                                elif target == "f":
                                    failed = max(failed, value)
                                else:
                                    errors = max(errors, value)
    if proc.returncode == 0:
        return "ok", passed, ""
    detail = next(
        (ln.strip() for ln in blob.splitlines()
         if "ModuleNotFoundError" in ln or "ImportError" in ln or "Error" in ln),
        f"exit {proc.returncode}",
    )
    return "FAIL", passed, f"{failed} failed, {errors} errors | {detail[:70]}"


def main() -> int:
    trees = tuple(sys.argv[1:]) or TREES
    packages = suites(trees)
    if not packages:
        raise SystemExit(f"no packages with tests/ under {trees}")

    print(f"{len(packages)} packages with test suites\n")
    started = time.time()
    total = 0
    broken: list[tuple[str, str]] = []

    for package in packages:
        outcome, count, detail = run(package)
        total += count
        label = f"{package.parent.name}/{package.name}"
        print(f"  {label:<34}{count:>5} tests   {outcome}"
              + (f"   {detail}" if detail else ""), flush=True)
        if outcome != "ok":
            broken.append((label, detail))

    print()
    print(f"{total:,} tests across {len(packages)} packages in {time.time() - started:.0f}s")
    if broken:
        print(f"\n{len(broken)} package(s) not green:")
        for label, detail in broken:
            print(f"  {label}: {detail}")
        return 1
    print("all green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
