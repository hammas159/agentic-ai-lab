"""The runnable product. ``python -m onedesk.app`` serves it."""

from __future__ import annotations

from agentplatform import api, models
from agentplatform.llm import Model, Ollama
from agentplatform.ports import InMemoryBus, InMemoryStore

from .graph import build

DOMAIN = "social"


def runtime(model: Model, sources: dict | None = None) -> api.Runtime:
    """In-memory by default. Swap the ports for the adapters to deploy."""
    return api.Runtime(
        domain=DOMAIN,
        bus=InMemoryBus(),
        store=InMemoryStore(),
        graph=build(model, sources),
    )


def main() -> None:  # pragma: no cover - the serving path, not the tested one
    import subprocess

    import uvicorn

    listed = subprocess.run(
        ["ollama", "list"], capture_output=True, text=True, check=False
    ).stdout
    installed = [line.split()[0] for line in listed.splitlines()[1:] if line.strip()]
    chosen = models.resolve(models.GENERAL, installed)
    print(f"one-desk using {chosen.note}")

    uvicorn.run(api.create_app(runtime(Ollama(chosen.tag))), host="127.0.0.1", port=8000)


if __name__ == "__main__":  # pragma: no cover
    main()
