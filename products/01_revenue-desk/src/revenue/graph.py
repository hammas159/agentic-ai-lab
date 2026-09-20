"""The outreach graph: rules, fan-out, synthesis, a capped revision loop, a gate, an approval.

Every shape in ``agentplatform.graphs`` appears here once, which makes this the
worked example the other nineteen products copy.
"""

from __future__ import annotations

from agentplatform import graphs
from agentplatform.graphs import END, Graph, Node
from agentplatform.llm import Model

from . import agents


def synthesise(model: Model):
    def _run(state: dict) -> dict:
        # The branch status list is in the state, so a dead source cannot be
        # narrated as a complete picture. See agentplatform.graphs.
        failed = state.get("branches_failed", [])
        prompt = f"summarise:{sorted(state.get('issued_receipts', ()))}|failed:{sorted(failed)}"
        completion = model.generate(prompt)
        return {"summary": completion.text, "model": completion.model}

    return _run


def draft(model: Model):
    def _once(state: dict) -> dict:
        completion = model.generate(f"draft:{state.get('summary', '')}")
        return {"draft.body": completion.text, "model": completion.model}

    # Capped at two, with an external done predicate — never the model's own
    # verdict, which quit on the first draft every time it was measured.
    return graphs.loop(_once, max_iterations=2, done=lambda s: len(s.get("draft.body", "")) > 0)


def build(model: Model, sources: dict) -> Graph:
    """``sources`` maps a branch name to a callable, so a test can fail one."""
    return Graph(
        nodes={
            "classify": Node("classify", graphs.RULES, agents.classify_reply),
            "qualify": Node("qualify", graphs.RULES, agents.qualify),
            "enrich": Node("enrich", graphs.FANOUT, branches=sources),
            "synthesise": Node("synthesise", graphs.LLM, synthesise(model)),
            "draft": Node("draft", graphs.LLM, draft(model)),
            "gate": Node("gate", graphs.GATE, agents.run_gate),
            "approve": Node("approve", graphs.INTERRUPT),
            "send": Node("send", graphs.TOOL, lambda s: {"sent": True}),
            "suppress": Node("suppress", graphs.TOOL, lambda s: {"suppressed": True}),
        },
        entry="classify",
        # An opt-out leaves the graph before anything is drafted, let alone sent.
        edges={
            "classify": lambda s: "suppress" if s.get("contact.opted_out") else "qualify",
            "suppress": END,
            "qualify": "enrich",
            "enrich": "synthesise",
            "synthesise": "draft",
            "draft": "gate",
            "gate": "approve",
            "approve": "send",
            "send": END,
        },
    )
