"""The runnable product: a graph, a bus, a store and an HTTP surface.

``python -m revenue.app`` serves it. Nothing here is imported by the tests,
which build a Runtime directly against the in-memory ports.
"""

from __future__ import annotations

from agentplatform import api, models
from agentplatform.llm import Model, Ollama
from agentplatform.ports import InMemoryBus, InMemoryStore

from .graph import build

DOMAIN = "crm"


def default_sources() -> dict:
    """Stubs. A deployment swaps these for SearXNG, a registry client and a crawler."""
    return {
        "web_search": lambda s: ["src_a41", "src_c07"],
        "registry": lambda s: ["src_b22"],
    }


def runtime(model: Model, sources: dict | None = None) -> api.Runtime:
    return api.Runtime(
        domain=DOMAIN,
        bus=InMemoryBus(),
        store=InMemoryStore(),
        graph=build(model, sources or default_sources()),
    )


def main() -> None:  # pragma: no cover - the serving path, not the tested one
    import subprocess

    import uvicorn

    listed = subprocess.run(
        ["ollama", "list"], capture_output=True, text=True, check=False
    ).stdout
    installed = [line.split()[0] for line in listed.splitlines()[1:] if line.strip()]
    chosen = models.resolve(models.GENERAL, installed)
    print(f"revenue-desk using {chosen.note}")

    rt = runtime(Ollama(chosen.tag))
    uvicorn.run(api.create_app(rt), host="127.0.0.1", port=8000)


if __name__ == "__main__":  # pragma: no cover
    main()
