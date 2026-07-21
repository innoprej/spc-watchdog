"""Verify ordered resume behavior and fail-closed skill-load normalization."""

from __future__ import annotations

from pathlib import Path

from spc_watchdog.event_log import EventLog, normalize_codex_event
from spc_watchdog.skill_mount import SkillMount


def _skill() -> SkillMount:
    body = "---\nname: mean-shift-ocap\n---\n\nFollow the evidence.\n"
    return SkillMount(
        id="ocap-mean-shift-v1",
        name="mean-shift-ocap",
        signal_family="mean-shift",
        version=1,
        sha256="a" * 64,
        body=body,
    )


def test_event_log_resumes_after_acknowledged_sequence(tmp_path: Path) -> None:
    log = EventLog(path=tmp_path / "events.jsonl", run_id="run-1")
    first = log.append("status", {"state": "started"})
    second = log.append("tool_call", {"tool": "chart_context"})
    third = log.append("evidence", {"rows": 1})

    assert [event.sequence for event in log.after(first.sequence)] == [
        second.sequence,
        third.sequence,
    ]
    assert EventLog(path=log.path, run_id="run-1").append(
        "status", {"state": "completed"}
    ).sequence == 4


def test_skill_load_requires_exact_body_and_digest_in_completed_mcp_event() -> None:
    skill = _skill()
    completed = {
        "type": "item.completed",
        "item": {
            "type": "mcp_tool_call",
            "tool": "load_ocap_skill",
            "status": "completed",
            "result": {"sha256": skill.sha256, "body": skill.body},
        },
    }

    assert normalize_codex_event(completed, expected_skill=skill)[0][0] == "skill_load"

    completed["item"]["result"]["body"] = "metadata only"
    assert (
        normalize_codex_event(completed, expected_skill=skill)[0][0]
        == "skill_load_rejected"
    )
