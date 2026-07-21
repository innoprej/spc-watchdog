"""Exercise the verifier-owned single retry without launching live Codex."""

from __future__ import annotations

import json
from pathlib import Path

from pytest import MonkeyPatch

from spc_watchdog import investigation_runner as runner_module
from spc_watchdog.broker import open_incident
from spc_watchdog.world import create_world


class _NoopBrokerService:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        pass


def test_verification_failure_triggers_one_corrective_retry(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    database = tmp_path / "world.db"
    create_world(database)
    open_incident(
        database,
        incident_id="incident-s1-001",
        scenario="scenario-1",
        opened_sim_hour=26,
        primary_rule=1,
    )
    attempts: list[int] = []

    def install_auth(_source: Path, destination: Path) -> None:
        destination.mkdir(parents=True)

    def fake_attempt(**kwargs) -> tuple[int, str]:
        attempt = kwargs["attempt"]
        attempts.append(attempt)
        status = "wrong" if attempt == 1 else "pass"
        skill = kwargs["skill"]
        report = {
            "schema_version": "1.0",
            "incident_id": "incident-s1-001",
            "skill": {"id": skill.id, "version": 1, "sha256": skill.sha256},
            "status": "concluded",
            "claims": [
                {
                    "text": "Equipment status was checked.",
                    "citations": [
                        {
                            "id": "equipment-s1-002",
                            "table": "equipment_logs",
                            "field": "status",
                            "value": status,
                        }
                    ],
                }
            ],
            "root_cause": {
                "text": "The material inspection is marginal.",
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
        return 0, json.dumps(report)

    monkeypatch.setattr(runner_module, "_resolve_codex_executable", lambda: "codex")
    monkeypatch.setattr(runner_module, "_install_credential_only_codex_home", install_auth)
    monkeypatch.setattr(runner_module, "_BrokerService", _NoopBrokerService)
    monkeypatch.setattr(runner_module, "_run_attempt", fake_attempt)

    outcome = runner_module.run_live_investigation(
        database_path=database,
        incident_id="incident-s1-001",
        run_directory=tmp_path / "run",
        user_codex_home=tmp_path / "user-codex",
    )
    events = [
        json.loads(line)
        for line in (tmp_path / "run" / "events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    verifier_results = [
        event["payload"]["passed"]
        for event in events
        if event["type"] == "verifier"
    ]

    assert attempts == [1, 2]
    assert outcome.attempts == 2
    assert outcome.verification is not None and outcome.verification.passed
    assert verifier_results == [False, True]
