"""Lock the broker to compact, incident-scoped, non-SQL evidence queries."""

from __future__ import annotations

import asyncio
import hashlib
import sqlite3
from pathlib import Path

import pytest

from spc_watchdog.broker import (
    BrokerScopeError,
    InvestigationBroker,
    open_incident,
)
from spc_watchdog.broker_mcp import BROKER_TOOL_NAMES, create_broker_mcp
from spc_watchdog.skill_mount import load_skill_mount
from spc_watchdog.world import create_world

ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = ROOT / "investigator" / "skills" / "mean-shift-ocap" / "SKILL.md"


@pytest.fixture
def broker(tmp_path: Path) -> InvestigationBroker:
    database = tmp_path / "world.db"
    create_world(database)
    open_incident(
        database,
        incident_id="incident-s1-001",
        scenario="scenario-1",
        opened_sim_hour=26,
        primary_rule=1,
    )
    return InvestigationBroker(
        database_path=database,
        incident_id="incident-s1-001",
    )


def test_broker_returns_the_three_hop_scenario_1_evidence(
    broker: InvestigationBroker,
) -> None:
    equipment = broker.query_equipment_logs("incident-s1-001")
    genealogy = broker.query_material_lots("incident-s1-001")
    inspection = broker.query_incoming_inspection("incident-s1-001", "lot-s1-b")

    assert [(row["id"], row["status"]) for row in equipment] == [
        ("equipment-s1-001", "pass"),
        ("equipment-s1-002", "pass"),
    ]
    assert [(row["id"], row["lot_id"], row["introduced_sim_hour"]) for row in genealogy] == [
        ("genealogy-s1-001", "lot-s1-a", 0),
        ("genealogy-s1-002", "lot-s1-b", 24),
    ]
    assert inspection == [
        {
            "table": "incoming_inspection",
            "id": "inspection-s1-002",
            "lot_id": "lot-s1-b",
            "characteristic": "hardness",
            "measured_value": 51.8,
            "lower_limit": 44.0,
            "upper_limit": 52.0,
            "disposition": "accepted-marginal",
        }
    ]


def test_broker_rejects_cross_incident_and_unknown_lot_requests(
    broker: InvestigationBroker,
) -> None:
    with pytest.raises(BrokerScopeError, match="scoped to"):
        broker.chart_context("incident-s2-001")
    with pytest.raises(BrokerScopeError, match="outside incident genealogy"):
        broker.query_incoming_inspection("incident-s1-001", "lot-not-in-scope")


def test_citation_lookup_rejects_rows_outside_fixed_incident_queries(
    broker: InvestigationBroker,
) -> None:
    """Scenario membership alone cannot make an invisible stale row citable."""

    with sqlite3.connect(broker._database_path) as connection:
        connection.execute(
            "INSERT INTO equipment_logs VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "equipment-s1-stale",
                "scenario-1",
                1,
                "press-07",
                "old-check",
                "pass",
                "Outside the incident lookback.",
            ),
        )

    with pytest.raises(BrokerScopeError, match="outside incident evidence"):
        broker.canonical_value(
            table="equipment_logs",
            row_id="equipment-s1-stale",
            field="status",
        )


def test_mcp_skill_load_returns_exact_body_and_only_registered_tools(
    broker: InvestigationBroker,
) -> None:
    skill = load_skill_mount(
        SKILL_PATH,
        skill_id="ocap-mean-shift-v1",
        name="mean-shift-ocap",
        signal_family="mean-shift",
        version=1,
    )
    server = create_broker_mcp(broker, skill)

    async def inspect_server() -> tuple[list[str], dict[str, object]]:
        tools = await server.list_tools()
        content, structured = await server.call_tool(
            "load_ocap_skill",
            {"incident_id": "incident-s1-001", "signal_family": "mean-shift"},
        )
        assert content
        assert isinstance(structured, dict)
        return [tool.name for tool in tools], structured

    tool_names, result = asyncio.run(inspect_server())
    body = SKILL_PATH.read_text(encoding="utf-8")

    assert tool_names == list(BROKER_TOOL_NAMES)
    assert result["body"] == body
    assert result["sha256"] == hashlib.sha256(body.encode("utf-8")).hexdigest()
    assert "lot-s1-b" not in result["body"]
    assert "root cause" in result["body"]
