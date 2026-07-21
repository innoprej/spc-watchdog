# Devpost form — SPC Watchdog

## Exact form values

| Field | Value |
| --- | --- |
| Project name | **SPC Watchdog** |
| Tagline / elevator pitch | **An autonomous quality engineer that detects process violations with deterministic statistics, investigates root causes with row-level evidence, and improves its playbook only after human approval.** |
| Category | **Work & Productivity** |
| Repository | **https://github.com/innoprej/spc-watchdog** |
| License | **MIT** |
| Team size | **1** |
| Demo video | **[PASTE THE YOUTUBE URL AFTER UPLOAD]** |

Before pasting the repository URL into the form, confirm that the repository is publicly readable from a signed-out browser. The current project is public-safe, but repository visibility is an external submission action.

## Elevator pitch

SPC Watchdog is an autonomous quality engineer for manufacturing lines. Deterministic code decides when a process violates a Nelson rule; a Codex agent on GPT-5.6 Sol investigates through allowlisted evidence tools; a deterministic citation gate verifies every row; and a human controls whether the discovered lesson becomes an immutable new OCAP skill version.

## Full description

### Technological Implementation

SPC Watchdog uses a deliberately thin three-layer architecture.

**WATCH** is Python and NumPy, not an LLM. A fixed-seed SQLite factory emits AR(1) measurements over WebSocket while typed code evaluates Nelson Rules 1–3. The interface labels the compressed simulation clock honestly: one real second equals one simulated hour.

**INVESTIGATE** launches a real headless `codex exec` run configured for GPT-5.6 Sol. The runtime receives a fresh database-free workspace and no shell, file, or web tools. Its only path to factory evidence is an incident-scoped MCP broker with registered fixed queries. The backend parses the JSON event stream into the visible skill-load, hypothesis, tool-call, evidence, decision, and verification feed.

The agent returns a strict structured report whose claims contain stable row citations. A deterministic host gate re-reads every cited table, row, field, and value from SQLite before the report can render. A failed citation gets one bounded retry that reveals coordinates but never the correct value.

**LEARN** is a transactional human-in-the-loop state machine. A grounded proposal carries the base version, rationale, verified evidence, and patch. Reject is terminal. Approve atomically supersedes v1, inserts immutable v2, and advances the active pointer. Approved versions survive scenario resets.

The repository includes 64 pytest tests, exact replay-sequence regressions, frontend type-check/build, clean-clone Ubuntu CI, and schema-versioned sanitized fixtures for credential-free judging.

### Design

The product is organized around four visible verdict moments in one control-room surface:

1. the live chart flips from stable green to deterministic red;
2. every investigator action appears in a transparent activity feed;
3. the report renders with a visible citation-verification count; and
4. a human reviews the OCAP diff, approves v2, and sees the smarter re-run.

The interface never blurs live and recorded evidence. Replay keeps a `DETERMINISTIC REPLAY` badge visible at 1×, 2×, and 4×. Statistical verdicts say `Model involved: None`. Live and recorded investigator traces use different labels. Failed, inconclusive, and rejected states remain visible instead of being presented as success.

Both seeded stories are complete product flows. Scenario 1 eliminates clean equipment, finds a lot introduced two simulated hours before the shift, and confirms its accepted-marginal incoming inspection. Scenario 2 finds replacement-due tool wear, exposes a v1 playbook gap, and completes the human approval loop.

### Potential Impact

The wedge is specific: manufacturing quality engineers responding to an out-of-control SPC signal. Detection is only the opening step; proving a root cause requires correlating chart context with equipment, material, inspection, and tool-life records quickly enough to guide containment.

A 2024 industry analysis estimates an unproductive automotive hour at $2.3 million, or about $38,000 per minute. SPC Watchdog does not claim to save that amount; it demonstrates why reducing evidence-backed investigation latency matters. The canonical Scenario 1 live run produced a citation-verified report after 41.7 seconds of investigator runtime.

The product preserves the quality engineer's authority where consequences are highest. Statistics are deterministic, evidence is rechecked, and playbook changes require explicit human approval. The intended outcome is not “AI said so”; it is a faster, auditable eliminate-or-implicate workflow with evidence a human can inspect.

Source for the sector estimate: https://blog.siemens.com/2024/07/the-true-cost-of-an-hours-downtime-an-industry-analysis/

### Quality of the Idea

SPC Watchdog focuses on the gap after commodity SPC detection: autonomous, cited investigation that can learn from its own process failure without granting the agent unilateral control.

The novel closing beat is measured, not narrated. Scenario 2 v1 spends six registered calls and checks material genealogy before tool-life. The agent files a grounded change proposal. After human approval and reset, the exact v2 body visibly reaches the model; the same verified tool-wear verdict takes four calls, tool-life follows equipment immediately, and the irrelevant material branch disappears.

This combines three different trust models instead of applying a model to every step: deterministic statistics for detection, an agent for open-ended multi-hop reasoning, and deterministic plus human gates for publication and learning. That separation is the product's central design philosophy.

## How I used Codex

Codex was both the implementation collaborator and the live investigation runtime. I used an `AGENTS.md` contract, phased `/plan`, small checkpoint commits, tests, adversarial `/review`, a project-local judging skill, and an independent verification pass. The first subprocess-tool spike failed safely; Codex then checked current official runtime documentation, re-spiked an allowlisted MCP design, and used negative probes to reject two premature sandbox claims. The measured build log records 275 actual minutes against 510 planned across all four phases, with the deliberate security re-spike overrun and three rejected media candidates documented rather than hidden.

In the product, `codex exec` runs GPT-5.6 Sol, emits JSON events for the activity feed, loads the exact OCAP body through MCP, queries only registered evidence tools, and returns the structured cited report. Neither Codex nor GPT-5.6 decides whether a Nelson rule fired or whether a citation is valid.

## Built with

- Python 3.12
- FastAPI
- SQLite
- NumPy
- WebSockets
- Codex CLI (`codex exec --json`)
- GPT-5.6 Sol
- Model Context Protocol, Streamable HTTP transport
- React 19
- TypeScript 7
- Vite 8
- Tailwind CSS 4
- pytest
- GitHub Actions
- Playwright for deterministic capture
- FFmpeg and local text-to-speech for the submission video

## Test instructions

Prerequisites: Python 3.12 and Node.js 22.12 or newer. No API key or Codex login is required for replay.

```bash
git clone https://github.com/innoprej/spc-watchdog.git
cd spc-watchdog
python -m venv .venv
```

Activate `.venv` using `source .venv/bin/activate` on macOS/Linux or `.venv\Scripts\Activate.ps1` in Windows PowerShell, then run:

```bash
python -m pip install -e ".[dev]"
python run.py --mode replay --scenario scenario-2
```

Open http://127.0.0.1:8000. Wait for Rule 3, inspect the v1 tool trace and verified report, review the proposed diff, click **APPROVE & ACTIVATE V2**, and confirm the v2 trace uses four calls with tool-life immediately after equipment.

Optional automated gate:

```bash
python -m pytest
cd frontend
npm ci
npm run build
cd ..
python run.py --mode replay --smoke-test
python run.py --mode replay --scenario scenario-2 --smoke-test
```

## Final submission checklist for the human submitter

- [ ] Upload `spc-watchdog-build-week-final.mp4` to YouTube and paste its URL above.
- [ ] Make the repository public and confirm the default branch is `main`.
- [ ] Open the repository URL in a signed-out browser.
- [ ] Paste the exact category, description, built-with list, and test instructions from this file.
- [ ] Confirm the submitted video duration is 2:54 and captions are visible.
