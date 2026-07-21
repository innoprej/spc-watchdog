# SPC Watchdog — 2:54 demo script

## Capture evidence

- Canonical Scenario 1 live run: one attempt, 20 verified citations, 41.7 seconds of investigator runtime.
- Canonical Scenario 2 v1 live run: one attempt, 20 verified citations, six MCP calls including irrelevant genealogy and inspection before tool-life.
- Human-approved Scenario 2 v2 run after reset: one attempt, 11 verified citations, four MCP calls, with tool-life immediately after equipment and no material branch.
- Final fixture-driven source footage: 1920×1080 WebM, 69.12 seconds for Scenario 1 and 142.80 seconds for the corrected Scenario 2 v1→v2 flow.
- Rehearsed edit duration: 174 seconds. The cut uses the actual fixture footage, removes idle intervals, and preserves the visible `DETERMINISTIC REPLAY` badge during accelerated pickup shots.
- Final rendered deliverable: `../captures/phase3-canonical-20260722/final-package/spc-watchdog-build-week-final.mp4`, 1920×1080 H.264/AAC, exactly 174.000 seconds.
- The English narration was rendered locally in eleven timestamped segments; the two overlong segments received only the minimum tempo correction needed to stay inside their caption windows.
- The corrected LEARN cut holds the pending proposal from 01:45–02:06, shows the source recording's approval-to-v2 transition during 02:06–02:24, and starts the compressed v2 trace at 02:24.
- A full FFmpeg decode of both final streams completed with zero errors. An independent frame-and-audio review passed the corrected timing, and the four README stills were exported from this accepted MP4.

## Timed edit and narration

| Time | Picture from actual footage | Narration |
| --- | --- | --- |
| 00:00–00:10 | Product title, stable chart, honest simulation clock | Manufacturing teams already know when a process goes out of control. The expensive part is proving why before the line loses more production. |
| 00:10–00:24 | Scenario 1 chart accumulates; Rule 1 point turns red | SPC Watchdog separates that job into three layers. WATCH is deterministic code: one real second equals one simulated hour, and no model decides whether a Nelson rule fired. |
| 00:24–00:45 | Scenario 1 activity feed: exact OCAP load, chart context, equipment query | The signal launches a Codex investigator running on GPT-5.6 Sol. It receives the complete OCAP skill through MCP, inside a sterile database-free workspace, with only five registered broker tools. |
| 00:45–01:00 | Equipment eliminated; genealogy and inspection evidence arrive | Every hypothesis step and tool call is visible. Equipment is clean. A new material lot arrived two simulated hours before the shift, and incoming inspection confirms it was accepted marginal. |
| 01:00–01:12 | Verified Scenario 1 report and row citations | The model cannot publish this verdict by itself. A deterministic gate re-reads every cited row, field, and value from SQLite. Only the verified report renders. |
| 01:12–01:27 | Scenario 2 trend develops; Rule 3 turns chart red | Now the harder case: a deterministic Rule 3 trend. The version-one playbook checks recent equipment events, then wastes time on material genealogy and inspection. |
| 01:27–01:45 | V1 trace reaches tool-life last; tool-wear report | Tool-life finally exposes the cause: nine thousand nine hundred eighty cycles against a ten-thousand-cycle replacement limit. The verdict is verified—but the investigation also discovered its own playbook gap. |
| 01:45–02:06 | Grounded proposal card and unified diff | The agent files a change proposal, not a silent self-edit. It names the exact base version, explains the gap with row-level evidence, and proposes checking tool-life before unrelated material branches. |
| 02:06–02:24 | Human clicks approve; v2 activation confirmation | A human reviews the diff and approves it. The transaction supersedes version one, creates an immutable version two, and preserves that active version across the scenario reset. |
| 02:24–02:43 | V2 skill load and shorter trace; no genealogy call | On the re-run, the feed proves the exact version-two body reached the model. Tool-life follows equipment immediately. Four calls replace six, and the irrelevant genealogy branch disappears. |
| 02:43–02:54 | 6→4 comparison, three-layer rail, final product frame | It watches with statistics, investigates with a transparent Codex agent, and learns only with human approval. SPC Watchdog: it watches, investigates, and learns. |

## Edit notes

- Keep WATCH’s red transition, the first tool trace, the citation badge, the proposal diff, the approval-to-v2 state transition, and the v2 skill-load line legible.
- Accelerate only idle event gaps and pickup shots. Keep `DETERMINISTIC REPLAY` and the selected 1×/2×/4× control visible whenever replay footage is used.
- Use the Scenario 1 source for 00:00–01:12 and Scenario 2 source for 01:12–02:54. The table totals 174 seconds.
- Hold the proposal card rather than advancing into v2 early; compress only the v2 event gaps so skill delivery, equipment, tool-life, the verified report, and the 6→4 comparison all remain in order.
- Captions are in `docs/video-script.srt`; narration text must remain synchronized with that file.
