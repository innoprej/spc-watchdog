"""Prove incident deduplication, serialization, and cursor-based snapshots."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from spc_watchdog.event_log import EventLog
from spc_watchdog.investigation_queue import InvestigationCoordinator
from spc_watchdog.investigation_runner import InvestigationOutcome
from spc_watchdog.report import VerificationResult


def test_coordinator_serializes_runs_and_deduplicates_incidents(tmp_path: Path) -> None:
    active = 0
    maximum_active = 0
    order: list[str] = []
    lock = threading.Lock()

    def fake_runner(**kwargs) -> InvestigationOutcome:
        nonlocal active, maximum_active
        with lock:
            active += 1
            maximum_active = max(maximum_active, active)
        order.append(kwargs["incident_id"])
        EventLog(
            path=kwargs["run_directory"] / "events.jsonl",
            run_id=kwargs["run_id"],
        ).append("status", {"state": "run_completed"})
        time.sleep(0.02)
        with lock:
            active -= 1
        return InvestigationOutcome(
            run_id=kwargs["run_id"],
            attempts=1,
            report=None,
            verification=VerificationResult(True, (), 0),
            run_directory=kwargs["run_directory"],
        )

    coordinator = InvestigationCoordinator(
        database_path=tmp_path / "world.db",
        runs_root=tmp_path / "runs",
        runner=fake_runner,
    )
    first = coordinator.submit("incident-1")
    duplicate = coordinator.submit("incident-1")
    second = coordinator.submit("incident-2")
    coordinator.wait()

    assert duplicate.run_id == first.run_id
    assert second.run_id != first.run_id
    assert order == ["incident-1", "incident-2"]
    assert maximum_active == 1


def test_snapshot_resumes_after_sequence_and_hides_unverified_report(
    tmp_path: Path,
) -> None:
    release = threading.Event()

    def fake_runner(**kwargs) -> InvestigationOutcome:
        log = EventLog(
            path=kwargs["run_directory"] / "events.jsonl", run_id=kwargs["run_id"]
        )
        log.append("tool_call", {"tool": "chart_context"})
        log.append("verifier", {"passed": False})
        (kwargs["run_directory"] / "report.json").write_text(
            json.dumps({"must_not_render": True}), encoding="utf-8"
        )
        release.set()
        return InvestigationOutcome(
            run_id=kwargs["run_id"],
            attempts=1,
            report=None,
            verification=VerificationResult(False, (), 0),
            run_directory=kwargs["run_directory"],
        )

    coordinator = InvestigationCoordinator(
        database_path=tmp_path / "world.db",
        runs_root=tmp_path / "runs",
        runner=fake_runner,
    )
    state = coordinator.submit("incident-1")
    assert release.wait(2)
    coordinator.wait()

    snapshot = coordinator.snapshot("incident-1", after=1)

    assert snapshot["run_id"] == state.run_id
    assert [event["sequence"] for event in snapshot["events"]] == [2, 3, 4]
    assert snapshot["status"] == "failed"
    assert snapshot["report"] is None
