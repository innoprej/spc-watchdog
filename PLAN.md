# SPC Watchdog Build Plan

## Objective

Deliver a public-safe, judge-runnable SPC Watchdog demonstration in which deterministic process monitoring triggers a transparent Codex investigation, verified evidence produces the root-cause verdict, and human approval improves the active OCAP skill.

The hard deadline is July 21, 2026 at 17:00 PT. Phases have acceptance gates, not calendar allocations, and run back-to-back as soon as each gate passes. The only explicit timebox is the approximately 90-minute Phase 1 Codex runtime spike.

## Phase budgets

| Phase | Budget from plan approval | Overrun rule |
| --- | ---: | --- |
| Phase 1 | Approximately 2.5 hours | Stop and ask the user to choose scope cuts. |
| Phase 2 | Approximately 2.5 hours | Stop and ask the user to choose scope cuts. |
| Phase 3 | Approximately 2 hours | Stop and ask the user to choose scope cuts. |
| Phase 4 | Approximately 1.5 hours | Stop and ask the user to choose scope cuts. |

If the exec spike passes every hard gate, record the evidence and continue Phase 1 without waiting. If any hard gate fails, stop before touching the fallback.

## Fixed decisions

- The architecture and scenario contracts in `docs/project-charter.md` are binding.
- One Codex investigator runs per incident; additional incidents queue.
- SQLite stays outside the Codex runtime workspace and is reachable only through registered CLI tools backed by an allowlisted broker.
- Only citation-verified claims contribute to an official verdict. One verification-informed retry is allowed.
- Approved skill versions survive scenario resets.
- Live mode is the default; replay mode is explicit, credential-free, visibly labeled, and adjustable to 1x, 2x, or 4x.
- Committed JSONL replay logs are schema-versioned and sanitized only for absolute paths, usernames, and credentials.
- Requirements beyond the two seeded scenarios go to `BACKLOG.md` unless they directly unblock the demo or judge quickstart.

## Pre-Phase 1 approval gate

- [x] Confirm the five architecture decisions from the blindspot pass.
- [x] Initialize the public-safe repository and record the project working agreement.
- [x] Draft the charter, phased plan, acceptance gates, and backlog boundary.
- [x] Select `SPC Watchdog` as the product display name; keep the repository name `spc-watchdog`.
- [x] Receive, validate, and install the user's `judge-panel-review` skill file.
- [x] Obtain user approval for this plan.

No application scaffolding begins until this gate passes.

## Phase 1 — Prove the runtime and WATCH path

### Scope

1. **Codex exec / GPT-5.6 Sol spike — approximately 90 minutes**
   - Read current official OpenAI documentation before choosing flags or configuration.
   - Verify the exact headless command, JSON/JSONL event format, working-directory behavior, model selection, sandbox and tool access, authentication expectations, and Codex-credit billing claims.
   - Run a minimal investigation in an isolated disposable workspace and capture a sanitized sample event stream.
   - Record what official documentation proves separately from what local observation proves.
   - Decide `exec` or fallback at the end of the timebox. Trigger the direct GPT-5.6 API fallback only if the live spike cannot expose sufficient events, select the required model, maintain the workspace/tool boundary, or run reliably enough for the demo.
2. **Repository and cross-platform bootstrap**
   - Add Python 3.12 backend and React/Vite/Tailwind frontend skeletons with the smallest necessary dependency set.
   - Implement `python run.py` as the single cross-platform entry point.
   - Provide a replay-mode boot skeleton even before full replay fixtures exist.
3. **Synthetic factory world**
   - Define the minimal SQLite schema for measurements, equipment logs, material genealogy, incoming inspection, incidents, OCAP versions, proposals, and event metadata.
   - Generate a deterministic clean warm-up window and Scenario 1 from a fixed seed with immutable row IDs and separate UTC/simulated timestamps.
   - Shape the schema so Scenario 2 can be added without migration churn, but do not generalize beyond the two scenarios.
4. **Deterministic Nelson engine**
   - Implement Rules 1, 2, and 3 with typed inputs and explicit window semantics.
   - Record overlapping signals while deduplicating incident creation by a deterministic causal window.
   - Add focused pytest tests for positive, negative, boundary, warm-up, and overlap cases.
5. **Streaming dashboard skeleton**
   - Stream measurements and rule events through WebSocket.
   - Render a desktop-first control-room layout with the chart, persistent simulation-rate label, incident status, and reserved activity/report/proposal regions.
   - Make the chart's normal-to-red transition work for Scenario 1; defer visual polish.
6. **CI bootstrap**
   - Add an `ubuntu-latest` workflow that installs from a clean clone, runs backend tests and frontend checks, and proves `python run.py --mode replay` can boot without credentials.

### Acceptance criteria

