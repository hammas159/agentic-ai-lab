"""ledger-brain agents: document intake, reconciliation, collections.

Three quarters of this file does not call a model. The triage step, the early
exit and the commit are rules; the model writes the summary and the draft, and
:mod:`agentplatform.gate` removes anything it wrote that no tool supports.
"""

from __future__ import annotations

from agentplatform.authority import Level, Table

from .domain import Invoice, Payment, match
from .invoices import as_invoices, collisions, receivables


def authority() -> Table:
    """Who may write what. Default-deny — see agentplatform.authority."""
    return (
        Table()
        .grant("doc-intake", "document.*", Level.WRITE)
        .grant("reconciler", "match.*", Level.WRITE)
        .grant("match-explainer", "match.rationale", Level.WRITE)
        .grant("match-explainer", "match.decision", Level.NEVER)
        .grant("collections-writer", "chase.draft", Level.WRITE)
    )


def _book(state: dict) -> tuple[list, list]:
    """Payments and open invoices.

    Supplied directly by the unit tests. Otherwise drawn from the real ledger:
    a slice of open receivables, with a payment arriving for each.
    """
    if state.get("invoices") is not None:
        return (
            [Payment(p["id"], p["amount"]) for p in state.get("payments", [])],
            [Invoice(i["id"], i["amount"]) for i in state["invoices"]],
        )
    rows = receivables()[: state.get("limit", 200)]
    invoices = as_invoices(rows)
    payments = [Payment(f"pay_{r.invoice}", r.amount) for r in rows]
    return payments, invoices


def triage(state: dict) -> dict:
    """The deterministic matcher runs first; the model only sees the residue."""
    payments, invoices = _book(state)
    result = match(payments, invoices)
    return {
        "matched": result.matched,
        "ambiguous": result.ambiguous,
        "unmatched": result.unmatched,
        "summary_subject": sorted(result.ambiguous),
    }


def early_exit(state: dict) -> bool:
    """Equal amounts are refused, not guessed. That is the whole product."""
    return bool(state.get("ambiguous"))


def on_exit(state: dict) -> dict:
    return {"refused": True, "needs_a_person": sorted(state.get("ambiguous", {}))}


def commit(state: dict) -> dict:
    return {"chase.draft": state.get("draft", ""), "sent": False}


def _matched(state: dict) -> list[str]:
    """Invoice ids the deterministic matcher settled. Real receipts."""
    return sorted(state.get("matched", {}).values())


def _collisions(state: dict) -> list[str]:
    """What the amount alone cannot identify, as a receipt the narrator cites."""
    c = collisions(receivables())
    return [
        f"collision_rate={c.collision_rate:.4f}",
        f"guess_accuracy={c.guess_accuracy:.4f}",
        f"largest_group={c.largest_group}",
    ]


def default_sources() -> dict:
    """Both branches read the committed invoice ledger."""
    return {"matched": _matched, "collisions": _collisions}
