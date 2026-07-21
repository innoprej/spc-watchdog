"""Persist ordered, schema-versioned investigation activity for live resume."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .skill_mount import SkillMount

EVENT_SCHEMA_VERSION = "1.0"


def _contains_exact(value: Any, expected: str) -> bool:
    if value == expected:
        return True
    if isinstance(value, dict):
        return any(_contains_exact(child, expected) for child in value.values())
    if isinstance(value, list):
        return any(_contains_exact(child, expected) for child in value)
    return False


@dataclass(frozen=True, slots=True)
class RunEvent:
    """One normalized activity item delivered to the control room."""

    schema_version: str
    run_id: str
    sequence: int
    recorded_at: str
    type: str
    payload: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "sequence": self.sequence,
            "recorded_at": self.recorded_at,
            "type": self.type,
            "payload": self.payload,
        }


class EventLog:
    """Append-only JSONL with monotonic sequence numbers and resume reads."""

    def __init__(self, *, path: Path, run_id: str) -> None:
        self.path = path
        self.run_id = run_id
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._sequence = self._last_sequence()

    def _last_sequence(self) -> int:
        if not self.path.exists():
            return 0
        last = 0
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                last = int(json.loads(line)["sequence"])
        return last

    def append(self, event_type: str, payload: dict[str, Any]) -> RunEvent:
        """Durably append one event before returning it to WebSocket callers."""

        with self._lock:
            self._sequence += 1
            event = RunEvent(
                schema_version=EVENT_SCHEMA_VERSION,
                run_id=self.run_id,
                sequence=self._sequence,
                recorded_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                type=event_type,
                payload=payload,
            )
            with self.path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(event.as_dict(), separators=(",", ":")))
                stream.write("\n")
            return event

    def after(self, sequence: int) -> tuple[RunEvent, ...]:
        """Read a reconnect snapshot without duplicating acknowledged events."""

        events: list[RunEvent] = []
        if not self.path.exists():
            return ()
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            raw = json.loads(line)
            if int(raw["sequence"]) > sequence:
                events.append(RunEvent(**raw))
        return tuple(events)


def normalize_codex_event(
    raw: dict[str, Any], *, expected_skill: SkillMount
) -> tuple[tuple[str, dict[str, Any]], ...]:
    """Map Codex JSONL to UI activity and prove skill delivery before labeling it."""

    source_type = str(raw.get("type", "unknown"))
    item = raw.get("item")
    if not isinstance(item, dict):
        if source_type in {"thread.started", "turn.started", "turn.completed", "turn.failed"}:
            return (("status", {"source": source_type}),)
        return ()

    item_type = str(item.get("type", "unknown"))
    if item_type == "mcp_tool_call":
        tool = str(item.get("tool", item.get("name", "unknown")))
        if source_type == "item.started":
            return (
                (
                    "tool_call",
                    {"tool": tool, "arguments": item.get("arguments", {})},
                ),
            )
        if source_type == "item.completed":
            if tool == "load_ocap_skill":
                if (
                    not _contains_exact(item, expected_skill.sha256)
                    or not _contains_exact(item, expected_skill.body)
                ):
                    return (
                        (
                            "skill_load_rejected",
                            {
                                "skill_id": expected_skill.id,
                                "reason": "completed MCP result did not contain the exact skill body and digest",
                            },
                        ),
                    )
                return (
                    (
                        "skill_load",
                        {
                            "skill_id": expected_skill.id,
                            "name": expected_skill.name,
                            "version": expected_skill.version,
                            "sha256": expected_skill.sha256,
                            "delivery": "completed MCP result",
                        },
                    ),
                )
            return (
                (
                    "evidence",
                    {
                        "tool": tool,
                        "result": item.get("result"),
                        "status": item.get("status", "completed"),
                    },
                ),
            )

    if source_type == "item.completed" and item_type == "reasoning":
        text = item.get("text", item.get("summary", ""))
        return (("hypothesis", {"text": text}),) if text else ()
    if source_type == "item.completed" and item_type == "agent_message":
        text = item.get("text", "")
        return (("decision", {"text": text}),) if text else ()
    return ()
