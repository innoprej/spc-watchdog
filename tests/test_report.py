"""Make tampered ids, fields, values, and skill identities fail closed."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spc_watchdog.broker import InvestigationBroker, open_incident
from spc_watchdog.learning import load_active_skill
from spc_watchdog.report import parse_report_json, verify_report
from spc_watchdog.skill_mount import load_skill_mount
from spc_watchdog.world import SCENARIO_2_ID, create_world

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "investigator" / "report.schema.json"


def _walk_schema(node: object):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk_schema(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk_schema(value)


def test_committed_report_schema_matches_strict_structured_output_shape() -> None:
    """Regress the exact file passed to `codex exec --output-schema`."""

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert schema["type"] == "object"
    for node in _walk_schema(schema):
        if "const" in node or "enum" in node:
            assert "type" in node
        if node.get("type") == "object":
            assert node.get("additionalProperties") is False
            assert set(node.get("required", [])) == set(node.get("properties", {}))


@pytest.fixture
def verification_context(tmp_path: Path):
    database = tmp_path / "world.db"
    create_world(database)
    open_incident(
        database,
        incident_id="incident-s1-001",
        scenario="scenario-1",
        opened_sim_hour=26,
        primary_rule=1,
    )
    broker = InvestigationBroker(
        database_path=database, incident_id="incident-s1-001"
    )
    skill = load_skill_mount(
        ROOT / "investigator" / "skills" / "mean-shift-ocap" / "SKILL.md",
        skill_id="ocap-mean-shift-v1",
        name="mean-shift-ocap",
        signal_family="mean-shift",
        version=1,
    )
    return broker, skill


def _report(skill_sha256: str) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "incident_id": "incident-s1-001",
        "skill": {
            "id": "ocap-mean-shift-v1",
            "version": 1,
            "sha256": skill_sha256,
        },
        "status": "concluded",
        "claims": [
            {
                "text": "Recent equipment checks passed.",
                "citations": [
                    {
                        "id": "equipment-s1-002",
                        "table": "equipment_logs",
                        "field": "status",
                        "value": "pass",
                    }
                ],
            }
        ],
        "root_cause": {
            "text": "The changed lot is implicated by its marginal inspection.",
            "citations": [
                {
                    "id": "inspection-s1-002",
                    "table": "incoming_inspection",
                    "field": "disposition",
                    "value": "accepted-marginal",
                }
            ],
        },
    }


def test_citation_verifier_accepts_canonical_rows(verification_context) -> None:
    broker, skill = verification_context
    report = parse_report_json(json.dumps(_report(skill.sha256)))

    result = verify_report(report, broker=broker, skill=skill)

    assert result.passed
    assert result.citation_count == 2
    assert result.failures == ()


@pytest.mark.parametrize(
    ("key", "tampered"),
    [
        ("id", "equipment-does-not-exist"),
        ("field", "not_a_real_field"),
        ("value", "fail"),
    ],
)
def test_citation_verifier_rejects_tampered_row_field_or_value(
    verification_context, key: str, tampered: str
) -> None:
    broker, skill = verification_context
    payload = _report(skill.sha256)
    payload["claims"][0]["citations"][0][key] = tampered  # type: ignore[index]
    report = parse_report_json(json.dumps(payload))

    result = verify_report(report, broker=broker, skill=skill)

    assert not result.passed
    assert len(result.failures) == 1


def test_citation_verifier_rejects_unmounted_skill_digest(
    verification_context,
) -> None:
    broker, skill = verification_context
    report = parse_report_json(json.dumps(_report("0" * 64)))

    result = verify_report(report, broker=broker, skill=skill)

    assert not result.passed
    assert result.failures[0].claim_text == "OCAP skill identity"


def test_citation_verifier_binds_report_to_broker_incident(
    verification_context,
) -> None:
    broker, skill = verification_context
    payload = _report(skill.sha256)
    payload["incident_id"] = "incident-wrong"
    report = parse_report_json(json.dumps(payload))

    result = verify_report(report, broker=broker, skill=skill)

    assert not result.passed
    assert any(failure.claim_text == "Incident identity" for failure in result.failures)


def test_citation_verifier_rejects_boolean_for_integer_field(
    verification_context,
) -> None:
    broker, skill = verification_context
    payload = _report(skill.sha256)
    citation = payload["claims"][0]["citations"][0]  # type: ignore[index]
    citation.update(
        {
            "id": "incident-s1-001",
            "table": "incidents",
            "field": "primary_rule",
            "value": True,
        }
    )

    result = verify_report(
        parse_report_json(json.dumps(payload)), broker=broker, skill=skill
    )

    assert not result.passed


def test_citation_verifier_normalizes_equivalent_json_numbers(
    verification_context,
) -> None:
    broker, skill = verification_context
    payload = _report(skill.sha256)
    citation = payload["root_cause"]["citations"][0]  # type: ignore[index]
    citation.update(
        {
            "id": "inspection-s1-002",
            "table": "incoming_inspection",
            "field": "upper_limit",
            "value": 52,
        }
    )

    result = verify_report(
        parse_report_json(json.dumps(payload)), broker=broker, skill=skill
    )

    assert result.passed


def test_report_schema_rejects_a_claim_without_citations(
    verification_context,
) -> None:
    _, skill = verification_context
    payload = _report(skill.sha256)
    payload["claims"][0]["citations"] = []  # type: ignore[index]

    with pytest.raises(ValueError, match="invalid investigation report"):
        parse_report_json(json.dumps(payload))


def test_v1_trend_report_requires_proposal_for_decisive_tool_life(
    tmp_path: Path,
) -> None:
    """A v1 evidence-source gap cannot silently disappear from the LEARN loop."""

    database = tmp_path / "world.db"
    create_world(database, SCENARIO_2_ID)
    open_incident(
        database,
        incident_id="incident-s2-001",
        scenario=SCENARIO_2_ID,
        opened_sim_hour=29,
        primary_rule=3,
    )
    broker = InvestigationBroker(
        database_path=database, incident_id="incident-s2-001"
    )
    skill = load_active_skill(database, "trend")
    payload = {
        "schema_version": "1.0",
        "incident_id": "incident-s2-001",
        "skill": {
            "id": skill.id,
            "version": skill.version,
            "sha256": skill.sha256,
        },
        "status": "concluded",
        "claims": [
            {
                "text": "Tool life is near its replacement limit.",
                "citations": [
                    {
                        "id": "tool-life-s2-002",
                        "table": "tool_life",
                        "field": "status",
                        "value": "replacement-due",
                    }
                ],
            }
        ],
        "root_cause": {
            "text": "Tool wear caused the trend.",
            "citations": [
                {
                    "id": "tool-life-s2-002",
                    "table": "tool_life",
                    "field": "cycle_count",
                    "value": 9980,
                }
            ],
        },
        "skill_change_proposal": None,
    }

    result = verify_report(
        parse_report_json(json.dumps(payload)), broker=broker, skill=skill
    )

    assert not result.passed
    assert result.failures[0].claim_text == "Required playbook-gap proposal"
