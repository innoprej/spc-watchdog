# Codex Exec Runtime Spike

## Verdict

**PASS — a registered MCP tool completed inside a `read-only` Codex sandbox after every non-broker tool surface was disabled, returned stable row evidence, received the serialized runtime contract, and produced schema-valid cited output with no command event.**

The spike used Codex CLI `0.144.6`, ChatGPT-managed authentication, and the `gpt-5.6-sol` model slug. Machine-readable events, schema-constrained final output, sterile runtime-contract serialization, and MCP broker access all worked. Windows denied the initial `.cmd` and `.ps1` subprocess probes in safe sandboxes, so the revised spike exposed the same allowlisted broker operation as a Streamable HTTP MCP tool instead. A later adversarial probe showed that Windows read sandboxes and beta permission profiles did not reliably prevent reads outside the working directory; the final command therefore removes shell access entirely rather than relying on a path filter.

## Official contract checked

| Concern | Current official contract | Source |
| --- | --- | --- |
| Non-interactive execution | `codex exec` is the supported non-interactive command. | [Codex CLI command reference](https://learn.chatgpt.com/docs/developer-commands.md?surface=cli#cli-codex-exec) |
| Model selection | `-m` / `--model` overrides the configured model for an invocation. | [Codex models](https://learn.chatgpt.com/docs/models.md) |
| Working directory | `-C` / `--cd` sets the agent working directory before processing the request. | [Codex CLI command reference](https://learn.chatgpt.com/docs/developer-commands.md?surface=cli) |
| Sandbox | `read-only`, `workspace-write`, and `danger-full-access` are documented modes; automation should use the least permission that works. | [Codex CLI command reference](https://learn.chatgpt.com/docs/developer-commands.md?surface=cli#cli-codex-exec) |
| Tool and context removal | Feature flags and config can disable shell/exec, browser/computer, app/plugin, image, hook, goal, skill-dependency, workspace-dependency, tool-suggestion, subagent, web-search, environment-context, project-doc, and skill-instruction surfaces. | [Codex configuration basics](https://learn.chatgpt.com/docs/config-file/config-basic), [Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference) |
| Event stream | `--json` emits JSONL events including thread/turn lifecycle and `item.*` events for reasoning, commands, file changes, MCP calls, web searches, and plans. | [Codex non-interactive mode](https://learn.chatgpt.com/docs/developer-commands.md?surface=cli#cli-codex-exec) |
| Structured final output | `--output-schema` constrains the final response to a JSON Schema; `-o` writes the final message. | [Codex non-interactive mode](https://learn.chatgpt.com/docs/developer-commands.md?surface=cli#cli-codex-exec) |
| MCP transport and scope | Codex supports Streamable HTTP MCP servers in `config.toml`; trusted projects may keep project-scoped `.codex/config.toml` configuration. | [Model Context Protocol](https://learn.chatgpt.com/docs/extend/mcp), [Codex configuration](https://learn.chatgpt.com/docs/config-file/config-reference) |
| MCP restriction and reliability | `required`, `enabled_tools`, startup/tool timeouts, and server/per-tool approval modes are supported. `default_tools_approval_mode = "approve"` is the non-interactive trusted-tool policy used by this project. | [Model Context Protocol](https://learn.chatgpt.com/docs/extend/mcp), [Codex configuration](https://learn.chatgpt.com/docs/config-file/config-reference) |
| Authentication and billing | `codex exec` reuses saved CLI authentication. ChatGPT plans use Codex usage and credits; API-key runs use API token billing. | [Codex pricing](https://learn.chatgpt.com/docs/pricing.md), [Codex authentication](https://learn.chatgpt.com/docs/auth) |
| Codex state isolation | `CODEX_HOME` selects the root for authentication, configuration, sessions, skills, and other state. | [Codex configuration](https://learn.chatgpt.com/docs/config-file/config-advanced#config-and-state-locations) |

The CLI does not expose a per-run currency charge in its JSONL stream, so this project can truthfully state that the observed run used ChatGPT-managed Codex authentication and reported token usage, but not a precise credit charge.

## Local evidence

| Gate | Result | Evidence |
| --- | --- | --- |
| Project-local skill discovery | PASS | `codex debug prompt-input` listed `judge-panel-review` from the repository's `.codex/skills` root. |
| Authentication | PASS | `codex login status` reported ChatGPT-managed login. No API-key environment variable was supplied. |
| Model availability | PASS | The local model catalog listed `gpt-5.6-sol` as GPT-5.6 Sol, and the exec invocation accepted `-m gpt-5.6-sol`. |
| JSONL parsing | PASS | The successful run parsed lifecycle, MCP tool, agent-message, and usage objects without scraping terminal prose. |
| Structured final output | PASS | The successful run produced schema-valid JSON with exactly `claim` and `citation_id`. |
| Runtime contract | PASS | Automatic `AGENTS.md` loading was separately observed, but it prefixes the source's absolute path. The final sterile run instead serialized the same public-safe contract content into stdin and returned its private marker. |
| CLI subprocess tool in safe sandboxes | FAIL | Windows denied `.cmd` and `.ps1` process creation in both `read-only` and `workspace-write`; the tools themselves worked from the host shell. |
| MCP discovery | PASS | The project-scoped server initialized and advertised only the allowlisted `query_probe` tool. |
| MCP invocation in `read-only` | PASS | The JSONL stream contained one completed `mcp_tool_call` with the expected stable row and no `command_execution` item. |
| Headless tool approval | PASS | Changing the server default from `auto` to `approve` allowed dispatch under non-interactive approval policy; the earlier `auto` run cancelled before `tools/call`. |
| Read-only path isolation | FAIL | An adversarial shell probe could read the source contract and the SQLite file because read-only prevents writes, not broad reads. |
| Beta permission-profile path isolation | FAIL | Both symbolic and explicit path policies were accepted but did not reliably block PowerShell reads on this native Windows host. The final report was not trusted when it contradicted returned tool content. |
| Shell-free broker boundary | PASS | The final invocation explicitly disabled all discovered command, browser/computer, web, app/plugin, image, hook, goal, skill-dependency, workspace-dependency, tool-suggestion, and subagent surfaces. Its only tool event was the allowlisted MCP call. |
| Prompt sanitization | PASS | `codex debug prompt-input` confirmed no runtime absolute path, user-directory path, username, environment block, or skills block while the serialized contract marker remained present. |
| User-state isolation | PARTIAL BY DESIGN | A credential-only `CODEX_HOME` avoids user config and plugins, but global `.agents/skills` discovery is OS-home based. Phase 1 disables skill instructions completely; Phase 2 must isolate OS-home discovery before installing only the OCAP skill. No credential content was read, copied into the runtime, logged, or committed. |
| Native OCAP skill body load | OPEN FOR PHASE 2 | Automatic project-document discovery was observed separately, but a probe skill's body was not progressively loaded after shell removal. Phase 2 must prove a truthful skill-mount mechanism before the activity feed claims a skill-load event. |

The spike invocation temporarily used `enabled = true`. The committed contributor-safe default is `enabled = false`; Phase 2's live backend will enable the still-required server only after the broker is listening and healthy. This avoids making unrelated Codex commands depend on a demo service that is not running.

The successful MCP call returned this structured row inside Codex:

```json
{"id":"probe-row-001","table":"probe_evidence","field":"status","value":"mcp-tool-access-confirmed"}
```

The final schema-valid boundary report included the MCP evidence, runtime-contract marker, and the absence of shell access:

```json
{"claim":"mcp-tool-access-confirmed","citation_id":"probe-row-001","contract_marker":"cobalt-watchdog","skill_marker":"","shell_unavailable":true}
```

The event sequence was `thread.started` → `turn.started` → `item.started` (`mcp_tool_call`) → `item.completed` (`mcp_tool_call`) → `item.completed` (`agent_message`) → `turn.completed`. No raw run log or thread identifier is committed. This note contains no absolute paths, usernames, or credentials.

## Boundary assessment

The passing design keeps the SQLite database, broker implementation, source repository, and credentials outside the investigator workspace. The backend serializes the public-safe runtime contract into stdin because automatic project-document source labels expose absolute host paths. The model receives no non-broker tool, environment block, or skill catalog. The child uses an external credential-only `CODEX_HOME`; Phase 1 also disables skill instructions because global skill discovery is independent of `CODEX_HOME`. The `read-only` sandbox remains defense in depth; this project does not claim that native Windows read-only mode prevents reads by itself.

The MCP transport crosses the sandbox by design, but it does not grant arbitrary network or SQL access: the configured loopback server is required, the server tool allowlist is explicit, and each broker operation owns its query shape. Phase 2 will replace `query_probe` with the four incident-scoped factory query tools, verify that the runtime workspace contains no database or database path, and close the native skill-body loading question without restoring broad shell access.

## Adopted decision

Use `codex exec` with GPT-5.6 Sol, `read-only`, no non-broker tools, no automatic host-path context, a serialized runtime contract, a disposable database-free workspace outside the source repository, an isolated credential-only `CODEX_HOME`, and a backend-owned allowlisted MCP broker as the standard live path. Phase 2 may re-enable only the OCAP skill after proving OS-home isolation.

Keep `danger-full-access`, WSL/container isolation, and direct GPT-5.6 API fan-out dormant. The initial subprocess failure remains documented because it explains the MCP boundary and prevents an unsupported claim that Windows safe sandboxes can launch the original CLI wrappers.
