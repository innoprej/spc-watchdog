"""Run one queued Codex investigator against the allowlisted MCP broker."""

from __future__ import annotations

import json
import os
import queue
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import uvicorn

from .broker import InvestigationBroker
from .broker_mcp import BROKER_TOOL_NAMES, create_broker_mcp
from .event_log import EventLog, normalize_codex_event
from .investigation_runtime import (
    PROJECT_ROOT,
    build_codex_exec_command,
    build_codex_exec_environment,
    build_investigation_prompt,
)
from .report import InvestigationReport, VerificationResult, parse_report_json, verify_report
from .skill_mount import SkillMount, load_skill_mount

INVESTIGATOR_TEMPLATE = PROJECT_ROOT / "investigator"
CODEX_ATTEMPT_TIMEOUT_SECONDS = 180.0


@dataclass(frozen=True, slots=True)
class InvestigationOutcome:
    """The host-owned result of one live investigation."""

    run_id: str
    attempts: int
    report: InvestigationReport | None
    verification: VerificationResult | None
    run_directory: Path


def _available_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _resolve_codex_executable() -> str:
    """Prefer the native Windows binary over npm PowerShell/cmd shims."""

    if os.name == "nt":
        npm_shim = shutil.which("codex.cmd")
        if npm_shim:
            package_node_modules = (
                Path(npm_shim).parent
                / "node_modules"
                / "@openai"
                / "codex"
                / "node_modules"
            )
            native_binaries = sorted(
                package_node_modules.glob(
                    "@openai/codex-win32-*/vendor/*/bin/codex.exe"
                )
            )
            if native_binaries:
                return str(native_binaries[0])
    candidates = ("codex.exe", "codex") if os.name == "nt" else ("codex",)
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise RuntimeError("Codex CLI was not found on PATH")


def _install_runtime_template(runtime_workspace: Path) -> SkillMount:
    """Copy only public-safe contract assets into the disposable workspace."""

    runtime_workspace.mkdir(parents=True)
    shutil.copy2(INVESTIGATOR_TEMPLATE / "AGENTS.md", runtime_workspace / "AGENTS.md")
    shutil.copy2(
        INVESTIGATOR_TEMPLATE / "report.schema.json",
        runtime_workspace / "report.schema.json",
    )
    skill_directory = runtime_workspace / ".agents" / "skills" / "mean-shift-ocap"
    skill_directory.mkdir(parents=True)
    shutil.copy2(
        INVESTIGATOR_TEMPLATE / "skills" / "mean-shift-ocap" / "SKILL.md",
        skill_directory / "SKILL.md",
    )
    return load_skill_mount(
        skill_directory / "SKILL.md",
        skill_id="ocap-mean-shift-v1",
        name="mean-shift-ocap",
        signal_family="mean-shift",
        version=1,
    )


def _install_credential_only_codex_home(source: Path, destination: Path) -> None:
    """Copy only saved CLI authentication into a disposable Codex home."""

    auth = source / "auth.json"
    if not auth.is_file():
        raise RuntimeError("Codex CLI authentication was not found; run `codex login` first.")
    destination.mkdir(parents=True)
    shutil.copy2(auth, destination / "auth.json")


class _BrokerService:
    """Own the loopback MCP server lifetime for exactly one run."""

    def __init__(
        self, broker: InvestigationBroker, skill: SkillMount, *, port: int
    ) -> None:
        app = create_broker_mcp(broker, skill, port=port).streamable_http_app()
        self._server = uvicorn.Server(
            uvicorn.Config(
                app,
                host="127.0.0.1",
                port=port,
                log_level="warning",
            )
        )
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    def __enter__(self) -> _BrokerService:
        self._thread.start()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if self._server.started:
                return self
            if not self._thread.is_alive():
                break
            time.sleep(0.05)
        raise RuntimeError("investigation broker did not become healthy")

    def __exit__(self, *args: object) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=5)


def _drain_stderr(stream: Any, sink: list[str]) -> None:
    for line in stream:
        sink.append(line)


