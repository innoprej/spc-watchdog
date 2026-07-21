"""API boundary tests for credential-free replay and explicit live readiness."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from spc_watchdog import app as app_module


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
    """Lock the dashboard contract from its 20-point snapshot through the red verdict."""

    async def no_delay(_: float) -> None:
        return None

    monkeypatch.setattr(app_module.asyncio, "sleep", no_delay)
    app = app_module.create_app(mode="replay", data_path=tmp_path / "socket.db")

    with TestClient(app) as client:
        with client.websocket_connect("/ws/watch") as websocket:
            snapshot = websocket.receive_json()
            assert snapshot["type"] == "snapshot"
            assert len(snapshot["events"]) == 20
            events = [websocket.receive_json() for _ in range(7)]

    verdict = events[-1]
    assert verdict["sequence"] == 26
    assert verdict["violations"][0]["rule"] == 1
    assert verdict["incident"]["id"] == "incident-s1-001"
