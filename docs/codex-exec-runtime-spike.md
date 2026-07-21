# Codex Exec Runtime Spike

## Verdict

**PASS — a registered MCP tool completed inside a `read-only` Codex sandbox, returned stable row evidence, and produced schema-valid cited output without a shell command.**

The spike used Codex CLI `0.144.6`, ChatGPT-managed authentication, and the `gpt-5.6-sol` model slug. Machine-readable events, schema-constrained final output, project-scoped MCP configuration, and sandboxed broker access all worked. Windows denied the initial `.cmd` and `.ps1` subprocess probes in safe sandboxes, so the revised spike exposed the same allowlisted broker operation as a Streamable HTTP MCP tool instead.

## Official contract checked

| Concern | Current official contract | Source |
| --- | --- | --- |
| Non-interactive execution | `codex exec` is the supported non-interactive command. | [Codex CLI command reference](https://learn.chatgpt.com/docs/developer-commands.md?surface=cli#cli-codex-exec) |
| Model selection | `-m` / `--model` overrides the configured model for an invocation. | [Codex models](https://learn.chatgpt.com/docs/models.md) |
| Working directory | `-C` / `--cd` sets the agent working directory before processing the request. | [Codex CLI command reference](https://learn.chatgpt.com/docs/developer-commands.md?surface=cli) |
| Sandbox | `read-only`, `workspace-write`, and `danger-full-access` are documented modes; automation should use the least permission that works. | [Codex CLI command reference](https://learn.chatgpt.com/docs/developer-commands.md?surface=cli#cli-codex-exec) |
| Event stream | `--json` emits JSONL events including thread/turn lifecycle and `item.*` events for reasoning, commands, file changes, MCP calls, web searches, and plans. | [Codex non-interactive mode](https://learn.chatgpt.com/docs/developer-commands.md?surface=cli#cli-codex-exec) |
| Structured final output | `--output-schema` constrains the final response to a JSON Schema; `-o` writes the final message. | [Codex non-interactive mode](https://learn.chatgpt.com/docs/developer-commands.md?surface=cli#cli-codex-exec) |
| MCP transport and scope | Codex supports Streamable HTTP MCP servers in `config.toml`; trusted projects may keep project-scoped `.codex/config.toml` configuration. | [Model Context Protocol](https://learn.chatgpt.com/docs/extend/mcp), [Codex configuration](https://learn.chatgpt.com/docs/config-file/config-reference) |
| MCP restriction and reliability | `required`, `enabled_tools`, startup/tool timeouts, and server/per-tool approval modes are supported. `default_tools_approval_mode = "approve"` is the non-interactive trusted-tool policy used by this project. | [Model Context Protocol](https://learn.chatgpt.com/docs/extend/mcp), [Codex configuration](https://learn.chatgpt.com/docs/config-file/config-reference) |
| Authentication and billing | `codex exec` reuses saved CLI authentication. ChatGPT plans use Codex usage and credits; API-key runs use API token billing. | [Codex pricing](https://learn.chatgpt.com/docs/pricing.md), [Codex authentication](https://learn.chatgpt.com/docs/auth) |

The CLI does not expose a per-run currency charge in its JSONL stream, so this project can truthfully state that the observed run used ChatGPT-managed Codex authentication and reported token usage, but not a precise credit charge.

## Local evidence

| Gate | Result | Evidence |
| --- | --- | --- |
| Project-local skill discovery | PASS | `codex debug prompt-input` listed `judge-panel-review` from the repository's `.codex/skills` root. |
| Authentication | PASS | `codex login status` reported ChatGPT-managed login. No API-key environment variable was supplied. |
| Model availability | PASS | The local model catalog listed `gpt-5.6-sol` as GPT-5.6 Sol, and the exec invocation accepted `-m gpt-5.6-sol`. |
| JSONL parsing | PASS | The successful run parsed lifecycle, MCP tool, agent-message, and usage objects without scraping terminal prose. |
| Structured final output | PASS | The successful run produced schema-valid JSON with exactly `claim` and `citation_id`. |
| Working-directory contract | PASS | The agent loaded the disposable database-free runtime contract from its configured working directory. |
| CLI subprocess tool in safe sandboxes | FAIL | Windows denied `.cmd` and `.ps1` process creation in both `read-only` and `workspace-write`; the tools themselves worked from the host shell. |
| MCP discovery | PASS | The project-scoped server initialized and advertised only the allowlisted `query_probe` tool. |
| MCP invocation in `read-only` | PASS | The JSONL stream contained one completed `mcp_tool_call` with the expected stable row and no `command_execution` item. |
| Headless tool approval | PASS | Changing the server default from `auto` to `approve` allowed dispatch under non-interactive approval policy; the earlier `auto` run cancelled before `tools/call`. |

The successful MCP call returned this structured row inside Codex:

```json
{"id":"probe-row-001","table":"probe_evidence","field":"status","value":"mcp-tool-access-confirmed"}
```

The final schema-valid report was:

```json
{"claim":"mcp-tool-access-confirmed","citation_id":"probe-row-001"}
```

The event sequence was `thread.started` → `turn.started` → `item.started` (`mcp_tool_call`) → `item.completed` (`mcp_tool_call`) → `item.completed` (`agent_message`) → `turn.completed`. No raw run log or thread identifier is committed. This note contains no absolute paths, usernames, or credentials.

## Boundary assessment

The passing design keeps the SQLite database and broker implementation outside the investigator workspace. Codex receives only its contract and skills, while the backend exposes a fixed MCP allowlist. The Codex run remains in `read-only` when investigation output is returned through the final response; `workspace-write` remains available only if a later runtime artifact genuinely requires it.

The MCP transport crosses the Codex shell sandbox by design, but it does not grant arbitrary network or SQL access: the configured loopback server is required, the server tool allowlist is explicit, and each broker operation owns its query shape. Phase 2 will replace `query_probe` with the four incident-scoped factory query tools and will verify that the runtime workspace contains no database or database path.

## Adopted decision

Use `codex exec` with GPT-5.6 Sol, a safe sandbox, a disposable database-free runtime workspace, and a backend-owned allowlisted MCP broker as the standard live path.

Keep `danger-full-access`, WSL/container isolation, and direct GPT-5.6 API fan-out dormant. The initial subprocess failure remains documented because it explains the MCP boundary and prevents an unsupported claim that Windows safe sandboxes can launch the original CLI wrappers.
