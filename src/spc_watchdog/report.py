"""Validate structured investigation reports and re-check every cited value."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .broker import BrokerScopeError, InvestigationBroker
from .skill_mount import SkillMount


class Citation(BaseModel):
    """A row-level claim anchor emitted by the investigator."""

    model_config = ConfigDict(extra="forbid")

    id: str
    table: Literal[
        "incidents", "equipment_logs", "lot_genealogy", "incoming_inspection"
    ]
    field: str
    value: str | int | float | bool | None


class Claim(BaseModel):
    """One conclusion that is invalid without at least one citation."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    citations: list[Citation] = Field(min_length=1)


class SkillReference(BaseModel):
    """The exact OCAP bytes the model received through MCP."""

    model_config = ConfigDict(extra="forbid")

    id: str
    version: int = Field(ge=1)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class InvestigationReport(BaseModel):
    """The schema-constrained report accepted from Codex exec."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"]
    incident_id: str
    skill: SkillReference
    status: Literal["concluded", "insufficient-evidence"]
    claims: list[Claim] = Field(min_length=1)
    root_cause: Claim


@dataclass(frozen=True, slots=True)
class CitationFailure:
    """A deterministic reason a model-provided citation cannot be trusted."""

    claim_text: str
    citation: Citation
    reason: str


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """The gate result rendered by the product, never by the model."""

    passed: bool
    failures: tuple[CitationFailure, ...]
    citation_count: int


def _same_citation_value(canonical: object, cited: object) -> bool:
    """Compare exactly except for intentional int/float JSON normalization."""

    if isinstance(canonical, bool) or isinstance(cited, bool):
        return type(canonical) is type(cited) and canonical == cited
    if isinstance(canonical, (int, float)) and isinstance(cited, (int, float)):
        return float(canonical) == float(cited)
    return type(canonical) is type(cited) and canonical == cited


def parse_report_json(payload: str) -> InvestigationReport:
    """Parse JSON and reject any output outside the public report contract."""

    try:
        return InvestigationReport.model_validate_json(payload)
    except ValidationError as error:
        raise ValueError(f"invalid investigation report: {error}") from error


def verify_report(
    report: InvestigationReport,
    *,
    broker: InvestigationBroker,
    skill: SkillMount,
) -> VerificationResult:
    """Re-read all claimed row values and verify the mounted skill identity."""

    failures: list[CitationFailure] = []
    if report.incident_id != broker.scope.id:
        failures.append(
            CitationFailure(
                claim_text="Incident identity",
                citation=Citation(
                    id=report.incident_id,
                    table="incidents",
                    field="status",
                    value="incident-scope-mismatch",
                ),
                reason="report incident does not match the broker scope",
            )
        )
    references = (report.skill.id, report.skill.version, report.skill.sha256)
    expected = (skill.id, skill.version, skill.sha256)
    if references != expected:
        synthetic = Citation(
            id=report.incident_id,
            table="incidents",
            field="status",
            value="skill-reference-mismatch",
        )
        failures.append(
            CitationFailure(
                claim_text="OCAP skill identity",
                citation=synthetic,
                reason="report does not identify the exact skill body returned by MCP",
            )
        )

    claims = [*report.claims, report.root_cause]
    citation_count = 0
    for claim in claims:
        for citation in claim.citations:
            citation_count += 1
            try:
                canonical = broker.canonical_value(
                    table=citation.table,
                    row_id=citation.id,
                    field=citation.field,
                )
            except BrokerScopeError as error:
                failures.append(
                    CitationFailure(claim.text, citation, str(error))
                )
                continue
            if not _same_citation_value(canonical, citation.value):
                failures.append(
                    CitationFailure(
                        claim.text,
                        citation,
                        "cited value does not match the canonical row",
                    )
                )

    return VerificationResult(
        passed=not failures,
        failures=tuple(failures),
        citation_count=citation_count,
    )
