"""Mount exact OCAP skill bytes through the shell-free MCP boundary."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SkillMount:
    """A content-addressed skill body safe to return as an MCP result."""

    id: str
    name: str
    signal_family: str
    version: int
    sha256: str
    body: str

    def as_tool_result(self) -> dict[str, str | int]:
        """Return the full body plus the digest used for feed verification."""

        return asdict(self)


def load_skill_mount(
    path: Path,
    *,
    skill_id: str,
    name: str,
    signal_family: str,
    version: int,
) -> SkillMount:
    """Read the installed SKILL.md and address the exact UTF-8 bytes by digest."""

    body = path.read_text(encoding="utf-8")
    if not body.startswith("---\n") or f"name: {name}\n" not in body:
        raise ValueError("OCAP skill metadata does not match the active version")
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return SkillMount(skill_id, name, signal_family, version, digest, body)


def build_skill_mount(
    body: str, *, skill_id: str, name: str, signal_family: str, version: int
) -> SkillMount:
    """Create a content-addressed mount from a version stored in SQLite."""

    if not body.startswith("---\n") or f"name: {name}\n" not in body:
        raise ValueError("stored OCAP skill metadata does not match the active version")
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return SkillMount(skill_id, name, signal_family, version, digest, body)
