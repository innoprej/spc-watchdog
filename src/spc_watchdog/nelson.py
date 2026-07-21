"""Pure Nelson Rules 1-3 evaluation; statistical verdicts never reach an LLM."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True, slots=True)
class RuleViolation:
    """A deterministic rule result anchored to an exact sample window."""

    rule: int
    start_index: int
    end_index: int
    direction: str
    observed: float
    limit: float | None


def evaluate_latest(
    values: Sequence[float], *, center: float, sigma: float
) -> tuple[RuleViolation, ...]:
    """Return Nelson violations whose deciding window ends at the latest point.

    Rule 1 uses a strict three-sigma boundary, Rule 2 requires nine points
    strictly on one side of center, and Rule 3 requires six strictly monotonic
    points. Equality therefore breaks every relevant sequence.
    """

    if sigma <= 0:
        raise ValueError("sigma must be greater than zero")
    if not values:
        return ()

    end = len(values) - 1
    latest = float(values[-1])
    violations: list[RuleViolation] = []

    upper = center + 3 * sigma
    lower = center - 3 * sigma
    if latest > upper:
        violations.append(RuleViolation(1, end, end, "above", latest, upper))
    elif latest < lower:
        violations.append(RuleViolation(1, end, end, "below", latest, lower))

    if len(values) >= 9:
        window = values[-9:]
        if all(value > center for value in window):
            violations.append(RuleViolation(2, end - 8, end, "above", latest, center))
        elif all(value < center for value in window):
            violations.append(RuleViolation(2, end - 8, end, "below", latest, center))

    if len(values) >= 6:
        window = values[-6:]
        if all(left < right for left, right in zip(window, window[1:])):
            violations.append(RuleViolation(3, end - 5, end, "increasing", latest, None))
        elif all(left > right for left, right in zip(window, window[1:])):
            violations.append(RuleViolation(3, end - 5, end, "decreasing", latest, None))

    return tuple(violations)


def evaluate_series(
    values: Sequence[float], *, center: float, sigma: float
) -> tuple[RuleViolation, ...]:
    """Evaluate a complete series while preserving overlapping rule evidence."""

    violations: list[RuleViolation] = []
    for end in range(len(values)):
        violations.extend(evaluate_latest(values[: end + 1], center=center, sigma=sigma))
    return tuple(violations)
