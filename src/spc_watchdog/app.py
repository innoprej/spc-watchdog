"""FastAPI boundary for health, deterministic state, and the live chart stream."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .stream import SNAPSHOT_COUNT, build_stream_events
from .world import create_world, derive_control_limits, load_measurements

Mode = Literal["live", "replay"]
SIM_RATE_LABEL = "1 real second = 1 simulated hour"


def create_app(*, mode: Mode, data_path: Path) -> FastAPI:
    """Create an isolated application instance and rebuild its synthetic world."""

    summary = create_world(data_path)
    measurements = load_measurements(data_path)
    center, sigma = derive_control_limits(measurements)
    events = build_stream_events(measurements)
    app = FastAPI(title="SPC Watchdog", version="0.1.0")
    investigator_status = (
        "not required in deterministic replay"
        if mode == "replay"
        else (
            "Codex CLI detected; authentication is checked when an incident opens"
            if shutil.which("codex")
            else "unavailable: Codex CLI was not found on PATH"
        )
    )

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
                await websocket.send_json(event)
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
