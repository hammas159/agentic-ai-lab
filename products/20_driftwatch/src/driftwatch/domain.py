"""Which documentation claims can be checked by running something.

Most doc linters assume every claim is checkable and produce a wall of
unfalsifiable findings, which is how they get turned off in week two.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MECHANICAL = "mechanical"
JUDGEMENT = "judgement"

_PYTHON_VERSION = re.compile(r"python\s*(?:>=|≥)\s*(\d+\.\d+)", re.I)
_TEST_COUNT = re.compile(r"(\d[\d,]*)\s+tests\b", re.I)
_ZERO_DEPS = re.compile(r"\bzero\s+(?:runtime\s+)?dependencies\b", re.I)

_CHECKS = (
    ("python_version", _PYTHON_VERSION),
    ("test_count", _TEST_COUNT),
    ("zero_dependencies", _ZERO_DEPS),
)


@dataclass(frozen=True)
class Claim:
    text: str
    file: str = "README.md"
    line: int = 0

    @property
    def kind(self) -> str:
        return MECHANICAL if self.check is not None else JUDGEMENT

    @property
    def check(self) -> str | None:
        for name, pattern in _CHECKS:
            if pattern.search(self.text):
                return name
        return None


@dataclass(frozen=True)
class Verdict:
    claim: Claim
    checked: bool
    holds: bool | None
    detail: str


NOT_CHECKABLE = "unfalsifiable by running anything; a person decides"


def verify(claim: Claim, facts: dict) -> Verdict:
    """Check a claim against facts collected from the repository.

    ``facts`` comes from running things — ``pyproject.toml``, a collected test
    count, the declared dependency list. Nothing here reasons about the claim.
    """
    check = claim.check
    if check is None:
        return Verdict(claim, False, None, NOT_CHECKABLE)

    if check == "python_version":
        stated = _PYTHON_VERSION.search(claim.text).group(1)
        actual = str(facts.get("requires_python", "")).lstrip(">=≥ ")
        return Verdict(
            claim,
            True,
            stated == actual,
            f"README says {stated}, project says {actual or 'nothing'}",
        )

    if check == "test_count":
        stated = int(_TEST_COUNT.search(claim.text).group(1).replace(",", ""))
        actual = facts.get("collected_tests")
        if actual is None:
            return Verdict(claim, False, None, "no collected test count available")
        return Verdict(
            claim,
            True,
            stated == actual,
            f"README says {stated}, pytest collected {actual}",
        )

    stated_zero = True
    actual = list(facts.get("dependencies", []))
    return Verdict(
        claim,
        True,
        stated_zero and not actual,
        f"README claims zero dependencies, project declares {actual or 'none'}",
    )


def verifiable_share(claims: list[Claim]) -> float:
    """Share of claims a machine can settle. The product's headline ratio."""
    if not claims:
        return 0.0
    return sum(1 for c in claims if c.kind == MECHANICAL) / len(claims)


def broken(verdicts: list[Verdict]) -> list[Verdict]:
    """Claims that were checked and do not hold. The pull request's contents."""
    return [v for v in verdicts if v.checked and v.holds is False]
