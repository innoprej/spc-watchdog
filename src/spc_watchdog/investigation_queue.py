"""Serialize incident investigations and expose their persisted run state."""

from __future__ import annotations

import json
import queue
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .event_log import EventLog
from .investigation_runner import InvestigationOutcome, run_live_investigation

InvestigationRunner = Callable[..., InvestigationOutcome]


@dataclass(slots=True)
class InvestigationState:
    """Mutable host state for one queued or completed incident run."""

    incident_id: str
    run_id: str
    run_directory: Path
    status: str = "queued"
    outcome: InvestigationOutcome | None = None


class InvestigationCoordinator:
    """Run at most one investigator at a time and deduplicate incident submissions."""

    def __init__(
        self,
        *,
        database_path: Path,
        runs_root: Path,
        runner: InvestigationRunner = run_live_investigation,
    ) -> None:
        self._database_path = database_path
        self._runs_root = runs_root
        self._runner = runner
        self._states: dict[str, InvestigationState] = {}
        self._jobs: queue.Queue[InvestigationState | None] = queue.Queue()
        self._lock = threading.Lock()
        self._worker: threading.Thread | None = None

    def _ensure_worker(self) -> None:
        if self._worker is None:
            self._worker = threading.Thread(target=self._work, daemon=True)
            self._worker.start()

    def submit(self, incident_id: str) -> InvestigationState:
        """Queue an incident once and return its stable active-run mapping."""

        with self._lock:
            existing = self._states.get(incident_id)
            if existing is not None:
                return existing
            run_id = f"run-{incident_id}-{uuid.uuid4().hex[:8]}"
            state = InvestigationState(
                incident_id=incident_id,
                run_id=run_id,
                run_directory=self._runs_root / run_id,
            )
            self._states[incident_id] = state
            EventLog(
                path=state.run_directory / "events.jsonl", run_id=run_id
            ).append("status", {"state": "queued", "incident_id": incident_id})
            self._ensure_worker()
            self._jobs.put(state)
            return state

    def get(self, incident_id: str) -> InvestigationState | None:
        """Return the current run for an incident without exposing mutable internals."""

        with self._lock:
            return self._states.get(incident_id)

    def snapshot(self, incident_id: str, *, after: int = 0) -> dict[str, object]:
        """Return persisted events after a client cursor and only a verified report."""

        state = self.get(incident_id)
        if state is None:
            raise KeyError(incident_id)
        events = EventLog(
            path=state.run_directory / "events.jsonl", run_id=state.run_id
        ).after(after)
        report_path = state.run_directory / "report.json"
        report = (
            json.loads(report_path.read_text(encoding="utf-8"))
            if report_path.is_file() and state.status in {"completed", "inconclusive"}
            else None
        )
        return {
            "schema_version": "1.0",
            "incident_id": incident_id,
            "run_id": state.run_id,
            "status": state.status,
            "events": [event.as_dict() for event in events],
            "report": report,
        }

    def _work(self) -> None:
        while True:
            state = self._jobs.get()
            if state is None:
                self._jobs.task_done()
                return
            state.status = "investigating"
            try:
                outcome = self._runner(
                    database_path=self._database_path,
                    incident_id=state.incident_id,
                    run_directory=state.run_directory,
                    run_id=state.run_id,
                )
                state.outcome = outcome
                if outcome.verification is not None and outcome.verification.passed:
                    state.status = (
                        "inconclusive"
                        if outcome.report is not None
                        and outcome.report.status == "insufficient-evidence"
                        else "completed"
                    )
                else:
                    state.status = "failed"
                if state.status == "failed":
                    EventLog(
                        path=state.run_directory / "events.jsonl",
                        run_id=state.run_id,
                    ).append(
                        "status",
                        {"state": "run_failed", "reason": "verification did not pass"},
                    )
            except Exception as error:  # pragma: no cover - defensive host boundary
                state.status = "failed"
                log = EventLog(
                    path=state.run_directory / "events.jsonl", run_id=state.run_id
                )
                log.append("runtime_error", {"reason": str(error)})
                log.append("status", {"state": "run_failed"})
            finally:
                self._jobs.task_done()

    def wait(self, timeout: float = 120.0) -> None:
        """Wait for tests and controlled shutdowns without polling shared state."""

        completed = threading.Event()

        def mark_when_done() -> None:
            self._jobs.join()
            completed.set()

        threading.Thread(target=mark_when_done, daemon=True).start()
        if not completed.wait(timeout):
            raise TimeoutError("investigation queue did not drain")

    def close(self) -> None:
        """Stop the idle worker; an active Codex run is allowed to finish safely."""

        if self._worker is None:
            return
        self._jobs.put(None)
        self._worker.join(timeout=5)
