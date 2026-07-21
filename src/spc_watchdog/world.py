"""Generate the deterministic synthetic factory and persist its queryable evidence."""

from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

SCENARIO_ID = "scenario-1"
SEED = 41021
CENTER = 10.0
SIGMA = 0.25
SIM_START = datetime(2026, 4, 6, 6, 0, tzinfo=timezone.utc)
GENERATED_START = datetime(2026, 7, 21, 0, 0, tzinfo=timezone.utc)


@dataclass(frozen=True, slots=True)
class Measurement:
    """One immutable measurement row from the simulated line."""

    id: str
    sequence: int
    sim_hour: int
    sim_timestamp: str
    value: float
    lot_id: str


@dataclass(frozen=True, slots=True)
class WorldSummary:
    """Stable facts returned after constructing a scenario database."""

    scenario: str
    seed: int
    measurement_count: int
    first_shift_hour: int
    new_lot_hour: int


SCHEMA = """
CREATE TABLE IF NOT EXISTS measurements (
    id TEXT PRIMARY KEY,
    scenario TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    sim_hour INTEGER NOT NULL,
    sim_timestamp TEXT NOT NULL,
    utc_generated_at TEXT NOT NULL,
    value REAL NOT NULL,
    lot_id TEXT NOT NULL,
    UNIQUE (scenario, sequence)
);
CREATE TABLE IF NOT EXISTS equipment_logs (
    id TEXT PRIMARY KEY,
    scenario TEXT NOT NULL,
    sim_hour INTEGER NOT NULL,
    equipment_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    status TEXT NOT NULL,
    detail TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS material_lots (
    id TEXT PRIMARY KEY,
    scenario TEXT NOT NULL,
    material_code TEXT NOT NULL,
    supplier_code TEXT NOT NULL,
    received_sim_hour INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS lot_genealogy (
    id TEXT PRIMARY KEY,
    scenario TEXT NOT NULL,
    line_id TEXT NOT NULL,
    lot_id TEXT NOT NULL,
    introduced_sim_hour INTEGER NOT NULL,
    retired_sim_hour INTEGER
);
CREATE TABLE IF NOT EXISTS incoming_inspection (
    id TEXT PRIMARY KEY,
    scenario TEXT NOT NULL,
    lot_id TEXT NOT NULL,
    characteristic TEXT NOT NULL,
    measured_value REAL NOT NULL,
    lower_limit REAL NOT NULL,
    upper_limit REAL NOT NULL,
    disposition TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS incidents (
    id TEXT PRIMARY KEY,
    scenario TEXT NOT NULL,
    opened_sim_hour INTEGER NOT NULL,
    primary_rule INTEGER NOT NULL,
    status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ocap_versions (
    id TEXT PRIMARY KEY,
    signal_family TEXT NOT NULL,
    version INTEGER NOT NULL,
    status TEXT NOT NULL,
    UNIQUE (signal_family, version)
);
CREATE TABLE IF NOT EXISTS change_proposals (
    id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    base_version_id TEXT NOT NULL,
    status TEXT NOT NULL,
    patch TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS event_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _iso_at(origin: datetime, hour: int) -> str:
    return (origin + timedelta(hours=hour)).isoformat().replace("+00:00", "Z")


def generate_measurements() -> tuple[Measurement, ...]:
    """Create AR(1) measurements plus the discoverable Scenario 1 lot shift."""

    rng = np.random.default_rng(SEED)
    phi = 0.42
    innovation_sigma = SIGMA * math.sqrt(1 - phi**2)
    residual = 0.0
    values: list[float] = []

    for hour in range(40):
        residual = phi * residual + float(rng.normal(0.0, innovation_sigma))
        residual = float(np.clip(residual, -2.4 * SIGMA, 2.4 * SIGMA))
        value = CENTER + residual

        # The scenario plant is deterministic: lot B begins at hour 24, and
        # its measurable process effect appears two hours later.
        if hour == 26:
            value = CENTER + 3.35 * SIGMA
        elif hour > 26:
            value = CENTER + max(0.22, min(0.88, 0.62 + residual))

        lot_id = "lot-s1-b" if hour >= 24 else "lot-s1-a"
        values.append(round(value, 4))

    return tuple(
        Measurement(
            id=f"measurement-s1-{hour:03d}",
            sequence=hour,
            sim_hour=hour,
            sim_timestamp=_iso_at(SIM_START, hour),
            value=value,
            lot_id="lot-s1-b" if hour >= 24 else "lot-s1-a",
        )
        for hour, value in enumerate(values)
    )


def create_world(path: Path) -> WorldSummary:
    """Replace generated state with the canonical fixed-seed Scenario 1 world."""

    path.parent.mkdir(parents=True, exist_ok=True)
    measurements = generate_measurements()
    with sqlite3.connect(path) as connection:
        connection.executescript(SCHEMA)
        # Scenario resets replace synthetic production state but intentionally
        # preserve approved OCAP versions and their proposal history.
        for table in (
            "measurements",
            "equipment_logs",
            "material_lots",
            "lot_genealogy",
            "incoming_inspection",
            "incidents",
        ):
            connection.execute(f"DELETE FROM {table} WHERE scenario = ?", (SCENARIO_ID,))
        connection.execute("DELETE FROM event_metadata")
        connection.executemany(
            """INSERT INTO measurements
               (id, scenario, sequence, sim_hour, sim_timestamp, utc_generated_at, value, lot_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    row.id,
                    SCENARIO_ID,
                    row.sequence,
                    row.sim_hour,
                    row.sim_timestamp,
                    _iso_at(GENERATED_START, row.sim_hour),
                    row.value,
                    row.lot_id,
                )
                for row in measurements
            ],
        )
        connection.executemany(
            "INSERT INTO equipment_logs VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "equipment-s1-001",
                    SCENARIO_ID,
                    18,
                    "press-07",
                    "preventive-check",
                    "pass",
                    "Pressure, alignment, and vibration checks within standard.",
                ),
                (
                    "equipment-s1-002",
                    SCENARIO_ID,
                    25,
                    "press-07",
                    "operator-check",
                    "pass",
                    "No alarm, adjustment, or unplanned stop recorded.",
                ),
            ],
        )
        connection.executemany(
            "INSERT INTO material_lots VALUES (?, ?, ?, ?, ?)",
            [
                ("lot-s1-a", SCENARIO_ID, "alloy-feedstock", "source-14", 0),
                ("lot-s1-b", SCENARIO_ID, "alloy-feedstock", "source-14", 22),
            ],
        )
        connection.executemany(
            "INSERT INTO lot_genealogy VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("genealogy-s1-001", SCENARIO_ID, "line-07", "lot-s1-a", 0, 24),
                ("genealogy-s1-002", SCENARIO_ID, "line-07", "lot-s1-b", 24, None),
            ],
        )
        connection.executemany(
            "INSERT INTO incoming_inspection VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("inspection-s1-001", SCENARIO_ID, "lot-s1-a", "hardness", 47.8, 44.0, 52.0, "accepted"),
                ("inspection-s1-002", SCENARIO_ID, "lot-s1-b", "hardness", 51.8, 44.0, 52.0, "accepted-marginal"),
            ],
        )
        connection.execute(
            "INSERT OR IGNORE INTO ocap_versions VALUES (?, ?, ?, ?)",
            ("ocap-mean-shift-v1", "mean-shift", 1, "active"),
        )
        metadata = {
            "schema_version": "1",
            "scenario": SCENARIO_ID,
            "seed": str(SEED),
            "center": str(CENTER),
            "sigma": str(SIGMA),
            "sim_rate": "1 real second = 1 simulated hour",
        }
        connection.executemany(
            "INSERT INTO event_metadata VALUES (?, ?)", metadata.items()
        )

    return WorldSummary(SCENARIO_ID, SEED, len(measurements), 26, 24)


def load_measurements(path: Path) -> tuple[Measurement, ...]:
    """Read the compact chart stream without leaking the database to an agent."""

    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            """SELECT id, sequence, sim_hour, sim_timestamp, value, lot_id
               FROM measurements ORDER BY sequence"""
        ).fetchall()
    return tuple(Measurement(*row) for row in rows)


def canonical_snapshot(path: Path) -> str:
    """Return stable generated facts for deterministic rebuild assertions."""

    measurements = load_measurements(path)
    payload = [
        {
            "id": row.id,
            "sequence": row.sequence,
            "sim_hour": row.sim_hour,
            "sim_timestamp": row.sim_timestamp,
            "value": row.value,
            "lot_id": row.lot_id,
        }
        for row in measurements
    ]
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)
