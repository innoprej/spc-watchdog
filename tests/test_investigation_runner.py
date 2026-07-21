"""Exercise the verifier-owned single retry without launching live Codex."""

from __future__ import annotations

import json
import io
import threading
from pathlib import Path

from pytest import MonkeyPatch

from spc_watchdog import investigation_runner as runner_module
from spc_watchdog.broker import open_incident
from spc_watchdog.event_log import EventLog
from spc_watchdog.report import Citation, CitationFailure, VerificationResult
from spc_watchdog.skill_mount import SkillMount
from spc_watchdog.world import create_world


class _NoopBrokerService:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        pass


def test_retry_feedback_never_leaks_a_canonical_database_value() -> None:
    """A rejected citation must force an MCP re-query, not reveal the answer in stdin."""

    failure = CitationFailure(
        claim_text="Equipment status was checked.",
        citation=Citation(
            id="equipment-s1-002",
            table="equipment_logs",
            field="status",
            value="wrong",
        ),
        reason="expected canonical value 'secret-pass-value'",
    )
    feedback = runner_module._verification_feedback(
        VerificationResult(False, (failure,), 1)
    )

    assert "equipment_logs/equipment-s1-002.status" in feedback
    assert "registered broker tool" in feedback
    assert "secret-pass-value" not in feedback


def test_attempt_timeout_terminates_a_hung_codex_process(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """The sole investigator worker must recover when the JSONL stream never ends."""

    release = threading.Event()

    class BlockingStdout:
        def __iter__(self):
            return self

        def __next__(self) -> str:
            release.wait()
            raise StopIteration

    class HangingProcess:
        def __init__(self) -> None:
            self.stdin = io.StringIO()
            self.stdout = BlockingStdout()
            self.stderr = io.StringIO()
            self.terminated = False

        def terminate(self) -> None:
            self.terminated = True
            release.set()

        def kill(self) -> None:
            release.set()

        def wait(self, timeout: float | None = None) -> int:
            return 124

    process = HangingProcess()
    monkeypatch.setattr(runner_module.subprocess, "Popen", lambda *args, **kwargs: process)
    runtime = tmp_path / "runtime"
    codex_home = tmp_path / "codex-home"
    runtime.mkdir()
    codex_home.mkdir()
    (runtime / "AGENTS.md").write_text("Use only broker tools.", encoding="utf-8")
    (runtime / "report.schema.json").write_text("{}", encoding="utf-8")
    skill = SkillMount(
        id="ocap-mean-shift-v1",
        name="mean-shift-ocap",
        signal_family="mean-shift",
        version=1,
        sha256="a" * 64,
        body="Follow the evidence.",
    )
    event_log = EventLog(path=tmp_path / "run" / "events.jsonl", run_id="run-1")

    return_code, payload = runner_module._run_attempt(
        attempt=1,
        runtime_workspace=runtime,
        codex_home=codex_home,
        mcp_url="http://127.0.0.1:1/mcp",
        incident_id="incident-s1-001",
        skill=skill,
        event_log=event_log,
        raw_event_path=tmp_path / "run" / "raw.jsonl",
        retry_feedback=None,
        codex_executable="codex",
        attempt_timeout_seconds=0.01,
    )

    assert return_code == 124
    assert payload == ""
    assert process.terminated
    assert any(event.type == "runtime_error" for event in event_log.after(0))


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
