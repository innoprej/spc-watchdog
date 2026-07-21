# Codex Exec Runtime Spike

## Verdict

**BLOCKED — registered CLI tool execution failed a hard gate on Windows. Phase 1 stopped before application scaffolding or fallback work.**

The spike used Codex CLI `0.144.6`, ChatGPT-managed authentication, and the `gpt-5.6-sol` model slug. Machine-readable events and schema-constrained final output worked. A registered tool could not start inside either the `read-only` or `workspace-write` sandbox, even though the same tools executed successfully from the host shell.

## Official contract checked

| Concern | Current official contract | Source |
| --- | --- | --- |
| Non-interactive execution | `codex exec` is the supported non-interactive command. | [Codex CLI command reference](https://learn.chatgpt.com/docs/developer-commands.md?surface=cli#cli-codex-exec) |
| Model selection | `-m` / `--model` overrides the configured model for an invocation. | [Codex models](https://learn.chatgpt.com/docs/models.md) |
| Working directory | `-C` / `--cd` sets the agent working directory before processing the request. | [Codex CLI command reference](https://learn.chatgpt.com/docs/developer-commands.md?surface=cli) |
| Sandbox | `read-only`, `workspace-write`, and `danger-full-access` are documented modes; automation should use the least permission that works. | [Codex CLI command reference](https://learn.chatgpt.com/docs/developer-commands.md?surface=cli#cli-codex-exec) |
| Event stream | `--json` emits JSONL events including thread/turn lifecycle and `item.*` events for reasoning, commands, file changes, MCP calls, web searches, and plans. | [Codex non-interactive mode](https://learn.chatgpt.com/docs/developer-commands.md?surface=cli#cli-codex-exec) |
| Structured final output | `--output-schema` constrains the final response to a JSON Schema; `-o` writes the final message. | [Codex non-interactive mode](https://learn.chatgpt.com/docs/developer-commands.md?surface=cli#cli-codex-exec) |
| Authentication and billing | `codex exec` reuses saved CLI authentication. ChatGPT plans use Codex usage and credits; API-key runs use API token billing. | [Codex pricing](https://learn.chatgpt.com/docs/pricing.md), [Codex authentication](https://learn.chatgpt.com/docs/auth) |

The CLI does not expose a per-run currency charge in its JSONL stream, so this project can truthfully state that the observed run used ChatGPT-managed Codex authentication and reported token usage, but not a precise credit charge.

## Local evidence

| Gate | Result | Evidence |
| --- | --- | --- |
| Project-local skill discovery | PASS | `codex debug prompt-input` listed `judge-panel-review` from the repository's `.codex/skills` root. |
| Authentication | PASS | `codex login status` reported ChatGPT-managed login. No API-key environment variable was supplied. |
| Model availability | PASS | The local model catalog listed `gpt-5.6-sol` as GPT-5.6 Sol, and the exec invocation accepted `-m gpt-5.6-sol`. |
| JSONL parsing | PASS | The probe parsed JSON objects and observed one `command_execution` item rather than scraping terminal prose. |
| Structured final output | PASS | All three attempts produced schema-valid JSON with exactly `claim` and `citation_id`. |
| Working-directory contract | PASS | The agent loaded the disposable runtime contract and attempted the relative registered-tool path. |
| Registered tool in `read-only` | FAIL | The `.cmd` probe returned `access denied while spawning the sandboxed process`. |
| Registered tool in `workspace-write` | FAIL | Both `.cmd` and in-workspace `.ps1` probes reported that sandboxed process creation was denied. |
| Tool validity outside sandbox | PASS | Both probe tools printed the expected stable evidence row when invoked directly from the host shell. |

The disposable probe returned this row outside Codex:

```json
{"id":"probe-row-001","table":"probe_evidence","field":"status","value":"tool-access-confirmed"}
```

The schema-valid Codex failure reports were:

```json
{"claim":"query-probe.cmd failed before returning a row: access denied while spawning the sandboxed process.","citation_id":""}
{"claim":"query-probe.cmd could not be executed because the sandbox denied process creation; no JSON row was returned.","citation_id":""}
{"claim":"query-probe.ps1 could not start because the sandbox denied process creation; no evidence row was returned.","citation_id":""}
```

No raw run log is committed. This note contains no absolute paths, usernames, or credentials.

## Hard-gate assessment

The default architecture requires a Codex investigator to call registered CLI tools inside a constrained runtime workspace. Because both safe sandbox modes denied those tool processes on the development machine, the primary exec path does not currently meet its tool-access hard gate.

No direct GPT-5.6 API fallback, `danger-full-access` run, MCP replacement, WSL/container workaround, backend scaffold, or frontend scaffold was started after the failure.

## Decision required

1. **Fastest demo path:** permit `danger-full-access` for the synthetic live run while retaining a database-free runtime workspace and backend query broker; keep replay credential-free and safe.
2. **Stronger boundary, more work:** replace CLI subprocess tools with registered MCP tools and re-spike Codex exec.
3. **Environment workaround:** run the live investigator inside Linux/WSL or a container and keep the existing CLI-tool contract.
4. **Fallback:** activate direct GPT-5.6 API function calling as the documented fallback.

Given the submission deadline, option 1 is the shortest path, but it weakens the claim from OS-enforced isolation to an application-level broker boundary and therefore requires explicit approval.
