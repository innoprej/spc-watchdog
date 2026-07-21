"""API boundary tests for credential-free replay and explicit live readiness."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from spc_watchdog import app as app_module
from spc_watchdog.event_log import EventLog
from spc_watchdog.investigation_queue import InvestigationCoordinator
from spc_watchdog.investigation_runner import InvestigationOutcome
from spc_watchdog.report import VerificationResult
from spc_watchdog.replay import ReplayCoordinator
from spc_watchdog import replay as replay_module

ROOT = Path(__file__).resolve().parents[1]


def health_json(app: FastAPI) -> dict[str, object]:
    """Call the ASGI app without depending on a deprecated test client shim."""

    async def request() -> dict[str, object]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/health")
            assert response.status_code == 200
            return response.json()

    return asyncio.run(request())


def test_replay_health_requires_no_credentials(tmp_path: Path) -> None:
    app = app_module.create_app(mode="replay", data_path=tmp_path / "replay.db")
    payload = health_json(app)

    assert payload["credentials_required"] is False
    assert payload["investigator_status"] == "not required in deterministic replay"


def test_live_health_reports_missing_codex_cli(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    def missing_cli(_: str) -> None:
        return None

    monkeypatch.setattr(app_module.shutil, "which", missing_cli)
    app = app_module.create_app(mode="live", data_path=tmp_path / "live.db")
    payload = health_json(app)

    assert payload["credentials_required"] is True
    assert payload["investigator_status"] == "unavailable: Codex CLI was not found on PATH"


def test_watch_socket_reaches_the_first_rule_one_incident(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """Lock the dashboard contract from its 5-point snapshot through the red verdict."""

    async def no_delay(_: float) -> None:
        return None

    monkeypatch.setattr(app_module.asyncio, "sleep", no_delay)
    app = app_module.create_app(mode="replay", data_path=tmp_path / "socket.db")

    with TestClient(app) as client:
        with client.websocket_connect("/ws/watch") as websocket:
            snapshot = websocket.receive_json()
            assert snapshot["type"] == "snapshot"
            assert len(snapshot["events"]) == 5
            events = [websocket.receive_json() for _ in range(22)]

    verdict = events[-1]
    assert verdict["sequence"] == 26
    assert verdict["violations"][0]["rule"] == 1
    assert verdict["incident"]["id"] == "incident-s1-001"


def test_investigation_socket_resumes_without_duplicates_and_returns_verified_report(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """A reconnect cursor omits acknowledged events and exposes only a passed report."""

    async def no_delay(_: float) -> None:
        return None

    def fake_runner(**kwargs) -> InvestigationOutcome:
        log = EventLog(
            path=kwargs["run_directory"] / "events.jsonl", run_id=kwargs["run_id"]
        )
        log.append("hypothesis", {"text": "Test the equipment hypothesis."})
        log.append("tool_call", {"tool": "query_equipment_logs"})
        log.append("verifier", {"passed": True, "citation_count": 1})
        report = {
            "schema_version": "1.0",
            "incident_id": kwargs["incident_id"],
            "status": "concluded",
            "root_cause": {"text": "The new material lot is implicated.", "citations": []},
        }
        (kwargs["run_directory"] / "report.json").write_text(
            json.dumps(report), encoding="utf-8"
        )
        return InvestigationOutcome(
            run_id=kwargs["run_id"],
            attempts=1,
            report=None,
            verification=VerificationResult(True, (), 1),
            run_directory=kwargs["run_directory"],
        )

    monkeypatch.setattr(app_module.asyncio, "sleep", no_delay)
    database = tmp_path / "socket.db"
    coordinator = InvestigationCoordinator(
        database_path=database,
        runs_root=tmp_path / "runs",
        runner=fake_runner,
    )
    app = app_module.create_app(
        mode="live", data_path=database, coordinator=coordinator
    )

    with TestClient(app) as client:
        with client.websocket_connect("/ws/watch") as watch:
            watch.receive_json()
            streamed = [watch.receive_json() for _ in range(22)]
        assert streamed[-1]["incident"]["id"] == "incident-s1-001"
        coordinator.wait()

        response = client.get(
            "/api/investigations/incident-s1-001", params={"after": 2}
        )
        assert response.status_code == 200
        assert [event["sequence"] for event in response.json()["events"]] == [3, 4]
        assert response.json()["report"]["incident_id"] == "incident-s1-001"

        with client.websocket_connect(
            "/ws/investigate/incident-s1-001?after=2"
        ) as investigate:
            snapshot = investigate.receive_json()
        assert snapshot["type"] == "investigation_snapshot"
        assert [event["sequence"] for event in snapshot["events"]] == [3, 4]
        assert snapshot["report"]["status"] == "concluded"


def test_replay_api_changes_speed_and_approves_v2(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """The browser controls operate without credentials or a live investigator."""

    now = [100.0]
    monkeypatch.setattr(replay_module.time, "monotonic", lambda: now[0])
    coordinator = ReplayCoordinator(
        fixture_root=ROOT / "fixtures", scenario="scenario-2"
    )
    coordinator.submit("incident-s2-001")
    now[0] = 200.0
    app = app_module.create_app(
        mode="replay",
        scenario="scenario-2",
        data_path=tmp_path / "replay.db",
        coordinator=coordinator,
    )

    with TestClient(app) as client:
        speed = client.post("/api/replay/speed/4")
        approved = client.post(
            "/api/proposals/proposal-incident-s2-001-v1/approve"
        )

    assert speed.json()["speed"] == 4
    assert approved.json()["active_version_id"] == "ocap-trend-v2"
