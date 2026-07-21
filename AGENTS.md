# SPC Watchdog Working Agreement

## Mission

Build SPC Watchdog for OpenAI Build Week by July 21, 2026 at 17:00 PT. The product is judged equally on technological implementation, product coherence, potential impact, and quality and novelty; technological implementation is the tie-breaker.

The three-minute demonstration is the governing product surface. SPC Watchdog must visibly watch a simulated production line, investigate a statistically detected incident with a Codex agent running on GPT-5.6 Sol, verify every reported claim, and learn through a human-approved OCAP skill change.

## Architecture invariants

1. Statistical judgments are deterministic code. The Nelson-rules engine alone decides whether a rule fired; an LLM never makes that decision.
2. Every agent conclusion carries row-level citations. The deterministic citation-verification gate must pass before a claim contributes to the rendered official verdict. Rejected claims may appear only as visibly struck-through audit records.
3. The investigation layer talks to the factory world only through registered tools. Prompts and the investigation workspace never receive direct database access; registered tools use the backend-owned query boundary.
4. Simulation is honestly labeled in the UI. The simulation clock and its `1 real second = 1 simulated hour` rate remain visible.

## Confirmed runtime decisions

- Run one Codex investigator per incident and queue overlapping incidents. Phase 2 fan-out means transparent multi-hop investigation activity and event propagation, not concurrent investigator agents.
- Keep SQLite outside the Codex runtime workspace. Give the runtime only its contract, OCAP skills, and registered CLI tools backed by an allowlisted query broker.
- On citation failure, provide verification feedback and allow one retry. After that, verified claims alone form the verdict and rejected claims remain visible only in the audit trail.
- The initial Scenario 2 playbook checks recent equipment events but omits accumulated tool-life or cycle-age analysis. The investigation can expose this gap and propose a trend-specific tool-life step.
- Phase 1 begins with a timeboxed Codex exec / GPT-5.6 Sol runtime spike. Build the direct GPT-5.6 API fallback only if documented spike gates prove the exec path unsuitable.
- Approved skill versions survive scenario resets so the closing demonstration can re-run the incident with the improved v2 playbook.

## Engineering rules

- Make small commits with imperative subject lines.
- Require pytest coverage for the Nelson-rules engine and citation verifier.
- Use Python type hints.
- When adding a dependency, record why it is necessary in the commit body.
- Prefer the smallest implementation that proves the two seeded scenarios. Put safeguards or generalizations that do not serve them in `BACKLOG.md`.
- Prioritize demo-first delivery: polish for the red chart, live activity feed, cited report, and skill-change approval flow outranks internal elegance.
- Keep the repository public-safe from its first commit. Never commit secrets, credentials, personal data, absolute local paths, usernames, raw runtime logs, employer code, or proprietary schemas.
- Keep user-visible and repository content in English. Use unrelated third-party trademarks neither in product copy nor synthetic factory data.
- Keep the entry point cross-platform and singular: `python run.py`. Replay mode must run without credentials.

## Working log and phase-close ritual

`PLAN.md` is the canonical build plan and contains a `Deviations & discoveries` section. Append a line immediately when reality diverges from the plan, including a deviation, discovery, tentative decision, or deferral and why it happened.

At each phase close:

1. Review the diff with `/review`.
2. Run the `judge-panel-review` skill once it is installed and resolve every CRITICAL finding.
3. Summarize the phase's deviations and discoveries in `PLAN.md`.
4. Append measured acceleration numbers to `docs/codex-acceleration-log.md`.
5. Run the phase acceptance checks before opening the next phase.

## Scope guard

If a task does not serve the three-minute demo or the judges' quickstart, defer it to `BACKLOG.md`. The submission deadline is the only calendar anchor; phases run back-to-back as soon as their gates pass.

## Session hygiene

Hackathon judges may read this file through the session log. Keep it accurate, concise, and current whenever architecture, safety boundaries, phase gates, or demo decisions change.
