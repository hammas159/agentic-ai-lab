"""Collapsing an alert storm without collapsing the whole afternoon into it.

Correlation inside a window is transitive: A near B, B near C, C near D, and
suddenly four unrelated services are one critical incident. That happened for
real in ``incident-copilot`` with evenly spaced noise, so it is guarded here.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Alert:
    id: str
    service: str
    template: str
    at: int  # seconds

    @property
    def fingerprint(self) -> str:
        """Dedupe on the template, never on the rendered line.

        The same fault emits a different host, request id or latency every time,
        so text-identical deduplication catches almost nothing.
        """
        return f"{self.service}|{self.template}"


@dataclass
class Incident:
    alerts: list[Alert] = field(default_factory=list)

    @property
    def span(self) -> int:
        return self.alerts[-1].at - self.alerts[0].at

    @property
    def services(self) -> set[str]:
        return {a.service for a in self.alerts}

    @property
    def started(self) -> int:
        return self.alerts[0].at


def collapse(
    alerts: list[Alert],
    window: int = 120,
    max_span: int = 900,
    same_service_only: bool = True,
) -> list[Incident]:
    """Group alerts into incidents.

    ``window`` is the gap between adjacent alerts; ``max_span`` caps the whole
    group, which is what stops a steady drip chaining forever. Crossing service
    boundaries is opt-in, not the default.
    """
    if window < 1 or max_span < window:
        raise ValueError("need window >= 1 and max_span >= window")
    out: list[Incident] = []
    for alert in sorted(alerts, key=lambda a: (a.at, a.id)):
        for incident in reversed(out):
            if alert.at - incident.alerts[-1].at > window:
                continue
            if alert.at - incident.started > max_span:
                continue
            if same_service_only and alert.service not in incident.services:
                continue
            incident.alerts.append(alert)
            break
        else:
            out.append(Incident([alert]))
    return out


def dedupe(alerts: list[Alert], repeat_after: int = 300) -> list[Alert]:
    """Drop a re-fire of the same fingerprint inside ``repeat_after`` seconds."""
    last: dict[str, int] = {}
    kept: list[Alert] = []
    for alert in sorted(alerts, key=lambda a: (a.at, a.id)):
        seen = last.get(alert.fingerprint)
        if seen is not None and alert.at - seen < repeat_after:
            continue
        last[alert.fingerprint] = alert.at
        kept.append(alert)
    return kept


def reduction(alerts: list[Alert], incidents: list[Incident]) -> float:
    """Alert-volume reduction. The number this product is bought on."""
    if not alerts:
        return 0.0
    return 1 - (len(incidents) / len(alerts))
