"""Tests for reproducible world data and discoverable Scenario 1 evidence."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from spc_watchdog.nelson import evaluate_series
from spc_watchdog.world import CENTER, SIGMA, canonical_snapshot, create_world, load_measurements


def test_scenario_1_rebuild_is_byte_stable_at_row_level(tmp_path: Path) -> None:
    first = tmp_path / "first.db"
    second = tmp_path / "second.db"
    create_world(first)
    create_world(second)
    assert canonical_snapshot(first) == canonical_snapshot(second)


def test_scenario_1_places_new_lot_two_hours_before_first_violation(tmp_path: Path) -> None:
    database = tmp_path / "scenario.db"
    summary = create_world(database)
    rows = load_measurements(database)
    violations = evaluate_series([row.value for row in rows], center=CENTER, sigma=SIGMA)
    first_violation_hour = rows[violations[0].end_index].sim_hour

    with sqlite3.connect(database) as connection:
        lot_hour = connection.execute(
            "SELECT introduced_sim_hour FROM lot_genealogy WHERE id = ?",
            ("genealogy-s1-002",),
        ).fetchone()[0]

    assert first_violation_hour == summary.first_shift_hour == 26
    assert lot_hour == summary.new_lot_hour == first_violation_hour - 2


def test_scenario_1_has_clean_equipment_and_marginal_new_lot_evidence(tmp_path: Path) -> None:
    database = tmp_path / "scenario.db"
    create_world(database)
    with sqlite3.connect(database) as connection:
        equipment_statuses = connection.execute(
            "SELECT status FROM equipment_logs ORDER BY id"
        ).fetchall()
        inspection = connection.execute(
            """SELECT id, disposition, measured_value, upper_limit
               FROM incoming_inspection WHERE lot_id = ?""",
            ("lot-s1-b",),
        ).fetchone()

    assert equipment_statuses == [("pass",), ("pass",)]
    assert inspection == ("inspection-s1-002", "accepted-marginal", 51.8, 52.0)

