"""API for the Vue UI, served by the standard library.

    python ui/server.py      # then, in ui/: npm install && npm run dev

Read-only: it scans and reports. Applying edits is a CLI action, deliberately,
because writing to a working tree from a browser request is not a thing this
should offer.
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pilot.cli import _python_files  # noqa: E402
from pilot.rules import MECHANICAL, RULE_KIND, scan_source  # noqa: E402

MAX_FILES = 4000


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

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/api/scan":
            self._json({"error": "not found"}, 404)
            return

        params = parse_qs(parsed.query)
        target = Path((params.get("path") or ["."])[0]).resolve()
        if not target.exists():
            self._json({"error": f"no such path: {target}"}, 400)
            return

        counts: Counter = Counter()
        files = []
        scanned = 0
        errors = 0

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            for path in _python_files(target)[:MAX_FILES]:
                scanned += 1
                try:
                    source = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                scan = scan_source(str(path), source)
                if scan.parse_error:
                    errors += 1
                    continue
                if not scan.edits:
                    continue
                try:
                    shown = str(path.relative_to(target))
                except ValueError:
                    shown = str(path)
                files.append(
                    {
                        "path": shown,
                        "edits": [
                            {
                                "line": e.line,
                                "rule": e.rule,
                                "mechanical": e.mechanical,
                                "before": e.before,
                                "replacement": e.replacement,
                                "note": e.note,
                            }
                            for e in scan.edits
                        ],
                    }
                )
                for edit in scan.edits:
                    counts[edit.rule] += 1

        mechanical = sum(v for k, v in counts.items() if RULE_KIND[k] == MECHANICAL)
        self._json(
            {
                "files_scanned": scanned,
                "parse_errors": errors,
                "mechanical": mechanical,
                "behavioural": sum(counts.values()) - mechanical,
                "by_rule": dict(counts),
                "files": files[:200],
            }
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="migration-pilot API for the Vue UI")
    parser.add_argument("--port", type=int, default=8105)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"migration-pilot API on http://127.0.0.1:{args.port}")
    print("now run:  cd ui && npm install && npm run dev")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
