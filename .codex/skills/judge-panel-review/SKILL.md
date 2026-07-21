---
name: judge-panel-review
description: Pre-submission quality gate for OpenAI Build Week — scores the current project state against the event's four official judging criteria as this event's panel publicly evaluates work. Run at every phase close and before submitting.
---

# Judge Panel Review — Build Week Submission Gate

Simulate the official judging pass for this repo's current state. Be a rigorous, evidence-anchored reviewer — no cheerleading. Every finding must point at something concrete in the repo/submission and come with a fix.

## 1. Inputs — read before scoring

- README.md (including the required "how you collaborated with Codex" section)
- PLAN.md (decisions, deviations & discoveries), BACKLOG.md
- The judge-facing product surfaces (run the demo or replay mode if possible)
- docs/video-script.md and the Devpost form text, if present
- docs/codex-acceleration-log.md

## 2. Stage One screen (pass/fail, before scoring)

Flag as CRITICAL if any of these is not unmistakable at a glance:
- The project plausibly fits the chosen category theme (Work & Productivity)
- Codex usage is evident (README narrative + session evidence)
- GPT-5.6 usage is evident and truthfully described (never claim an unused primitive)
- The project can be installed and run (or replayed without an API key) per the README

## 3. Score the four official criteria (verbatim from the rules)

1. **Technological Implementation** — "How thoroughly and skillfully does the project use Codex? Does the code reflect genuine effort and a working, non-trivial implementation?"
2. **Design** — "Does the project deliver a working or runnable project that has a complete, coherent product experience — not just a technical proof of concept?"
3. **Potential Impact** — "Does the project make a credible, specific case for solving a real problem for a real audience — and does the solution actually address that problem based on what's demonstrated?"
4. **Quality of the Idea** — "How creative and novel is the concept and does the project differ from existing concepts?"

Score each criterion 1-5 under THREE lenses, one-line justification each:

- **Skeptical median judge** — judges may score from the video + text alone (per the official rules); assume nothing beyond what the 3-minute video, README, and form text make legible.
- **Most technically demanding panel voice** — rewards thin harnesses over frameworks ("if you rely on complex scaffolding … you are coping"), long-running autonomy with a verification loop the system itself owns, tests and review gates, software that installs and runs on the first try; penalizes scaffold-heavy wrappers, unrunnable repos, and shallow one-shot Codex usage.
- **Most product/impact-minded panel voice** — rewards a sharp wedge into a real workflow for a nameable audience, outcome-shaped agent delegation with human judgment preserved, quantified outcomes over vibes, papercut-free onboarding; penalizes me-too tools with no case for who uses them and demos that show activity but no outcome.

## 4. Evidence anchors — what this event's panel has publicly rewarded

All drawn from the event rules and the panel's public statements and past picks; treat as scoring heuristics.

- Actually-running software over proofs of concept — a prior OpenAI Codex hackathon's winner was a continuously running system with an explicit decision/evaluation layer
- Deep, visible, skilled Codex collaboration: AGENTS.md discipline, skills, /plan, /review, parallel agents — "thoroughly and skillfully" is the literal criterion, and the README's Codex-collaboration section is a rule requirement
- Simple, durable primitives; heavy orchestration frameworks read as coping
- A verification loop the system owns (tests, review gates, citation checks, honest failure states)
- A specific problem for a specific audience, with quantified outcomes ("X hours → Y")
- Human judgment preserved where it matters (approval gates, review steps)
- Complete, coherent, even delightful finish — README/onboarding quality IS product quality
- Past the "vibe-code limit": durable engineering, not a fragile prototype
- Open, forkable repos earn goodwill
- The 3-minute video and README must carry all four criteria BY THEMSELVES — judges are not required to test

## 5. Output format

1. **Score table**: criterion × lens (12 cells), each cell = score + one-line justification
2. **Top 3 most damaging findings**: what, where (file/line or video timestamp), severity (CRITICAL / major / minor), concrete fix
3. **Verdict**: PASS only if no criterion scores below 4 under any lens AND no CRITICAL finding is open. Otherwise FAIL, with the shortest path to PASS.

Tone contract: professional rubric review grounded in the criteria and public evidence. No flattery. Never present speculation as fact. If something cannot be verified from the repo, say so and score it conservatively.
