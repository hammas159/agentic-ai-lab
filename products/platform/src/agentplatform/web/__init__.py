"""The operator console every product serves.

One page, no build step, no npm, no framework. It is the same four things for
all twenty products because they all expose the same Runtime: start work, watch
it, approve what it paused on, read the audit trail.

Deliberately one shared page rather than twenty frontends. Twenty
half-implemented dashboards is the mistake this portfolio already made once and
corrected by deleting them.
"""

from pathlib import Path

CONSOLE = Path(__file__).with_name("console.html")


def html(domain: str) -> str:
    """The console, with the product's domain baked in."""
    return CONSOLE.read_text(encoding="utf-8").replace("{{DOMAIN}}", domain)
