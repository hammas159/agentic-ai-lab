"""The watchtower pipeline, built from the shared blueprint.

Seven nodes, the same seven every product has. What differs is the judgement in
:mod:`watchtower.agents`, not the shape.
"""

from __future__ import annotations

from agentplatform import blueprint, gate
from agentplatform.graphs import Graph
from agentplatform.llm import Model

from . import agents


def summarise(model: Model):
    def _run(state: dict) -> dict:
        # branches_failed is in the state, so a dead source cannot be narrated
        # as a complete picture.
        failed = sorted(state.get("branches_failed", []))
        prompt = f"summarise:{state.get('summary_subject')}|failed:{failed}"
        completion = model.generate(prompt)
        return {"summary": completion.text, "model": completion.model}

    return _run


def compose(model: Model):
    def _run(state: dict) -> dict:
        completion = model.generate(f"compose:{state.get('summary', '')}")
        return {"draft": completion.text, "model": completion.model}

    return _run


def build(model: Model, sources: dict | None = None) -> Graph:
    return blueprint.review_pipeline(
        triage=agents.triage,
        gather=sources or agents.default_sources(),
        synthesise=summarise(model),
        compose=compose(model),
        gate=gate.from_state,
        commit=agents.commit,
        early_exit=agents.early_exit,
        on_exit=agents.on_exit,
    )