- [x] A public-safe spike note records official source links, verified command mechanics, observed event examples, sandbox/working-directory findings, model-selection evidence, and any billing uncertainty.
- [ ] A minimal GPT-5.6 Sol Codex exec produces a parseable event stream in the disposable runtime, or a written hard-gate decision activates the API fallback.
- [ ] No prompt or runtime workspace contains the planted root cause, factory database, credentials, username, or absolute local path.
- [ ] Rebuilding Scenario 1 with the same seed yields the same measurements, evidence IDs, and violation window.
- [ ] Nelson Rules 1–3 pass focused pytest coverage, including exact threshold and sequence boundaries.
- [ ] Scenario 1 streams to the dashboard and visibly flips the chart red from deterministic engine output.
- [ ] `python run.py` starts the live application path; unavailable live prerequisites produce an explicit state rather than a silent replay.
- [ ] `python run.py --mode replay` boots the skeleton without Codex credentials.
- [ ] The Ubuntu CI job passes the clean-clone test, frontend check, and replay-mode boot smoke test.
- [ ] The phase-close ritual in `AGENTS.md` passes with no unresolved CRITICAL review finding.

## Phase 2 — Complete the INVESTIGATE path

### Scope

1. Implement the backend-owned, incident-scoped query broker and the registered CLI tools: `query-equipment-logs`, `query-material-lots`, `query-incoming-inspection`, and `chart-context`.
2. Create the dedicated Codex runtime template containing its public-safe investigation `AGENTS.md`, the initial OCAP skill, output schema, and tool launchers—but no database.
3. Launch one queued Codex exec investigation per incident and normalize its event stream into skill-load, hypothesis, tool-call, evidence, decision, and status events.
4. Persist every run as sequence-numbered, schema-versioned JSONL and support WebSocket snapshot/resume.
5. Validate `report.json`, verify every citation deterministically against the broker's canonical row value, and supply verification failures to one retry.
6. Connect Scenario 1 end to end: eliminate equipment, implicate the new lot through genealogy, and confirm marginal incoming inspection.
7. Render the transparent activity feed and the verified incident report; show any terminally rejected claim only as struck-through audit evidence.

### Acceptance criteria

- [ ] The Codex workspace has no database file or direct database path, and every world query is observable as a registered tool event.
- [ ] Tool outputs use compact stable rows and cannot issue arbitrary SQL.
- [ ] A live Scenario 1 run reaches the planted material-lot cause without the prompt or playbook naming the answer.
- [ ] The report cites the clean equipment evidence, lot transition, and marginal incoming-inspection evidence with stable IDs.
- [ ] A tampered row, field, or value fails deterministic citation verification in pytest.
- [ ] One verification-informed retry is observable; an exhausted failure cannot contribute to the official verdict.
- [ ] Refreshing or reconnecting the browser resumes the run from persisted event sequence numbers without duplicating feed items.
- [ ] The activity feed visibly distinguishes agent hypotheses from deterministic tool results and verifier decisions.
- [ ] Each run leaves a schema-versioned local JSONL artifact suitable for later sanitization and replay capture.
- [ ] The phase-close ritual passes with no unresolved CRITICAL review finding.

## Phase 3 — Complete LEARN, replay, and the three-minute story

### Scope

1. Add Scenario 2's deterministic tool-wear trend and Rule 3 incident with discoverable cycle-age evidence.
2. Make the v1 OCAP gap genuine but recoverable: it checks recent equipment events without directing accumulated tool-life analysis.
3. Let the investigator file a structured skill-change proposal containing the base version, rationale, evidence, and patch.
4. Add a human diff-review flow with explicit approve/reject actions, atomic immutable version creation, and active-version advancement.
5. Protect approved skills across scenario resets and re-run Scenario 2 with v2 for the closing beat.
6. Measure the improvement: v2 reaches tool-life evidence earlier than v1 and avoids unnecessary material-lot work when the evidence supports tool wear.
7. Polish the red-chart transition, live activity feed, cited verdict, proposal diff, and approval confirmation for a 1440p desktop capture.
8. Record canonical live runs for both scenarios, sanitize only absolute paths, usernames, and credentials, and commit versioned replay fixtures.
9. Implement deterministic replay with original relative timing, persistent mode/source-run labels, and 1x/2x/4x controls.
10. Record the primary three-minute demo footage and pickup shots from the same canonical run data.

### Acceptance criteria

