"""Build the least-privilege Codex exec command for one investigator run."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping, Sequence

MODEL = "gpt-5.6-sol"
MCP_URL = "http://127.0.0.1:8765/mcp"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def build_investigation_prompt(*, contract_text: str, task_text: str) -> str:
    """Serialize public-safe runtime instructions without host-path metadata."""

    contract = contract_text.strip()
    task = task_text.strip()
    if not contract or not task:
        raise ValueError("investigation contract and task must both be non-empty")
    return (
        "<investigation_contract>\n"
        f"{contract}\n"
        "</investigation_contract>\n\n"
        "<investigation_task>\n"
        f"{task}\n"
        "</investigation_task>"
    )


def build_codex_exec_command(
    *,
    runtime_workspace: Path,
    output_schema: Path,
    output_last_message: Path,
    enabled_tools: Sequence[str],
    mcp_url: str = MCP_URL,
    codex_executable: str = "codex",
) -> list[str]:
    """Return a headless command isolated from permissive user sandbox settings.

    The investigator has no non-broker tool. The caller serializes the runtime
    contract into stdin because automatic project-doc and skill catalogs expose
    host paths; all factory interaction is limited to allowlisted MCP tools.
    """

    resolved_workspace = runtime_workspace.resolve()
    if resolved_workspace.is_relative_to(PROJECT_ROOT):
        raise ValueError("investigator runtime workspace must be outside the source repository")

    tools = ",".join(f'"{tool}"' for tool in enabled_tools)
    return [
        codex_executable,
        "-a",
        "never",
        "exec",
        "--ignore-user-config",
        "--strict-config",
        "--json",
        "--ephemeral",
        "--skip-git-repo-check",
        "--disable",
        "shell_tool",
        "--disable",
        "shell_snapshot",
        "--disable",
        "apps",
        "--disable",
        "remote_plugin",
        "--disable",
        "plugins",
        "--disable",
        "hooks",
        "--disable",
        "goals",
        "--disable",
        "multi_agent",
        "--disable",
        "unified_exec",
        "--disable",
        "browser_use",
        "--disable",
        "browser_use_external",
        "--disable",
        "browser_use_full_cdp_access",
        "--disable",
        "computer_use",
        "--disable",
        "image_generation",
        "--disable",
        "in_app_browser",
        "--disable",
        "plugin_sharing",
        "--disable",
        "skill_mcp_dependency_install",
        "--disable",
        "tool_call_mcp_elicitation",
        "--disable",
        "tool_suggest",
        "--disable",
        "workspace_dependencies",
        "--sandbox",
        "read-only",
        "--model",
        MODEL,
        "--cd",
        str(resolved_workspace),
        "-c",
        'web_search="disabled"',
        "-c",
        "include_environment_context=false",
        "-c",
        "project_doc_max_bytes=0",
        "-c",
        "skills.include_instructions=false",
        "-c",
        f'mcp_servers.spc_watchdog.url="{mcp_url}"',
        "-c",
        "mcp_servers.spc_watchdog.required=true",
        "-c",
        "mcp_servers.spc_watchdog.enabled=true",
        "-c",
        f"mcp_servers.spc_watchdog.enabled_tools=[{tools}]",
        "-c",
        'mcp_servers.spc_watchdog.default_tools_approval_mode="approve"',
        "-c",
        "mcp_servers.spc_watchdog.startup_timeout_sec=10",
        "-c",
        "mcp_servers.spc_watchdog.tool_timeout_sec=30",
        "--output-schema",
        str(output_schema),
        "--output-last-message",
        str(output_last_message),
        "-",
    ]


def build_codex_exec_environment(
    *,
    isolated_codex_home: Path,
    runtime_workspace: Path,
    base_environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Isolate Codex state and OS-home skill discovery from user customizations."""

    resolved_home = isolated_codex_home.resolve()
    if resolved_home.is_relative_to(PROJECT_ROOT):
        raise ValueError("isolated Codex home must be outside the source repository")
    if not resolved_home.is_dir():
        raise ValueError("isolated Codex home must already exist")
    resolved_workspace = runtime_workspace.resolve()
    if resolved_home == resolved_workspace or resolved_home.is_relative_to(resolved_workspace):
        raise ValueError("isolated Codex home must be outside the investigator workspace")
    if resolved_workspace.is_relative_to(PROJECT_ROOT):
        raise ValueError("investigator runtime workspace must be outside the source repository")
    os_home = resolved_workspace / ".home"
    os_home.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ if base_environment is None else base_environment)
    environment["CODEX_HOME"] = str(resolved_home)
    environment["HOME"] = str(os_home)
    environment["USERPROFILE"] = str(os_home)
    environment.pop("HOMEDRIVE", None)
    environment.pop("HOMEPATH", None)
    return environment
