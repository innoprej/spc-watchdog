"""File, review, and atomically approve evidence-grounded OCAP changes."""

from __future__ import annotations

import difflib
import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path

from .report import InvestigationReport
from .skill_mount import SkillMount, build_skill_mount


@dataclass(frozen=True, slots=True)
class ProposalRecord:
    """A persisted human-review packet derived from one verified report."""

    id: str
    incident_id: str
    base_version_id: str
    status: str
    rationale: str
    evidence: list[dict[str, object]]
    proposed_step: str
    patch: str
    proposed_body: str
    approved_version_id: str | None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _skill_name(signal_family: str) -> str:
    return "trend-ocap" if signal_family == "trend" else "mean-shift-ocap"


def load_active_skill(database_path: Path, signal_family: str) -> SkillMount:
    """Load exactly one active immutable skill version from SQLite."""

    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            """SELECT id, version, body FROM ocap_versions
               WHERE signal_family = ? AND status = 'active'""",
            (signal_family,),
        ).fetchall()
    if len(rows) != 1:
        raise RuntimeError(f"expected one active {signal_family} OCAP, found {len(rows)}")
    skill_id, version, body = rows[0]
    return build_skill_mount(
        str(body),
        skill_id=str(skill_id),
        name=_skill_name(signal_family),
        signal_family=signal_family,
        version=int(version),
    )


def _proposed_body(base_body: str, proposed_step: str, *, next_version: int) -> str:
    """Promote body metadata and place the learned step after equipment review."""

    step = " ".join(proposed_step.split())
    if not step:
        raise ValueError("proposed step must not be empty")
    lines = base_body.splitlines()
    version_line = next(
        (index for index, line in enumerate(lines) if line.startswith("This is OCAP version ")),
        None,
    )
    if version_line is None:
        raise ValueError("OCAP body has no version declaration")
    declaration_suffix = lines[version_line].partition(" for ")[2]
    if not declaration_suffix:
        raise ValueError("OCAP version declaration has no family description")
    lines[version_line] = f"This is OCAP version {next_version} for {declaration_suffix}"
    insertion = next(
        (index + 1 for index, line in enumerate(lines) if line.startswith("2. ")),
        None,
    )
    if insertion is None:
        raise ValueError("OCAP body has no equipment-review step")
    lines.insert(insertion, f"   - Learned v{next_version} step: {step}")
    return "\n".join(lines) + "\n"


def _proposal_from_row(row: sqlite3.Row) -> ProposalRecord:
    return ProposalRecord(
        id=str(row["id"]),
        incident_id=str(row["incident_id"]),
        base_version_id=str(row["base_version_id"]),
        status=str(row["status"]),
        rationale=str(row["rationale"]),
        evidence=json.loads(row["evidence_json"]),
        proposed_step=str(row["proposed_step"]),
        patch=str(row["patch"]),
        proposed_body=str(row["proposed_body"]),
        approved_version_id=row["approved_version_id"],
    )


def get_proposal(database_path: Path, proposal_id: str) -> ProposalRecord:
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT * FROM change_proposals WHERE id = ?", (proposal_id,)
        ).fetchone()
    if row is None:
        raise KeyError(proposal_id)
    return _proposal_from_row(row)


def file_change_proposal(
    database_path: Path, report: InvestigationReport, skill: SkillMount
) -> ProposalRecord | None:
    """Create a stable diff only after report citations and skill identity pass."""

    candidate = report.skill_change_proposal
    if candidate is None:
        return None
    if candidate.base_version_id != skill.id:
        raise ValueError("proposal base version does not match the loaded skill")
    proposed_body = _proposed_body(
        skill.body, candidate.proposed_step, next_version=skill.version + 1
    )
    patch = "".join(
        difflib.unified_diff(
            skill.body.splitlines(keepends=True),
            proposed_body.splitlines(keepends=True),
            fromfile=f"{skill.name}/SKILL.md@v{skill.version}",
            tofile=f"{skill.name}/SKILL.md@v{skill.version + 1}",
        )
    )
    proposal_id = f"proposal-{report.incident_id}-v{skill.version}"
    evidence = [citation.model_dump() for citation in candidate.rationale.citations]
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """INSERT OR IGNORE INTO change_proposals
               (id, incident_id, base_version_id, status, rationale, evidence_json,
                proposed_step, patch, proposed_body, approved_version_id)
               VALUES (?, ?, ?, 'pending', ?, ?, ?, ?, ?, NULL)""",
            (
                proposal_id,
                report.incident_id,
                skill.id,
                candidate.rationale.text,
                json.dumps(evidence, separators=(",", ":")),
                candidate.proposed_step,
                patch,
                proposed_body,
            ),
        )
    return get_proposal(database_path, proposal_id)


def approve_proposal(database_path: Path, proposal_id: str) -> ProposalRecord:
    """Atomically supersede the base, create immutable v2, and close the proposal."""

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            """SELECT p.*, v.signal_family, v.version, v.status AS base_status
               FROM change_proposals p
               JOIN ocap_versions v ON v.id = p.base_version_id
               WHERE p.id = ?""",
            (proposal_id,),
        ).fetchone()
        if row is None:
            raise KeyError(proposal_id)
        if row["status"] != "pending" or row["base_status"] != "active":
            raise ValueError("proposal is not pending against the active version")
        next_version = int(row["version"]) + 1
        next_id = f"ocap-{row['signal_family']}-v{next_version}"
        connection.execute(
            "UPDATE ocap_versions SET status = 'superseded' WHERE id = ?",
            (row["base_version_id"],),
        )
        connection.execute(
            """INSERT INTO ocap_versions (id, signal_family, version, status, body)
               VALUES (?, ?, ?, 'active', ?)""",
            (next_id, row["signal_family"], next_version, row["proposed_body"]),
        )
        connection.execute(
            """UPDATE change_proposals
               SET status = 'approved', approved_version_id = ? WHERE id = ?""",
            (next_id, proposal_id),
        )
        connection.commit()
    finally:
        connection.close()
    return get_proposal(database_path, proposal_id)


def reject_proposal(database_path: Path, proposal_id: str) -> ProposalRecord:
    """Reject without changing any OCAP version."""

    with sqlite3.connect(database_path) as connection:
        cursor = connection.execute(
            """UPDATE change_proposals SET status = 'rejected'
               WHERE id = ? AND status = 'pending'""",
            (proposal_id,),
        )
        if cursor.rowcount != 1:
            raise ValueError("proposal is not pending")
    return get_proposal(database_path, proposal_id)
