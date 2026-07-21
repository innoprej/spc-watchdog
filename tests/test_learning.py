"""Lock the human-gated OCAP proposal and atomic version transition."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from spc_watchdog.learning import (
    approve_proposal,
    file_change_proposal,
    load_active_skill,
    reject_proposal,
)
from spc_watchdog.report import InvestigationReport, parse_report_json
from spc_watchdog.world import SCENARIO_2_ID, create_world


def _proposal_report(skill_id: str, digest: str) -> InvestigationReport:
    citation = {
        "id": "tool-life-s2-002",
        "table": "tool_life",
        "field": "cycle_count",
        "value": 9980,
    }
    return parse_report_json(
        json.dumps(
            {
                "schema_version": "1.0",
                "incident_id": "incident-s2-001",
                "skill": {"id": skill_id, "version": 1, "sha256": digest},
                "status": "concluded",
                "claims": [{"text": "Tool life is near its limit.", "citations": [citation]}],
                "root_cause": {"text": "Tool wear caused the trend.", "citations": [citation]},
                "skill_change_proposal": {
                    "base_version_id": skill_id,
                    "rationale": {
                        "text": "Accumulated cycles were decisive but absent from v1.",
                        "citations": [citation],
                    },
                    "proposed_step": "Query tool-life after recent equipment logs and before material genealogy; compare cycle count with its replacement limit.",
                },
            }
        )
    )


def test_reject_keeps_active_skill_unchanged(tmp_path: Path) -> None:
    database = tmp_path / "world.db"
    create_world(database, SCENARIO_2_ID)
    skill = load_active_skill(database, "trend")
    proposal = file_change_proposal(database, _proposal_report(skill.id, skill.sha256), skill)
    assert proposal is not None

    rejected = reject_proposal(database, proposal.id)

    assert rejected.status == "rejected"
    assert load_active_skill(database, "trend").id == "ocap-trend-v1"


def test_approve_atomically_creates_v2_and_survives_reset(tmp_path: Path) -> None:
    database = tmp_path / "world.db"
    create_world(database, SCENARIO_2_ID)
    skill = load_active_skill(database, "trend")
    proposal = file_change_proposal(database, _proposal_report(skill.id, skill.sha256), skill)
    assert proposal is not None
    assert proposal.patch.startswith("--- trend-ocap/SKILL.md@v1")
    assert "Learned v2 step" in proposal.patch

    approved = approve_proposal(database, proposal.id)
    create_world(database, SCENARIO_2_ID)
    active = load_active_skill(database, "trend")

    assert approved.status == "approved"
    assert approved.approved_version_id == "ocap-trend-v2"
    assert active.id == "ocap-trend-v2"
    assert active.version == 2
    assert "This is OCAP version 2" in active.body
    assert "This is OCAP version 1" not in active.body
    assert "before material genealogy" in active.body
    with pytest.raises(ValueError, match="not pending"):
        approve_proposal(database, proposal.id)
    with sqlite3.connect(database) as connection:
        versions = connection.execute(
            """SELECT id, status FROM ocap_versions
               WHERE signal_family = 'trend' ORDER BY version"""
        ).fetchall()
    assert versions == [
        ("ocap-trend-v1", "superseded"),
        ("ocap-trend-v2", "active"),
    ]