def _drain_stdout(stream: Any, sink: queue.Queue[str | None]) -> None:
    try:
        for line in stream:
            sink.put(line)
    finally:
        sink.put(None)


def _stop_process(process: subprocess.Popen[str]) -> None:
    """Bound shutdown even when a child ignores the first termination request."""

    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _run_attempt(
    *,
    attempt: int,
    runtime_workspace: Path,
    codex_home: Path,
    mcp_url: str,
    incident_id: str,
    skill: SkillMount,
    event_log: EventLog,
    raw_event_path: Path,
    retry_feedback: str | None,
    codex_executable: str,
    attempt_timeout_seconds: float = CODEX_ATTEMPT_TIMEOUT_SECONDS,
) -> tuple[int, str]:
    output_path = runtime_workspace / f"report-attempt-{attempt}.json"
    contract = (runtime_workspace / "AGENTS.md").read_text(encoding="utf-8")
    task = (
        f"Investigate {incident_id}. First call load_ocap_skill for signal family "
        "mean-shift, then follow the complete returned body. Use the registered "
        "tools to eliminate or implicate hypotheses and return the cited report."
    )
    if retry_feedback:
        task += (
            "\n\nThe deterministic verifier rejected the previous report. Correct every "
            f"listed failure and re-query evidence as needed:\n{retry_feedback}"
        )
    prompt = build_investigation_prompt(contract_text=contract, task_text=task)
    command = build_codex_exec_command(
        runtime_workspace=runtime_workspace,
        output_schema=runtime_workspace / "report.schema.json",
        output_last_message=output_path,
        enabled_tools=BROKER_TOOL_NAMES,
        mcp_url=mcp_url,
        codex_executable=codex_executable,
    )
    environment = build_codex_exec_environment(
        isolated_codex_home=codex_home,
        runtime_workspace=runtime_workspace,
    )
    event_log.append("status", {"state": "attempt_started", "attempt": attempt})
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    assert process.stderr is not None
    process.stdin.write(prompt)
    process.stdin.close()
    stderr_lines: list[str] = []
    stderr_thread = threading.Thread(
        target=_drain_stderr, args=(process.stderr, stderr_lines), daemon=True
    )
    stderr_thread.start()
    stdout_lines: queue.Queue[str | None] = queue.Queue()
    stdout_thread = threading.Thread(
        target=_drain_stdout, args=(process.stdout, stdout_lines), daemon=True
    )
    stdout_thread.start()

    deadline = time.monotonic() + attempt_timeout_seconds
    timed_out = False
    with raw_event_path.open("a", encoding="utf-8", newline="\n") as raw_stream:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            try:
                line = stdout_lines.get(timeout=min(0.25, remaining))
            except queue.Empty:
                continue
            if line is None:
                break
            raw_stream.write(line)
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                event_log.append(
                    "runtime_error",
                    {"attempt": attempt, "reason": "non-JSON stdout from codex exec"},
                )
                continue
            for event_type, payload in normalize_codex_event(
                raw, expected_skill=skill
            ):
                event_log.append(event_type, {"attempt": attempt, **payload})

    if timed_out:
        _stop_process(process)
        stdout_thread.join(timeout=5)
        stderr_thread.join(timeout=5)
        event_log.append(
            "runtime_error",
            {
                "attempt": attempt,
                "return_code": 124,
                "reason": f"codex exec exceeded {attempt_timeout_seconds:g} seconds",
            },
        )
        return 124, ""

    try:
        return_code = process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        _stop_process(process)
        stdout_thread.join(timeout=5)
        stderr_thread.join(timeout=5)
        event_log.append(
            "runtime_error",
            {
                "attempt": attempt,
                "return_code": 124,
                "reason": "codex exec did not exit after closing its event stream",
            },
        )
        return 124, ""
    stdout_thread.join(timeout=5)
    stderr_thread.join(timeout=5)
    if return_code != 0:
        tail = "".join(stderr_lines)[-2000:]
        event_log.append(
            "runtime_error",
            {"attempt": attempt, "return_code": return_code, "stderr_tail": tail},
        )
        return return_code, ""
    payload = output_path.read_text(encoding="utf-8")
    event_log.append("status", {"state": "attempt_completed", "attempt": attempt})
    return 0, payload


