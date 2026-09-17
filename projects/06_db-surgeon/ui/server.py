"""API the SolidJS UI calls, served by the standard library.

    python ui/server.py            # then, in ui/: npm install && npm run dev

Vite proxies /api here, so the browser and `db-surgeon check` run the same
code. Bound to localhost only: it executes SQL that arrives in a request body,
which is the entire point of a shadow database and an appalling idea to expose.
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dbsurgeon.plan import build  # noqa: E402

MAX_BODY = 1_000_000  # a migration is text; a megabyte is already generous


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:
        pass

    def _json(self, payload, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        if self.path.rstrip("/") != "/api/check":
            self._json({"error": "not found"}, 404)
            return

        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            self._json({"error": "request too large"}, 413)
            return
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError as exc:
            self._json({"error": f"bad JSON: {exc}"}, 400)
            return

        plan = build(
            name=payload.get("name") or "migration",
            schema=payload.get("schema", ""),
            seed=payload.get("seed", ""),
            up=payload.get("up", ""),
            down=payload.get("down", ""),
        )
        trip = plan.trip
        self._json(
            {
                "verdict": plan.verdict,
                "safe": plan.safe,
                "error": plan.error,
                "schema_equivalent": trip.schema_equivalent if trip else None,
                "schema_restored": trip.schema_restored if trip else None,
                "data_restored": trip.data_restored if trip else None,
                "columns_reordered": trip.columns_reordered if trip else [],
                "columns_lost": trip.columns_lost if trip else [],
                "rows_lost": trip.rows_lost if trip else 0,
                "up": [
                    {
                        "kind": o.kind,
                        "category": o.category,
                        "target": o.target,
                        "reason": o.reason,
                    }
                    for o in plan.up_operations
                ],
                "disagreements": plan.disagreements,
            }
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="db-surgeon API for the SolidJS UI")
    parser.add_argument("--port", type=int, default=8095)
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"db-surgeon API on http://127.0.0.1:{args.port}  (localhost only)")
    print("now run:  cd ui && npm install && npm run dev")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
