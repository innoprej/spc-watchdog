"""Publish the scoped broker and truthful OCAP loader as MCP tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .broker import InvestigationBroker
from .skill_mount import SkillMount

BROKER_TOOL_NAMES = (
    "load_ocap_skill",
    "chart_context",
    "query_equipment_logs",
    "query_material_lots",
    "query_incoming_inspection",
    "query_tool_life",
)


def create_broker_mcp(
    broker: InvestigationBroker,
    skill: SkillMount,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> FastMCP:
    """Build one stateless MCP server whose closure fixes the incident scope."""

    server = FastMCP(
        "SPC Watchdog investigation broker",
        instructions="Use only the incident-scoped tools advertised by this server.",
        host=host,
        port=port,
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
    )

    @server.tool(
        name="load_ocap_skill",
        description=(
            "Load the complete active OCAP SKILL.md body. Call this before any "
            "investigation query and follow the returned workflow."
        ),
        structured_output=True,
    )
    def load_ocap_skill(incident_id: str, signal_family: str) -> dict[str, object]:
        if incident_id != broker.scope.id:
            broker.chart_context(incident_id)
        if signal_family != skill.signal_family:
            raise ValueError(f"no active OCAP skill for {signal_family}")
        return skill.as_tool_result()

    @server.tool(structured_output=True)
    def chart_context(incident_id: str) -> list[dict[str, object]]:
        """Return the deterministic signal context for the active incident."""

        return broker.chart_context(incident_id)

    @server.tool(structured_output=True)
    def query_equipment_logs(incident_id: str) -> list[dict[str, object]]:
        """Return recent equipment evidence for the active incident."""

        return broker.query_equipment_logs(incident_id)

    @server.tool(structured_output=True)
    def query_material_lots(incident_id: str) -> list[dict[str, object]]:
        """Return material genealogy evidence near the active incident."""

        return broker.query_material_lots(incident_id)

    @server.tool(structured_output=True)
    def query_incoming_inspection(
        incident_id: str, lot_id: str
    ) -> list[dict[str, object]]:
        """Return incoming inspection evidence for an in-scope lot."""

        return broker.query_incoming_inspection(incident_id, lot_id)

    @server.tool(structured_output=True)
    def query_tool_life(incident_id: str) -> list[dict[str, object]]:
        """Return accumulated tool-cycle evidence for the active incident."""

        return broker.query_tool_life(incident_id)

    return server