- [ ] Scenario 2 deterministically triggers Rule 3 and exposes tool-life evidence not prescribed by the v1 skill.
- [ ] The v1 live investigation reaches a verified tool-wear verdict and files a grounded, reviewable proposal rather than editing itself directly.
- [ ] Reject leaves the active skill unchanged; approve creates an immutable v2 and advances the active pointer atomically.
- [ ] Resetting the scenario preserves v2, and the re-run loads v2 visibly in the activity feed.
- [ ] The v2 re-run consults tool-life evidence before irrelevant material genealogy and reaches the verified verdict in fewer or equal tool calls.
- [ ] Both committed replay logs carry a schema version and contain no absolute paths, usernames, or credentials.
- [ ] Replay reproduces chart, feed, report, and proposal ordering without Codex or API credentials.
- [ ] `DETERMINISTIC REPLAY` remains visible at 1x, 2x, and 4x; speed changes do not change event order or evidence.
- [ ] A timed rehearsal shows the core story within three minutes at the selected capture speed.
- [ ] The Ubuntu clean-clone replay gate remains green.
- [ ] The phase-close ritual passes with no unresolved CRITICAL review finding.

## Phase 4 — Package and submit

### Scope

1. Write the public README with the chosen display name, value proposition, architecture, transparent Codex/GPT-5.6 Sol story, prerequisites, one-command live and replay quickstarts, screenshots, and limitations.
2. Confirm the MIT license and complete concise public architecture/demo documentation.
3. Finalize the demo video, thumbnail, captions, Devpost description, technology list, impact argument, repository link, and required submission fields.
4. Verify all time-sensitive market and economic claims against current primary or authoritative sources and cite them near the claim.
5. Run public-safety, secret, path, username, trademark, license, clean-clone, and replay checks.
6. Rehearse the judge path from a fresh clone and submit only after explicit user approval for external publication actions.

### Acceptance criteria

- [ ] README distinguishes deterministic WATCH, agentic INVESTIGATE, and human-gated LEARN without implying that the model performs statistical detection.
- [ ] A judge can clone and run replay with one documented cross-platform command and no credentials.
- [ ] Live prerequisites, Codex-credit behavior, degraded states, and replay behavior are described honestly.
- [ ] The repository contains an MIT license and no secrets, credentials, personal data, usernames, absolute local paths, raw unsanitized logs, employer artifacts, or unrelated third-party trademarks.
- [ ] The final video is at most three minutes and visibly contains the red chart, transparent investigation, cited report, approved skill diff, and smarter v2 re-run.
- [ ] Every Devpost field and required asset is complete, accessible, and consistent with the repository and video.
- [ ] The latest `ubuntu-latest` clean-clone replay workflow is green.
- [ ] The final `/review` and `judge-panel-review` have no unresolved CRITICAL findings.
- [ ] The user explicitly approves the final external submission or publication action.

## Cross-phase verification matrix

| Invariant | Primary proof |
| --- | --- |
| Statistics never delegated to an LLM | Nelson unit tests plus deterministic rule events preceding investigation launch |
| Conclusions require row citations | Report schema tests, verifier tests, and a tampered-citation failure demonstration |
| Agent uses registered tools only | Database-free runtime workspace plus broker/tool event audit |
| Simulation is honest | Persistent clock-rate label and separate simulated/UTC timestamps |
| Replay needs no credentials | Ubuntu clean-clone replay boot and full scenario playback |
| Human controls learning | Proposal state machine, reject test, approve test, immutable v2, and preserved version after reset |

## Deviations & discoveries

Append entries immediately; do not wait for phase close.

| Date | Type | Phase | Entry | Why |
| --- | --- | --- | --- | --- |
| 2026-07-21 | Decision | Phase 1 | Treat the first spike as a Codex exec / GPT-5.6 Sol runtime spike; keep direct API fan-out conditional. | The default product story and runtime use Codex credits, so building two integrations before proving the primary path would waste deadline time. |
| 2026-07-21 | Decision | Cross-phase | Use one queued investigator per incident and interpret fan-out as multi-hop tool activity and event propagation. | Concurrent investigators add cost and race conditions without strengthening either seeded scenario. |
| 2026-07-21 | Decision | Phase 2 | Enforce the tool-only boundary with a database-free runtime workspace and backend query broker. | A prompt-only prohibition would not substantiate the product's architecture invariant. |
| 2026-07-21 | Decision | Phase 3 | Preserve approved skill versions across scenario resets and expose 1x/2x/4x replay speeds. | The smarter-v2 re-run is the closing beat, and adjustable playback protects video pacing without disguising replay. |
| 2026-07-21 | Scope | All | Implement safeguards only to the depth required by the two seeded scenarios; defer general production hardening. | The submission deadline is today, and visible end-to-end proof outranks unused generality. |
| 2026-07-21 | Blocker | Phase 1 | Codex exec accepted GPT-5.6 Sol, emitted parseable JSONL, and produced schema-valid output, but both safe sandbox modes denied registered CLI tool process creation on Windows. Phase 1 stopped before fallback or scaffolding. | Registered tool access inside the constrained runtime is an explicit hard gate; choosing weaker isolation, MCP tools, Linux isolation, or the API fallback changes the architecture and requires the user's scope decision. |
