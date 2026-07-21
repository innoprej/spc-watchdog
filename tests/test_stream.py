"""Tests for signal transparency and deterministic incident deduplication."""

from __future__ import annotations

from spc_watchdog.stream import build_stream_events
from spc_watchdog.world import SCENARIO_2_ID, generate_measurements


def test_stream_exposes_rule_1_then_overlapping_rule_2_without_duplicate_incident() -> None:
    events = build_stream_events(generate_measurements())
    signaled = [event for event in events if event["violations"]]
    incidents = [event["incident"] for event in events if event["incident"]]

    assert signaled[0]["sequence"] == 26
    assert signaled[0]["violations"][0]["rule"] == 1
    assert any(
        violation["rule"] == 2
        for event in signaled
        for violation in event["violations"]
    )
    assert incidents == [
        {
            "id": "incident-s1-001",
            "opened_sim_hour": 26,
            "primary_rule": 1,
            "status": "investigation queued",
        }
    ]


def test_scenario_2_stream_opens_rule_3_incident() -> None:
    events = build_stream_events(generate_measurements(SCENARIO_2_ID))
    incidents = [event["incident"] for event in events if event["incident"]]

    assert incidents == [
        {
            "id": "incident-s2-001",
            "opened_sim_hour": 29,
            "primary_rule": 3,
            "status": "investigation queued",
        }
    ]
