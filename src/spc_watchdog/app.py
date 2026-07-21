"""FastAPI boundary for health, deterministic state, and the live chart stream."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .broker import open_incident
from .investigation_queue import InvestigationCoordinator
from .stream import SNAPSHOT_COUNT, build_stream_events
from .world import create_world, derive_control_limits, load_measurements

Mode = Literal["live", "replay"]
SIM_RATE_LABEL = "1 real second = 1 simulated hour"


def create_app(
    *,
    mode: Mode,
    data_path: Path,
    run_directory: Path | None = None,
    coordinator: InvestigationCoordinator | None = None,
) -> FastAPI:
    """Create an isolated application instance and rebuild its synthetic world."""

    summary = create_world(data_path)
    measurements = load_measurements(data_path)
    center, sigma = derive_control_limits(measurements)
    events = build_stream_events(measurements)
    app = FastAPI(title="SPC Watchdog", version="0.1.0")
    owns_coordinator = mode == "live" and coordinator is None and run_directory is not None
    active_coordinator = coordinator
    if owns_coordinator:
        assert run_directory is not None
        active_coordinator = InvestigationCoordinator(
            database_path=data_path,
            runs_root=run_directory,
        )
    investigator_status = (
        "not required in deterministic replay"
        if mode == "replay"
        else (
            "Codex CLI detected; authentication is checked when an incident opens"
            if shutil.which("codex")
            else "unavailable: Codex CLI was not found on PATH"
        )
    )

    if owns_coordinator:
        @app.on_event("shutdown")
        async def close_investigator() -> None:
            assert active_coordinator is not None
            active_coordinator.close()

    @app.get("/api/health")
    async def health() -> dict[str, object]:
        return {
            "status": "ok",
            "mode": mode,
            "scenario": summary.scenario,
            "measurement_count": summary.measurement_count,
            "credentials_required": mode == "live",
            "investigator_status": investigator_status,
        }

    @app.get("/api/state")
    async def state() -> dict[str, object]:
        return {
            "schema_version": "1.0",
            "mode": mode,
            "scenario": summary.scenario,
            "sim_rate_label": SIM_RATE_LABEL,
            "center": center,
            "sigma": sigma,
            "investigator_status": investigator_status,
            "initial_events": events[:SNAPSHOT_COUNT],
        }

    @app.get("/api/investigations/{incident_id}")
    async def investigation_snapshot(
        incident_id: str, after: int = 0
    ) -> dict[str, object]:
        """Resume a run from a monotonic event cursor without duplicate activity."""

        if active_coordinator is None:
            raise HTTPException(status_code=404, detail="investigation is not available")
        try:
            return active_coordinator.snapshot(incident_id, after=max(after, 0))
        except KeyError as error:
            raise HTTPException(status_code=404, detail="incident run was not found") from error

    @app.websocket("/ws/watch")
    async def watch(websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send_json(
            {
                "schema_version": "1.0",
                "type": "snapshot",
                "mode": mode,
                "scenario": summary.scenario,
                "sim_rate_label": SIM_RATE_LABEL,
                "center": center,
                "sigma": sigma,
                "investigator_status": investigator_status,
                "events": events[:SNAPSHOT_COUNT],
            }
        )
        try:
            for event in events[SNAPSHOT_COUNT:]:
                await asyncio.sleep(1.0)
                incident = event.get("incident")
                if active_coordinator is not None and isinstance(incident, dict):
                    open_incident(
                        data_path,
                        incident_id=str(incident["id"]),
                        scenario=summary.scenario,
                        opened_sim_hour=int(incident["opened_sim_hour"]),
                        primary_rule=int(incident["primary_rule"]),
                    )
                    active_coordinator.submit(str(incident["id"]))
                await websocket.send_json(event)
            await websocket.close(code=1000)
        except WebSocketDisconnect:
            return

    @app.websocket("/ws/investigate/{incident_id}")
    async def investigate(
        websocket: WebSocket, incident_id: str, after: int = 0
    ) -> None:
        """Stream persisted activity, allowing a reconnect from the last seen sequence."""

        await websocket.accept()
        if active_coordinator is None:
            await websocket.send_json(
                {"type": "investigation_unavailable", "incident_id": incident_id}
            )
            await websocket.close(code=4404)
            return
        cursor = max(after, 0)
        try:
            snapshot = active_coordinator.snapshot(incident_id, after=cursor)
        except KeyError:
            await websocket.send_json(
                {"type": "investigation_not_found", "incident_id": incident_id}
            )
            await websocket.close(code=4404)
            return

        await websocket.send_json({"type": "investigation_snapshot", **snapshot})
        delivered = snapshot["events"]
        assert isinstance(delivered, list)
        if delivered:
            cursor = max(int(event["sequence"]) for event in delivered)
        if snapshot["status"] in {"completed", "inconclusive", "failed"}:
            await websocket.close(code=1000)
            return

        try:
            while True:
                await asyncio.sleep(0.2)
                update = active_coordinator.snapshot(incident_id, after=cursor)
                update_events = update["events"]
                assert isinstance(update_events, list)
                for event in update_events:
                    await websocket.send_json(
                        {
                            "type": "investigation_event",
                            "incident_id": incident_id,
                            "status": update["status"],
                            "event": event,
                        }
                    )
                    cursor = int(event["sequence"])
                if update["status"] in {"completed", "inconclusive", "failed"}:
                    await websocket.send_json(
                        {
                            "type": "investigation_finished",
                            "incident_id": incident_id,
                            "status": update["status"],
                            "report": update["report"],
                        }
                    )
                    await websocket.close(code=1000)
                    return
        except WebSocketDisconnect:
            return

    frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
    else:
        @app.get("/", response_class=HTMLResponse)
        async def frontend_missing() -> str:
            return (
                "<main><h1>SPC Watchdog backend is ready.</h1>"
                "<p>Build the frontend to open the control room.</p></main>"
            )

    return app
