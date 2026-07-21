"""Tests that prevent weakening the investigator's Codex boundary."""

from __future__ import annotations

from pathlib import Path

import pytest

from spc_watchdog.investigation_runtime import (
    build_codex_exec_command,
    build_codex_exec_environment,
    build_investigation_prompt,
)


def test_investigation_prompt_serializes_contract_without_runtime_path() -> None:
    prompt = build_investigation_prompt(
        contract_text="Use only registered evidence tools.",
        task_text="Investigate incident incident-s1-001.",
    )

    assert prompt == (
        "<investigation_contract>\n"
        "Use only registered evidence tools.\n"
        "</investigation_contract>\n\n"
        "<investigation_task>\n"
        "Investigate incident incident-s1-001.\n"
        "</investigation_task>"
    )
    assert str(Path.cwd()) not in prompt


def test_investigator_command_disables_every_non_broker_tool(
    tmp_path: Path,
) -> None:
    runtime_workspace = tmp_path / "runtime"
    command = build_codex_exec_command(
        runtime_workspace=runtime_workspace,
        output_schema=runtime_workspace / "report.schema.json",
        output_last_message=runtime_workspace / "report.json",
        enabled_tools=("query_probe",),
    )

    assert "--ignore-user-config" in command
    assert "--skip-git-repo-check" in command
    assert command[command.index("--sandbox") + 1] == "read-only"
    disabled_features = {
        command[index + 1]
        for index, argument in enumerate(command)
        if argument == "--disable"
    }
    assert disabled_features == {
        "apps",
        "browser_use",
        "browser_use_external",
        "browser_use_full_cdp_access",
        "computer_use",
        "goals",
        "hooks",
        "image_generation",
        "in_app_browser",
        "multi_agent",
        "plugin_sharing",
        "plugins",
        "remote_plugin",
        "shell_snapshot",
        "shell_tool",
        "skill_mcp_dependency_install",
        "tool_call_mcp_elicitation",
        "tool_suggest",
        "unified_exec",
        "workspace_dependencies",
    }
    assert 'web_search="disabled"' in command
    assert "include_environment_context=false" in command
    assert "project_doc_max_bytes=0" in command
    assert "skills.include_instructions=false" in command
    assert 'mcp_servers.spc_watchdog.enabled_tools=["query_probe"]' in command
    assert "mcp_servers.spc_watchdog.required=true" in command


def test_investigator_command_exposes_only_explicit_tool_allowlist(tmp_path: Path) -> None:
    runtime_workspace = tmp_path / "runtime"
    command = build_codex_exec_command(
        runtime_workspace=runtime_workspace,
        output_schema=runtime_workspace / "schema.json",
        output_last_message=runtime_workspace / "report.json",
        enabled_tools=("chart_context", "query_equipment_logs"),
    )

    allowlist = next(argument for argument in command if "enabled_tools=" in argument)
    assert allowlist == (
        'mcp_servers.spc_watchdog.enabled_tools=["chart_context",'
        '"query_equipment_logs"]'
    )


def test_investigator_command_rejects_runtime_inside_source_repository() -> None:
    runtime_workspace = Path("runs") / "unsafe-runtime"

    with pytest.raises(ValueError, match="outside the source repository"):
        build_codex_exec_command(
            runtime_workspace=runtime_workspace,
            output_schema=runtime_workspace / "schema.json",
            output_last_message=runtime_workspace / "report.json",
            enabled_tools=("query_probe",),
        )


def test_investigator_environment_uses_isolated_codex_home(tmp_path: Path) -> None:
    codex_home = tmp_path / "codex-home"
    runtime_workspace = tmp_path / "runtime"
    codex_home.mkdir()
    runtime_workspace.mkdir()

    environment = build_codex_exec_environment(
        isolated_codex_home=codex_home,
        runtime_workspace=runtime_workspace,
        base_environment={"PATH": "test-path"},
    )

    assert environment == {"PATH": "test-path", "CODEX_HOME": str(codex_home.resolve())}
