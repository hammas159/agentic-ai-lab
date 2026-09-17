"""Turn validated findings into prose.

One rule, enforced structurally rather than by prompt: **every number in the
output is substituted from a `Finding` that was computed and passed
validation.** There is no free text generation step, and no model, so there is
nothing that can invent a figure.

A model could write nicer sentences. It could also write "revenue grew
strongly" about a number it did not see, which is the failure this whole
project exists to avoid, so the templates stay.
"""

from __future__ import annotations

from .execute import Finding
from .profile import TableProfile


def _plural(n: int, singular: str, plural: str | None = None) -> str:
    return singular if n == 1 else (plural or singular + "s")


def describe_shape(profile: TableProfile) -> str:
    kinds: dict[str, int] = {}
    for column in profile.columns:
        kinds[column.kind] = kinds.get(column.kind, 0) + 1
    parts = ", ".join(f"{n} {kind}" for kind, n in sorted(kinds.items(), key=lambda kv: -kv[1]))
    return (
        f"{profile.rows:,} rows and {len(profile.columns)} columns ({parts}), "
        f"delimiter {profile.delimiter!r}, read as {profile.encoding}."
    )


def describe_integrity(profile: TableProfile) -> list[str]:
    out: list[str] = []
    if profile.duplicate_rows:
        share = profile.duplicate_rows / profile.rows if profile.rows else 0
        out.append(
            f"{profile.duplicate_rows:,} rows are exact duplicates of an earlier row "
            f"({share:.1%}). Any count, sum or mean over this file double-counts them "
            f"unless they are removed first."
        )
    if profile.ragged_rows:
        out.append(
            f"{profile.ragged_rows:,} rows have a different number of fields from the "
            f"header. Those rows are padded or truncated here, and whatever wrote this "
            f"file was not writing valid CSV."
        )
    return out


def describe_contamination(profile: TableProfile) -> list[str]:
    """The headline section: columns a numeric cast would quietly thin out."""
    out: list[str] = []
    for column in profile.contaminated:
        missing = column.present - column.parsed
        examples = ", ".join(repr(v) for v in column.unparsed_examples[:3])
        out.append(
            f"`{column.name}` is {column.parse_rate:.1%} numeric. The remaining "
            f"{missing:,} {_plural(missing, 'value')} ({examples}) will not parse. "
            f"Loading this column as a number drops those rows from every aggregate "
            f"computed over it, and nothing in the output will say so. They are kept "
            f"as text here."
        )
    return out


def describe_findings(findings: list[Finding]) -> list[str]:
    out: list[str] = []
    for finding in findings:
        line = f"{finding.title}: computed from {finding.supporting:,} rows"
        if finding.excluded:
            line += f", excluding {finding.excluded:,} ({finding.exclusion_reason})"
        out.append(line + ".")
        for caveat in finding.caveats:
            out.append(f"    Caveat: {caveat}")
    return out


def describe_warnings(profile: TableProfile) -> list[str]:
    return [f"`{name}`: {warning}" for name, warning in profile.all_warnings]


def narrate(profile: TableProfile, findings: list[Finding]) -> str:
    """The whole report, as text. Every figure traces to a validated finding."""
    lines: list[str] = []
    add = lines.append

    add(f"# {profile.path}")
    add("")
    add(describe_shape(profile))
    add("")

    integrity = describe_integrity(profile)
    if integrity:
        add("## Integrity")
        add("")
        for item in integrity:
            add(f"- {item}")
        add("")

    contamination = describe_contamination(profile)
    if contamination:
        add("## Columns a numeric cast would thin out")
        add("")
        for item in contamination:
            add(f"- {item}")
        add("")

    warnings = describe_warnings(profile)
    if warnings:
        add("## Column warnings")
        add("")
        for item in warnings:
            add(f"- {item}")
        add("")

    if findings:
        add("## Computed")
        add("")
        for item in describe_findings(findings):
            add(f"- {item}" if not item.startswith("    ") else item)
        add("")

    add("---")
    add(
        "Every figure above was computed by a query that ran and passed validation. "
        "No number here was written by a language model."
    )
    return "\n".join(lines)
