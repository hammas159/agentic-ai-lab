"""watchtower agents: inventory, CVE matching, exploitability, remediation.

Three quarters of this file does not call a model. The triage step, the early
exit and the commit are rules; the model writes the summary and the draft, and
:mod:`agentplatform.gate` removes anything it wrote that no tool supports.
"""

from __future__ import annotations

from agentplatform.authority import Level, Table

from .domain import Advisory, OutOfScopeError, Package, assess, in_scope
from .osv import installed as _installed
from .osv import load as _osv


def authority() -> Table:
    """Who may write what. Default-deny — see agentplatform.authority."""
    return (
        Table()
        .grant("inventory", "asset.*", Level.WRITE)
        .grant("cve-matcher", "finding.*", Level.WRITE)
        .grant("exploitability-triager", "finding.priority", Level.WRITE)
        .grant("remediation-writer", "remediation.draft", Level.WRITE)
        .grant("remediation-writer", "remediation.applied", Level.NEVER)
    )


def triage(state: dict) -> dict:
    """Scope first, then version comparison with the backport table consulted."""
    try:
        in_scope(state.get("host", ""), set(state.get("scope", [])))
    except OutOfScopeError as refused:
        return {"out_of_scope": True, "refusal": str(refused), "summary_subject": []}

    if state.get("packages") is not None:
        vulnerable = []
        for row in state["packages"]:
            package = Package(row["name"], row["version"], row.get("release", ""))
            for adv in state.get("advisories", []):
                advisory = Advisory(
                    adv["cve"], adv["package"], adv["fixed_upstream"], adv.get("backported")
                )
                if assess(package, advisory).vulnerable:
                    vulnerable.append(advisory.cve)
    else:
        # The real scan: this environment against OSV's published advisories,
        # using interval logic rather than "below the highest fixed version".
        database = _osv()
        vulnerable = [
            adv.id
            for name, version in _installed().items()
            for adv in database.get(name, [])
            if adv.affects(version)
        ]
    return {
        "out_of_scope": False,
        "vulnerable": sorted(set(vulnerable)),
        "summary_subject": sorted(set(vulnerable)),
    }


def early_exit(state: dict) -> bool:
    """An unauthorised target is refused, not warned about."""
    return bool(state.get("out_of_scope"))


def on_exit(state: dict) -> dict:
    return {"refused": True, "reason": state.get("refusal", "")}


def commit(state: dict) -> dict:
    return {"remediation.draft": state.get("draft", ""), "applied": False}


def _advisories(state: dict) -> list[str]:
    """Advisory ids behind the findings. Real OSV records, as receipts."""
    return sorted(set(state.get("vulnerable", [])))


def _inventory(state: dict) -> list[str]:
    """The packages actually installed, as collected facts."""
    return sorted(f"{name}=={version}" for name, version in _installed().items())


def default_sources() -> dict:
    """Both branches read this machine and the committed OSV export."""
    return {"advisories": _advisories, "inventory": _inventory}
