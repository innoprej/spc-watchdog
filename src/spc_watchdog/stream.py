"""Translate generated measurements into ordered dashboard events."""

from __future__ import annotations

from dataclasses import asdict
from typing import Iterable

from .nelson import evaluate_latest
from .world import Measurement, derive_control_limits

SNAPSHOT_COUNT = 20
# Both seeded scenarios complete inside one simulated shift. A 24-hour causal
# window preserves later overlapping signals without reopening the same event.
INCIDENT_WINDOW = 24


def build_stream_events(measurements: Iterable[Measurement]) -> tuple[dict[str, object], ...]:
    """Create deterministic measurement, signal, and deduplicated incident events."""

    rows = tuple(measurements)
    center, sigma = derive_control_limits(rows)
    values: list[float] = []
    events: list[dict[str, object]] = []
    last_incident_index: int | None = None

    for row in rows:
        values.append(row.value)
        violations = evaluate_latest(values, center=center, sigma=sigma)
        incident: dict[str, object] | None = None
        if violations and (
            last_incident_index is None or row.sequence - last_incident_index > INCIDENT_WINDOW
        ):
            last_incident_index = row.sequence
            incident = {
                "id": "incident-s1-001",
                "opened_sim_hour": row.sim_hour,
                "primary_rule": violations[0].rule,
                "status": "investigation queued",
            }

        events.append(
            {
                "schema_version": "1.0",
                "type": "measurement",
                "sequence": row.sequence,
                "point": asdict(row),
                "violations": [asdict(violation) for violation in violations],
                "incident": incident,
            }
        )
    return tuple(events)
