"""Play sanitized canonical investigations with their original relative timing."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ReplaySubmission:
    """The small coordinator-compatible result of submitting a replay incident."""

    incident_id: str
    run_id: str


@dataclass(frozen=True, slots=True)
class ReplayPhase:
    """One immutable live-run fixture used by a replay phase."""

    name: str
    events: tuple[dict[str, Any], ...]
    report: dict[str, Any]
    proposal: dict[str, Any] | None

    @property
    def run_id(self) -> str:
        return str(self.events[0]["run_id"])


def _timestamp(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


class ReplayCoordinator:
    """Expose recorded runs through the same snapshot contract as live Codex."""

    def __init__(self, *, fixture_root: Path, scenario: str) -> None:
        manifest_path = fixture_root / scenario / "manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"replay fixture is missing: {manifest_path}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema_version") != "1.0":
            raise ValueError("unsupported replay manifest schema")
        self.scenario = scenario
        self.incident_id = str(manifest["incident_id"])
        self._fixture_directory = manifest_path.parent
        self._phases = {
            name: self._load_phase(name, definition)
            for name, definition in manifest["phases"].items()
        }
        self._phase_name = str(manifest["initial_phase"])
        self._speed = 1
        self._submitted = False
        self._elapsed_at_anchor = 0.0
        self._anchor = time.monotonic()
        self._active_skill_version = int(manifest.get("active_skill_version", 1))
        self._proposal_status = "pending"

    def _load_phase(self, name: str, definition: dict[str, Any]) -> ReplayPhase:
        event_path = self._fixture_directory / str(definition["event_log"])
        events = tuple(
            json.loads(line)
            for line in event_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        if not events or any(event.get("schema_version") != "1.0" for event in events):
            raise ValueError(f"invalid replay event log: {event_path}")
        report_path = self._fixture_directory / str(definition["report"])
        proposal_name = definition.get("proposal")
        proposal = (
            json.loads(
                (self._fixture_directory / str(proposal_name)).read_text(encoding="utf-8")
            )
            if proposal_name
            else None
        )
        return ReplayPhase(
            name=name,
            events=events,
            report=json.loads(report_path.read_text(encoding="utf-8")),
            proposal=proposal,
        )

    @property
    def speed(self) -> int:
        return self._speed

    @property
    def phase_name(self) -> str:
        return self._phase_name

    @property
    def active_skill_version(self) -> int:
        return self._active_skill_version

    def set_speed(self, speed: int) -> None:
        """Change speed without jumping the current replay clock."""

        if speed not in {1, 2, 4}:
            raise ValueError("replay speed must be 1, 2, or 4")
        self._elapsed_at_anchor = self._elapsed()
        self._anchor = time.monotonic()
        self._speed = speed

    def _elapsed(self) -> float:
        return self._elapsed_at_anchor + (time.monotonic() - self._anchor) * self._speed

    def _restart_phase(self, phase_name: str) -> None:
        self._phase_name = phase_name
        self._submitted = True
        self._elapsed_at_anchor = 0.0
        self._anchor = time.monotonic()

    def submit(self, incident_id: str) -> ReplaySubmission:
        if incident_id != self.incident_id:
            raise KeyError(incident_id)
        if not self._submitted:
            self._restart_phase(self._phase_name)
        return ReplaySubmission(incident_id=incident_id, run_id=self._phase().run_id)

    def _phase(self) -> ReplayPhase:
        return self._phases[self._phase_name]

    def _available_events(self) -> tuple[dict[str, Any], ...]:
        if not self._submitted:
            return ()
        phase = self._phase()
        first_time = _timestamp(str(phase.events[0]["recorded_at"]))
        elapsed = self._elapsed()
        return tuple(
            event
            for event in phase.events
            if _timestamp(str(event["recorded_at"])) - first_time <= elapsed
        )

    def snapshot(self, incident_id: str, *, after: int = 0) -> dict[str, object]:
        if incident_id != self.incident_id or not self._submitted:
            raise KeyError(incident_id)
        phase = self._phase()
        available = self._available_events()
        complete = len(available) == len(phase.events)
        proposal = dict(phase.proposal) if phase.proposal is not None else None
        if proposal is not None:
            proposal["status"] = self._proposal_status
        return {
            "schema_version": "1.0",
            "incident_id": incident_id,
            "run_id": phase.run_id,
            "status": "completed" if complete else "investigating",
            "events": [event for event in available if int(event["sequence"]) > after],
            "report": phase.report if complete else None,
            "proposal": proposal if complete else None,
            "replay_phase": self._phase_name,
            "active_skill_version": self._active_skill_version,
        }

    def approve(self, proposal_id: str) -> dict[str, object]:
        """Advance the recorded Scenario 2 session only after its v1 proposal exists."""

        phase = self._phase()
        if (
            self.scenario != "scenario-2"
            or phase.proposal is None
            or phase.proposal.get("id") != proposal_id
            or self._proposal_status != "pending"
            or len(self._available_events()) != len(phase.events)
        ):
            raise ValueError("proposal is not ready for replay approval")
        if "v2" not in self._phases:
            raise ValueError("v2 replay phase is missing")
        self._proposal_status = "approved"
        self._active_skill_version = 2
        self._restart_phase("v2")
        return {
            "schema_version": "1.0",
            "proposal_id": proposal_id,
            "status": "approved",
            "active_version_id": "ocap-trend-v2",
            "replay_phase": "v2",
        }

    def reject(self, proposal_id: str) -> dict[str, object]:
        phase = self._phase()
        if (
            phase.proposal is None
            or phase.proposal.get("id") != proposal_id
            or self._proposal_status != "pending"
        ):
            raise ValueError("proposal is not ready for replay rejection")
        self._proposal_status = "rejected"
        return {
            "schema_version": "1.0",
            "proposal_id": proposal_id,
            "status": "rejected",
            "active_version_id": "ocap-trend-v1",
            "replay_phase": self._phase_name,
        }

    def close(self) -> None:
        """Match the live coordinator lifecycle contract."""
