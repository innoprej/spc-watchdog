# SPC Watchdog Project Charter

## Product

SPC Watchdog is an autonomous quality engineer for manufacturing lines.

**Tagline:** It watches, investigates, and learns.

The product is a clean-room, synthetic demonstration for OpenAI Build Week. It must be coherent enough to feel like a product rather than an isolated agent experiment, while remaining runnable by judges without factory data or live credentials.

## Demonstration promise

Within three minutes, the viewer sees four verdict moments:

1. A live statistical process control chart flips red after a deterministic Nelson-rule violation.
2. A transparent activity feed shows the Codex investigator loading its OCAP skill, forming hypotheses, calling registered tools, and evaluating evidence.
3. A structured incident report renders a verified root-cause verdict with row-level citations.
4. The agent proposes an OCAP skill diff, a human approves it, and a reset scenario demonstrates that the surviving v2 skill investigates more intelligently.

## Architecture

### WATCH — deterministic

- A seeded SQLite factory world streams one hourly process measurement per real second.
- The first demonstration uses an Individuals chart with a fixed centerline and sigma derived from a clean warm-up window.
- The engine implements Nelson Rule 1 as one point beyond 3 sigma, Rule 2 as nine consecutive points on one side, and Rule 3 as six consecutive increasing or decreasing points.
- All violations are recorded, but a deterministic causal-window key and cooldown prevent duplicate incident launches.
- Real UTC timestamps and simulated factory timestamps are stored separately. The UI always labels the simulation rate.

### INVESTIGATE — agentic

- Each incident queues one headless Codex exec run configured for GPT-5.6 Sol.
- The dedicated runtime workspace contains `AGENTS.md` and versioned OCAP skills, but no SQLite database. Backend-owned, allowlisted factory queries are exposed as registered MCP tools.
- Registered tools query an allowlisted backend broker and return compact rows with immutable IDs.
- The investigator follows an eliminate-or-implicate contract and emits a schema-validated `report.json` containing claims and row-level citations.
- The backend persists a versioned JSONL event stream with monotonically increasing sequence numbers. WebSocket clients receive a snapshot and resume from the last observed sequence.
- A deterministic gate re-reads every cited table, row, field, and canonical value. Verification failure permits one agent retry; only verified claims enter the official verdict.

### LEARN — human-gated

- The investigator may propose a patch to the active OCAP skill but cannot activate it.
- A human reviews the diff and explicitly approves or rejects it.
- Approval validates the base version and patch, writes a new immutable version atomically, and advances the active-version pointer.
- Scenario resets clear scenario and incident state but preserve approved skill versions.

## Seeded factory world

### Scenario 1 — material mean shift

A new material lot enters the line two simulated hours before a Rule 1 or Rule 2 violation. Recent equipment evidence is clean, lot genealogy identifies the transition, and incoming inspection confirms that the lot is marginal. The answer is discoverable only after eliminating equipment and joining evidence across two additional data sources.

### Scenario 2 — tool-wear trend and playbook gap

Accumulated tool wear produces a Rule 3 trend. The initial OCAP skill checks recent equipment events but does not direct the investigator to tool-life or cycle-age evidence. The investigator finds the evidence, reports the gap, and proposes a trend-specific step for the v2 playbook.

## State and recovery defaults

The incident lifecycle is `watching → violation → queued → investigating → verifying → resolved|degraded → proposal_pending|complete`. A missing Codex executable, unavailable authentication or credits, timeout, cancellation, malformed event, invalid report, and exhausted citation retry each produce an explicit degraded state rather than a fabricated success.

Only one incident investigates at a time. A scenario reset creates a new run ID. Browser reconnects recover from persisted event sequence numbers.

## Live and replay modes

- `python run.py` starts the live path and launches Codex investigations. If live prerequisites are unavailable, the UI explains the failure and offers replay rather than silently changing modes.
- `python run.py --mode replay` is the credential-free judge and CI path.
- Replay fixtures are sanitized recordings of canonical live runs. Sanitization removes absolute paths, usernames, and credentials only; it does not rewrite the investigation narrative.
- Every replay JSONL file carries a schema version, source-run ID, ordered events, and relative timing.
- The UI keeps a `DETERMINISTIC REPLAY` badge visible and offers 1x, 2x, and 4x playback controls.

## Delivery constraints

- Deadline: July 21, 2026 at 17:00 PT.
- Stack: Python 3.12, FastAPI, NumPy, SQLite, React, Vite, Tailwind CSS, and WebSocket streaming unless the spike proves a strong reason to adjust.
- Default agent runtime: headless Codex exec on GPT-5.6 Sol, billed through Codex credits rather than an OpenAI API dependency.
- Phase 1 runtime spike timebox: approximately 90 minutes.
- Judges must be able to start replay mode from a clean macOS or Linux clone with one cross-platform command.
- GitHub Actions on `ubuntu-latest` must prove the clean-clone replay boot path beginning in Phase 1.
- License: MIT.

## Scope boundary

The two seeded scenarios and their three-minute narrative define the required domain. Multi-line orchestration, production identity, generalized database authorization, distributed queues, arbitrary OCAP editing, and long-term operational hardening are backlog work unless a phase gate exposes a direct demo need.