def _verification_feedback(result: VerificationResult) -> str:
    """Identify rejected citations without leaking canonical database values."""

    return "\n".join(
        f"- {failure.citation.table}/{failure.citation.id}."
        f"{failure.citation.field}: citation did not verify; re-query it through "
        "the registered broker tool"
        for failure in result.failures
    )


def run_live_investigation(
    *,
    database_path: Path,
    incident_id: str,
    run_directory: Path,
    run_id: str = "run-s1-001",
    user_codex_home: Path | None = None,
) -> InvestigationOutcome:
    """Run Codex, verify its citations, and allow one verifier-informed retry."""

    codex_executable = _resolve_codex_executable()
    run_directory.mkdir(parents=True, exist_ok=True)
    event_log = EventLog(path=run_directory / "events.jsonl", run_id=run_id)
    raw_event_path = run_directory / "codex-events.raw.jsonl"
    broker = InvestigationBroker(database_path=database_path, incident_id=incident_id)
    source_codex_home = user_codex_home or Path(
        os.environ.get("CODEX_HOME", Path.home() / ".codex")
    )
    last_report: InvestigationReport | None = None
    last_verification: VerificationResult | None = None

    with tempfile.TemporaryDirectory(prefix="spc-watchdog-investigator-") as temp:
        temp_root = Path(temp)
        runtime_workspace = temp_root / "runtime"
        codex_home = temp_root / "codex-home"
        skill = _install_runtime_template(runtime_workspace)
        _install_credential_only_codex_home(source_codex_home, codex_home)
        port = _available_port()
        mcp_url = f"http://127.0.0.1:{port}/mcp"
        event_log.append(
            "status",
            {
                "state": "run_started",
                "incident_id": incident_id,
                "model": "gpt-5.6-sol",
                "sandbox": "read-only",
            },
        )
        with _BrokerService(broker, skill, port=port):
            feedback: str | None = None
            for attempt in (1, 2):
                return_code, payload = _run_attempt(
                    attempt=attempt,
                    runtime_workspace=runtime_workspace,
                    codex_home=codex_home,
                    mcp_url=mcp_url,
                    incident_id=incident_id,
                    skill=skill,
                    event_log=event_log,
                    raw_event_path=raw_event_path,
                    retry_feedback=feedback,
                    codex_executable=codex_executable,
                )
                if return_code != 0:
                    return InvestigationOutcome(
                        run_id, attempt, last_report, last_verification, run_directory
                    )
                try:
                    last_report = parse_report_json(payload)
                except ValueError as error:
                    event_log.append(
                        "verifier",
                        {"attempt": attempt, "passed": False, "reason": str(error)},
                    )
                    feedback = str(error)
                    continue
                last_verification = verify_report(
                    last_report, broker=broker, skill=skill
                )
                event_log.append(
                    "verifier",
                    {
                        "attempt": attempt,
                        "passed": last_verification.passed,
                        "citation_count": last_verification.citation_count,
                        "failures": [
                            {
                                "claim": failure.claim_text,
                                "citation": failure.citation.model_dump(),
                                "reason": failure.reason,
                            }
                            for failure in last_verification.failures
                        ],
                    },
                )
                if last_verification.passed:
                    (run_directory / "report.json").write_text(
                        last_report.model_dump_json(indent=2), encoding="utf-8"
                    )
                    event_log.append(
                        "status",
                        {
                            "state": (
                                "run_completed"
                                if last_report.status == "concluded"
                                else "run_inconclusive"
                            ),
                            "attempt": attempt,
                        },
                    )
                    return InvestigationOutcome(
                        run_id, attempt, last_report, last_verification, run_directory
                    )
                feedback = _verification_feedback(last_verification)

    event_log.append(
        "status", {"state": "run_failed", "reason": "verification exhausted"}
    )
    return InvestigationOutcome(
        run_id, 2, last_report, last_verification, run_directory
    )
