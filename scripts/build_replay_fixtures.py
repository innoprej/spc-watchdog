"""Sanitize selected live-run artifacts into the committed replay contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from spc_watchdog.fixture_sanitizer import sanitize

SCHEMA_VERSION = "1.0"


def _copy_json(source: Path, target: Path) -> None:
    payload = sanitize(json.loads(source.read_text(encoding="utf-8")))
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _copy_jsonl(source: Path, target: Path) -> None:
    rows = [
        sanitize(json.loads(line))
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not rows or any(row.get("schema_version") != SCHEMA_VERSION for row in rows):
        raise ValueError(f"event log is not schema {SCHEMA_VERSION}: {source}")
    target.write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def _manifest(scenario: str) -> dict[str, Any]:
    if scenario == "scenario-1":
        return {
            "schema_version": SCHEMA_VERSION,
            "scenario": scenario,
            "incident_id": "incident-s1-001",
            "initial_phase": "investigation",
            "active_skill_version": 1,
            "phases": {
                "investigation": {
                    "event_log": "events.jsonl",
                    "report": "report.json",
                    "proposal": None,
                }
            },
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "scenario": scenario,
        "incident_id": "incident-s2-001",
        "initial_phase": "v1",
        "active_skill_version": 1,
        "phases": {
            "v1": {
                "event_log": "v1-events.jsonl",
                "report": "v1-report.json",
                "proposal": "proposal.json",
            },
            "v2": {
                "event_log": "v2-events.jsonl",
                "report": "v2-report.json",
                "proposal": None,
            },
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario-1-run", type=Path, required=True)
    parser.add_argument("--scenario-2-v1-run", type=Path, required=True)
    parser.add_argument("--scenario-2-v2-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("fixtures"))
    args = parser.parse_args()

    scenario_1 = args.output / "scenario-1"
    scenario_2 = args.output / "scenario-2"
    scenario_1.mkdir(parents=True, exist_ok=True)
    scenario_2.mkdir(parents=True, exist_ok=True)

    _copy_jsonl(args.scenario_1_run / "events.jsonl", scenario_1 / "events.jsonl")
    _copy_json(args.scenario_1_run / "report.json", scenario_1 / "report.json")
    _copy_jsonl(args.scenario_2_v1_run / "events.jsonl", scenario_2 / "v1-events.jsonl")
    _copy_json(args.scenario_2_v1_run / "report.json", scenario_2 / "v1-report.json")
    _copy_json(args.scenario_2_v1_run / "proposal.json", scenario_2 / "proposal.json")
    _copy_jsonl(args.scenario_2_v2_run / "events.jsonl", scenario_2 / "v2-events.jsonl")
    _copy_json(args.scenario_2_v2_run / "report.json", scenario_2 / "v2-report.json")

    for scenario, directory in (("scenario-1", scenario_1), ("scenario-2", scenario_2)):
        (directory / "manifest.json").write_text(
            json.dumps(_manifest(scenario), indent=2) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
