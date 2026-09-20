"""What a route costs, so any proposal can be scored on the same matrix.

Whether a model or a solver produced the route is irrelevant here, which is the
point: they become comparable.
"""

from __future__ import annotations

from dataclasses import dataclass

Matrix = dict


class MissingLegError(KeyError):
    """No distance for a pair. Never silently zero, never a straight line."""


class InvalidRouteError(ValueError):
    """A route that skips, repeats or fails to return would win every contest."""


def validate(route: list[str], stops: set[str], depot: str) -> None:
    if len(route) < 2 or route[0] != depot or route[-1] != depot:
        raise InvalidRouteError("a route starts and ends at the depot")
    body = route[1:-1]
    if len(body) != len(set(body)):
        raise InvalidRouteError("a route visits each stop once")
    if set(body) != stops:
        missing = sorted(stops - set(body))
        extra = sorted(set(body) - stops)
        raise InvalidRouteError(f"missing {missing}, unexpected {extra}")


def leg(matrix: Matrix, a: str, b: str) -> int:
    try:
        return matrix[(a, b)]
    except KeyError as exc:
        raise MissingLegError(f"no distance from {a} to {b}") from exc


def cost(route: list[str], matrix: Matrix, stops: set[str], depot: str) -> int:
    """Total distance of a validated route."""
    validate(route, stops, depot)
    return sum(leg(matrix, a, b) for a, b in zip(route, route[1:], strict=False))


@dataclass(frozen=True)
class Comparison:
    solver: int
    challenger: int

    @property
    def delta(self) -> int:
        return self.challenger - self.solver

    @property
    def pct_worse(self) -> float:
        if self.solver <= 0:
            raise ValueError("a solver route of zero cost cannot be compared against")
        return self.delta / self.solver

    @property
    def challenger_won(self) -> bool:
        return self.challenger < self.solver


def compare(
    solver_route: list[str],
    challenger_route: list[str],
    matrix: Matrix,
    stops: set[str],
    depot: str,
) -> Comparison:
    """Score two routes on one matrix. The product's headline measurement."""
    return Comparison(
        solver=cost(solver_route, matrix, stops, depot),
        challenger=cost(challenger_route, matrix, stops, depot),
    )


def eta_minutes(distance_m: int, speed_kmh: float, service_minutes: int = 0) -> int:
    """Arithmetic, so no model ever tells a customer a time it reasoned out."""
    if speed_kmh <= 0:
        raise ValueError("speed must be positive")
    return round(distance_m / 1000 / speed_kmh * 60) + service_minutes
