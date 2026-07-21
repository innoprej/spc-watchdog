"""Generate the deterministic synthetic factory and persist its queryable evidence."""

from __future__ import annotations

import json
import math
import sqlite3
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

SCENARIO_ID = "scenario-1"
SCENARIO_2_ID = "scenario-2"
SEED = 41021
CENTER = 10.0
SIGMA = 0.25
WARMUP_COUNT = 24
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
CREATE TABLE IF NOT EXISTS tool_life (
    id TEXT PRIMARY KEY,
    scenario TEXT NOT NULL,
    equipment_id TEXT NOT NULL,
    sim_hour INTEGER NOT NULL,
    cycle_count INTEGER NOT NULL,
    replacement_limit INTEGER NOT NULL,
    last_tool_change_hour INTEGER NOT NULL,
    status TEXT NOT NULL
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
    body TEXT NOT NULL,
    UNIQUE (signal_family, version)
);
CREATE TABLE IF NOT EXISTS change_proposals (
    id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    base_version_id TEXT NOT NULL,
    status TEXT NOT NULL,
    rationale TEXT NOT NULL DEFAULT '',
    evidence_json TEXT NOT NULL DEFAULT '[]',
    proposed_step TEXT NOT NULL DEFAULT '',
    patch TEXT NOT NULL,
    proposed_body TEXT NOT NULL DEFAULT '',
    approved_version_id TEXT
);
CREATE TABLE IF NOT EXISTS event_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _iso_at(origin: datetime, hour: int) -> str:
    return (origin + timedelta(hours=hour)).isoformat().replace("+00:00", "Z")


def generate_measurements(scenario: str = SCENARIO_ID) -> tuple[Measurement, ...]:
    """Create AR(1) measurements plus one deterministic discoverable cause."""

    if scenario not in {SCENARIO_ID, SCENARIO_2_ID}:
        raise ValueError(f"unknown scenario: {scenario}")
    seed = SEED
    rng = np.random.default_rng(seed)
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
        if scenario == SCENARIO_ID:
            if hour == 26:
                value = CENTER + 3.35 * SIGMA
            elif hour > 26:
                value = CENTER + max(0.22, min(0.88, 0.62 + residual))
        elif 24 <= hour <= 29:
            value = CENTER - 0.3 + (hour - 24) * 0.12

        values.append(round(value, 4))

    suffix = "s1" if scenario == SCENARIO_ID else "s2"
    return tuple(
        Measurement(
            id=f"measurement-{suffix}-{hour:03d}",
            sequence=hour,
            sim_hour=hour,
            sim_timestamp=_iso_at(SIM_START, hour),
            value=value,
            lot_id=(
                "lot-s1-b"
                if scenario == SCENARIO_ID and hour >= 24
                else "lot-s1-a" if scenario == SCENARIO_ID else "lot-s2-a"
            ),
        )
        for hour, value in enumerate(values)
    )


def derive_control_limits(
    measurements: tuple[Measurement, ...],
) -> tuple[float, float]:
    """Estimate center and sample sigma from the clean pre-lot warm-up window."""

    if len(measurements) < WARMUP_COUNT:
        raise ValueError(f"at least {WARMUP_COUNT} warm-up measurements are required")
    warmup = [row.value for row in measurements[:WARMUP_COUNT]]
    return statistics.fmean(warmup), statistics.stdev(warmup)


