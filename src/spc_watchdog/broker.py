"""Expose incident-scoped, fixed-shape factory evidence to investigators."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class BrokerScopeError(ValueError):
    """Raised when a tool request falls outside the active incident."""


@dataclass(frozen=True, slots=True)
class IncidentScope:
    """The immutable query boundary for one investigation."""

    id: str
    scenario: str
    opened_sim_hour: int
    primary_rule: int


class InvestigationBroker:
    """Own every SQL statement that can reach the synthetic factory database."""

    _CITABLE_FIELDS: dict[str, frozenset[str]] = {
        "equipment_logs": frozenset(
            {"sim_hour", "equipment_id", "event_type", "status", "detail"}
        ),
        "lot_genealogy": frozenset(
            {"line_id", "lot_id", "introduced_sim_hour", "retired_sim_hour"}
        ),
        "incoming_inspection": frozenset(
            {
                "lot_id",
                "characteristic",
                "measured_value",
                "lower_limit",
                "upper_limit",
                "disposition",
            }
        ),
        "incidents": frozenset(
            {"scenario", "opened_sim_hour", "primary_rule", "status"}
        ),
        "tool_life": frozenset(
            {
                "equipment_id",
                "sim_hour",
                "cycle_count",
                "replacement_limit",
                "last_tool_change_hour",
                "status",
            }
        ),
    }

    def __init__(self, *, database_path: Path, incident_id: str) -> None:
        self._database_path = database_path.resolve()
        self._scope = self._load_scope(incident_id)

    @property
    def scope(self) -> IncidentScope:
        """Return the incident whose evidence this broker may expose."""

        return self._scope

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _load_scope(self, incident_id: str) -> IncidentScope:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT id, scenario, opened_sim_hour, primary_rule
                   FROM incidents WHERE id = ?""",
                (incident_id,),
            ).fetchone()
        if row is None:
            raise BrokerScopeError(f"unknown incident: {incident_id}")
        return IncidentScope(
            id=str(row["id"]),
            scenario=str(row["scenario"]),
            opened_sim_hour=int(row["opened_sim_hour"]),
            primary_rule=int(row["primary_rule"]),
        )

    def _require_incident(self, incident_id: str) -> None:
        if incident_id != self._scope.id:
            raise BrokerScopeError(
                f"broker is scoped to {self._scope.id}, not {incident_id}"
            )

    @staticmethod
    def _compact_rows(rows: list[sqlite3.Row], table: str) -> list[dict[str, Any]]:
        return [{"table": table, **dict(row)} for row in rows]

    def chart_context(self, incident_id: str) -> list[dict[str, Any]]:
        """Return the deterministic signal context for the active incident."""

        self._require_incident(incident_id)
        with self._connect() as connection:
            row = connection.execute(
                """SELECT id, scenario, opened_sim_hour, primary_rule, status
                   FROM incidents WHERE id = ?""",
                (incident_id,),
            ).fetchone()
        return self._compact_rows([row], "incidents")

    def query_equipment_logs(self, incident_id: str) -> list[dict[str, Any]]:
        """Return recent equipment records in a fixed twelve-hour lookback."""

        self._require_incident(incident_id)
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT id, sim_hour, equipment_id, event_type, status, detail
                   FROM equipment_logs
                   WHERE scenario = ? AND sim_hour BETWEEN ? AND ?
                   ORDER BY sim_hour, id""",
                (
                    self._scope.scenario,
                    self._scope.opened_sim_hour - 12,
                    self._scope.opened_sim_hour,
                ),
            ).fetchall()
        return self._compact_rows(rows, "equipment_logs")

    def query_material_lots(self, incident_id: str) -> list[dict[str, Any]]:
        """Return lot transitions near the incident without exposing arbitrary SQL."""

        self._require_incident(incident_id)
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT id, line_id, lot_id, introduced_sim_hour, retired_sim_hour
                   FROM lot_genealogy
                   WHERE scenario = ?
                     AND introduced_sim_hour <= ?
                     AND (retired_sim_hour IS NULL OR retired_sim_hour >= ?)
                   ORDER BY introduced_sim_hour, id""",
                (
                    self._scope.scenario,
                    self._scope.opened_sim_hour,
                    self._scope.opened_sim_hour - 12,
                ),
            ).fetchall()
        return self._compact_rows(rows, "lot_genealogy")

    def query_incoming_inspection(
        self, incident_id: str, lot_id: str
    ) -> list[dict[str, Any]]:
        """Return inspection rows only for lots in this incident's genealogy."""

        self._require_incident(incident_id)
        with self._connect() as connection:
            allowed = connection.execute(
                """SELECT 1 FROM lot_genealogy
                   WHERE scenario = ? AND lot_id = ? AND introduced_sim_hour <= ?""",
                (self._scope.scenario, lot_id, self._scope.opened_sim_hour),
            ).fetchone()
            if allowed is None:
                raise BrokerScopeError(f"lot is outside incident genealogy: {lot_id}")
            rows = connection.execute(
                """SELECT id, lot_id, characteristic, measured_value,
                          lower_limit, upper_limit, disposition
                   FROM incoming_inspection
                   WHERE scenario = ? AND lot_id = ?
                   ORDER BY id""",
                (self._scope.scenario, lot_id),
            ).fetchall()
        return self._compact_rows(rows, "incoming_inspection")

    def query_tool_life(self, incident_id: str) -> list[dict[str, Any]]:
        """Return accumulated tool cycles at or before the active incident."""

        self._require_incident(incident_id)
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT id, equipment_id, sim_hour, cycle_count,
                          replacement_limit, last_tool_change_hour, status
                   FROM tool_life
                   WHERE scenario = ? AND sim_hour <= ?
                   ORDER BY sim_hour, id""",
                (self._scope.scenario, self._scope.opened_sim_hour),
            ).fetchall()
        return self._compact_rows(rows, "tool_life")

    def canonical_value(self, *, table: str, row_id: str, field: str) -> Any:
        """Resolve one citation through an allowlisted table and field."""

        allowed_fields = self._CITABLE_FIELDS.get(table)
        if allowed_fields is None or field not in allowed_fields:
            raise BrokerScopeError(f"field is not citable: {table}.{field}")
        visible_ids: set[str]
        if table == "incidents":
            visible_ids = {self._scope.id}
        elif table == "equipment_logs":
            visible_ids = {
                str(row["id"])
                for row in self.query_equipment_logs(self._scope.id)
            }
        elif table == "lot_genealogy":
            visible_ids = {
                str(row["id"])
                for row in self.query_material_lots(self._scope.id)
            }
        elif table == "tool_life":
            visible_ids = {
                str(row["id"])
                for row in self.query_tool_life(self._scope.id)
            }
        else:
            genealogy = self.query_material_lots(self._scope.id)
            visible_ids = {
                str(row["id"])
                for lot_id in {str(row["lot_id"]) for row in genealogy}
                for row in self.query_incoming_inspection(self._scope.id, lot_id)
            }
        if row_id not in visible_ids:
            raise BrokerScopeError(f"row is outside incident evidence: {table}/{row_id}")
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT scenario, {field} FROM {table} WHERE id = ?",
                (row_id,),
            ).fetchone()
        if row is None or row["scenario"] != self._scope.scenario:
            raise BrokerScopeError(f"row is outside incident scenario: {table}/{row_id}")
        return row[field]


def open_incident(
    database_path: Path,
    *,
    incident_id: str,
    scenario: str,
    opened_sim_hour: int,
    primary_rule: int,
) -> None:
    """Persist the deterministic WATCH handoff before starting INVESTIGATE."""

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """INSERT INTO incidents
               (id, scenario, opened_sim_hour, primary_rule, status)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET status = excluded.status""",
            (incident_id, scenario, opened_sim_hour, primary_rule, "investigating"),
        )
