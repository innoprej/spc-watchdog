"""Lock credential-free replay timing, ordering, and the recorded v2 improvement."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from pytest import MonkeyPatch

from spc_watchdog import replay as replay_module
from spc_watchdog.replay import ReplayCoordinator

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"


def test_replay_speed_preserves_elapsed_time(monkeypatch: MonkeyPatch) -> None:
    now = [100.0]
    monkeypatch.setattr(replay_module.time, "monotonic", lambda: now[0])
    replay = ReplayCoordinator(fixture_root=FIXTURES, scenario="scenario-1")
    replay.submit("incident-s1-001")

    now[0] = 110.0
    before = replay.snapshot("incident-s1-001")
    replay.set_speed(2)
    now[0] = 115.0
    after = replay.snapshot("incident-s1-001")

    assert len(after["events"]) >= len(before["events"])
    assert replay.speed == 2


def test_scenario_two_replay_approval_advances_to_smarter_v2(
    monkeypatch: MonkeyPatch,
) -> None:
    now = [100.0]
    monkeypatch.setattr(replay_module.time, "monotonic", lambda: now[0])
    replay = ReplayCoordinator(fixture_root=FIXTURES, scenario="scenario-2")
    replay.submit("incident-s2-001")
    now[0] = 200.0

    v1 = replay.snapshot("incident-s2-001")
    v1_tools = [
        event["payload"]["tool"]
        for event in v1["events"]
        if event["type"] == "tool_call"
    ]
    proposal = v1["proposal"]
    assert isinstance(proposal, dict)
    assert v1_tools.index("query_material_lots") < v1_tools.index("query_tool_life")

    approved = replay.approve(str(proposal["id"]))
    now[0] = 300.0
    v2 = replay.snapshot("incident-s2-001")
    v2_tools = [
        event["payload"]["tool"]
        for event in v2["events"]
        if event["type"] == "tool_call"
    ]

    assert approved["active_version_id"] == "ocap-trend-v2"
    assert v2["active_skill_version"] == 2
    assert v1_tools == [
        "load_ocap_skill",
        "chart_context",
        "query_equipment_logs",
        "query_material_lots",
        "query_incoming_inspection",
        "query_tool_life",
    ]
    assert v2_tools == [
        "load_ocap_skill",
        "chart_context",
        "query_equipment_logs",
        "query_tool_life",
    ]


def test_committed_fixtures_are_versioned_and_public_safe() -> None:
    forbidden = re.compile(
        r"(?i)(?:[a-z]:[\\/]|/(?:home|users)/|shin jaehee|"
        r"(?:api[_-]?key|authorization|bearer|password|secret|credential|token)\s*[:=])"
    )
    fixture_files = [
        path
        for scenario in (FIXTURES / "scenario-1", FIXTURES / "scenario-2")
        for path in scenario.iterdir()
        if path.is_file()
    ]

    for path in fixture_files:
        contents = path.read_text(encoding="utf-8")
        assert not forbidden.search(contents), path
        if path.suffix == ".jsonl":
            rows = [json.loads(line) for line in contents.splitlines() if line.strip()]
            assert rows
            assert all(row["schema_version"] == "1.0" for row in rows)


def test_replay_rejection_is_terminal(monkeypatch: MonkeyPatch) -> None:
    now = [100.0]
    monkeypatch.setattr(replay_module.time, "monotonic", lambda: now[0])
    replay = ReplayCoordinator(fixture_root=FIXTURES, scenario="scenario-2")
    replay.submit("incident-s2-001")
    now[0] = 200.0

    rejected = replay.reject("proposal-incident-s2-001-v1")
    snapshot = replay.snapshot("incident-s2-001")

    assert rejected["status"] == "rejected"
    assert snapshot["proposal"]["status"] == "rejected"  # type: ignore[index]
    assert snapshot["active_skill_version"] == 1
    with pytest.raises(ValueError, match="not ready"):
        replay.approve("proposal-incident-s2-001-v1")