def create_world(path: Path, scenario: str = SCENARIO_ID) -> WorldSummary:
    """Replace one scenario while preserving approved OCAP versions and proposals."""

    path.parent.mkdir(parents=True, exist_ok=True)
    measurements = generate_measurements(scenario)
    derived_center, derived_sigma = derive_control_limits(measurements)
    with sqlite3.connect(path) as connection:
        connection.executescript(SCHEMA)
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(ocap_versions)")
        }
        if "body" not in columns:
            connection.execute(
                "ALTER TABLE ocap_versions ADD COLUMN body TEXT NOT NULL DEFAULT ''"
            )
        proposal_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(change_proposals)")
        }
        for name, declaration in (
            ("rationale", "TEXT NOT NULL DEFAULT ''"),
            ("evidence_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("proposed_step", "TEXT NOT NULL DEFAULT ''"),
            ("proposed_body", "TEXT NOT NULL DEFAULT ''"),
            ("approved_version_id", "TEXT"),
        ):
            if name not in proposal_columns:
                connection.execute(
                    f"ALTER TABLE change_proposals ADD COLUMN {name} {declaration}"
                )
        # Scenario resets replace synthetic production state but intentionally
        # preserve approved OCAP versions and their proposal history.
        for table in (
            "measurements",
            "equipment_logs",
            "material_lots",
            "lot_genealogy",
            "incoming_inspection",
            "tool_life",
            "incidents",
        ):
            connection.execute(f"DELETE FROM {table} WHERE scenario = ?", (scenario,))
        connection.execute("DELETE FROM event_metadata")
        connection.executemany(
            """INSERT INTO measurements
               (id, scenario, sequence, sim_hour, sim_timestamp, utc_generated_at, value, lot_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    row.id,
                    scenario,
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
        equipment_rows = (
            [
                ("equipment-s1-001", scenario, 18, "press-07", "preventive-check", "pass", "Pressure, alignment, and vibration checks within standard."),
                ("equipment-s1-002", scenario, 25, "press-07", "operator-check", "pass", "No alarm, adjustment, or unplanned stop recorded."),
            ]
            if scenario == SCENARIO_ID
            else [
                ("equipment-s2-001", scenario, 20, "press-07", "preventive-check", "pass", "Alignment, lubrication, and vibration checks within standard."),
                ("equipment-s2-002", scenario, 28, "press-07", "operator-check", "pass", "No alarm or adjustment recorded during the developing trend."),
            ]
        )
        connection.executemany(
            "INSERT INTO equipment_logs VALUES (?, ?, ?, ?, ?, ?, ?)",
            equipment_rows,
        )
        lots = (
            [("lot-s1-a", scenario, "alloy-feedstock", "source-14", 0), ("lot-s1-b", scenario, "alloy-feedstock", "source-14", 22)]
            if scenario == SCENARIO_ID
            else [("lot-s2-a", scenario, "alloy-feedstock", "source-14", 0)]
        )
        connection.executemany(
            "INSERT INTO material_lots VALUES (?, ?, ?, ?, ?)",
            lots,
        )
        genealogy = (
            [("genealogy-s1-001", scenario, "line-07", "lot-s1-a", 0, 24), ("genealogy-s1-002", scenario, "line-07", "lot-s1-b", 24, None)]
            if scenario == SCENARIO_ID
            else [("genealogy-s2-001", scenario, "line-07", "lot-s2-a", 0, None)]
        )
        connection.executemany(
            "INSERT INTO lot_genealogy VALUES (?, ?, ?, ?, ?, ?)",
            genealogy,
        )
        inspections = (
            [("inspection-s1-001", scenario, "lot-s1-a", "hardness", 47.8, 44.0, 52.0, "accepted"), ("inspection-s1-002", scenario, "lot-s1-b", "hardness", 51.8, 44.0, 52.0, "accepted-marginal")]
            if scenario == SCENARIO_ID
            else [("inspection-s2-001", scenario, "lot-s2-a", "hardness", 48.1, 44.0, 52.0, "accepted")]
        )
        connection.executemany(
            "INSERT INTO incoming_inspection VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            inspections,
        )
        if scenario == SCENARIO_2_ID:
            connection.executemany(
                "INSERT INTO tool_life VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    ("tool-life-s2-001", scenario, "press-07", 18, 8300, 10000, 0, "monitoring"),
                    ("tool-life-s2-002", scenario, "press-07", 29, 9980, 10000, 0, "replacement-due"),
                ],
            )
        skill_root = Path(__file__).resolve().parents[2] / "investigator" / "skills"
        defaults = [
            ("ocap-mean-shift-v1", "mean-shift", 1, "active", (skill_root / "mean-shift-ocap" / "SKILL.md").read_text(encoding="utf-8")),
            ("ocap-trend-v1", "trend", 1, "active", (skill_root / "trend-ocap" / "SKILL.md").read_text(encoding="utf-8")),
        ]
        connection.executemany(
            "INSERT OR IGNORE INTO ocap_versions VALUES (?, ?, ?, ?, ?)", defaults
        )
        for skill_id, _, _, _, body in defaults:
            connection.execute(
                "UPDATE ocap_versions SET body = ? WHERE id = ? AND body = ''",
                (body, skill_id),
            )
        metadata = {
            "schema_version": "1",
            "scenario": scenario,
            "seed": str(SEED),
            "center": str(derived_center),
            "sigma": str(derived_sigma),
            "sim_rate": "1 real second = 1 simulated hour",
        }
        connection.executemany(
            "INSERT INTO event_metadata VALUES (?, ?)", metadata.items()
        )

    return WorldSummary(
        scenario,
        SEED,
        len(measurements),
        26 if scenario == SCENARIO_ID else 29,
        24 if scenario == SCENARIO_ID else 0,
    )


def load_measurements(path: Path, scenario: str | None = None) -> tuple[Measurement, ...]:
    """Read the compact chart stream without leaking the database to an agent."""

    with sqlite3.connect(path) as connection:
        active_scenario = scenario or connection.execute(
            "SELECT value FROM event_metadata WHERE key = 'scenario'"
        ).fetchone()[0]
        rows = connection.execute(
            """SELECT id, sequence, sim_hour, sim_timestamp, value, lot_id
               FROM measurements WHERE scenario = ? ORDER BY sequence""",
            (active_scenario,),
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
