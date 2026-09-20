"""Which model a product actually gets, and recording which one it was.

Products ask for a capability, never a tag. The resolver hands back the best
installed model for that capability, so nothing is blocked while a larger one is
still downloading, and the tag it chose is recorded on every result — which is
what turns a later run on a bigger model into a comparison row rather than an
overwrite.

The fuller fleet registry lives in ``langchain-lab/shared/models.py``. This is
the resolution policy, which is the part products need.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")

GENERAL = "general"
TOOLS = "tools"
CODER = "coder"
EMBEDDING = "embedding"

# Best first. A role resolves to the first tag that is actually installed.
PREFERENCE: dict[str, tuple[str, ...]] = {
    GENERAL: (
        "qwen2.5:14b-instruct",
        "qwen2.5:7b-instruct",
        "qwen2.5:3b-instruct",
        "llama3.2:3b",
    ),
    TOOLS: (
        "qwen2.5:14b-instruct",
        "qwen2.5:7b-instruct",
        "llama3.2:3b",
        "qwen2.5:3b-instruct",
    ),
    CODER: ("qwen2.5-coder:14b", "qwen2.5-coder:3b"),
    EMBEDDING: ("nomic-embed-text:latest", "nomic-embed-text"),
}


class NoModelForRoleError(LookupError):
    """Nothing installed can fill this role. A configuration error, not a crash."""


@dataclass(frozen=True)
class Resolved:
    role: str
    tag: str
    preferred: str

    @property
    def is_preferred(self) -> bool:
        return self.tag == self.preferred

    @property
    def note(self) -> str:
        if self.is_preferred:
            return f"{self.tag} (preferred for {self.role})"
        return (
            f"{self.tag} standing in for {self.preferred}, which is not installed; "
            "re-run to add a comparison row once it is"
        )


def resolve(role: str, installed: list[str]) -> Resolved:
    """The best installed model for a role.

    Deliberately never raises because a preferred model is missing — only when
    nothing at all fits. A product that cannot start until an 8.6 GB download
    finishes is a product that does not get built.
    """
    if role not in PREFERENCE:
        raise NoModelForRoleError(f"{role!r} is not a role; known roles: {sorted(PREFERENCE)}")
    ladder = PREFERENCE[role]
    have = set(installed)
    for tag in ladder:
        if tag in have:
            return Resolved(role, tag, ladder[0])
    raise NoModelForRoleError(
        f"no model installed for {role!r}; any of {list(ladder)} would do"
    )


def comparison_pending(role: str, installed: list[str]) -> str | None:
    """The tag whose arrival would be worth a re-run, or None."""
    try:
        chosen = resolve(role, installed)
    except NoModelForRoleError:
        return PREFERENCE.get(role, (None,))[0]
    return None if chosen.is_preferred else chosen.preferred
