/** Live control chart and transparent investigation shell for the demo story. */

import { useEffect, useMemo, useRef, useState } from "react";

type Violation = {
  rule: number;
  start_index: number;
  end_index: number;
  direction: string;
  observed: number;
  limit: number | null;
};

type MeasurementPoint = {
  id: string;
  sequence: number;
  sim_hour: number;
  sim_timestamp: string;
  value: number;
  lot_id: string;
};

type Incident = {
  id: string;
  opened_sim_hour: number;
  primary_rule: number;
  status: string;
};

type MeasurementEvent = {
  schema_version: string;
  type: "measurement";
  sequence: number;
  point: MeasurementPoint;
  violations: Violation[];
  incident: Incident | null;
};

type Snapshot = {
  type: "snapshot";
  mode: "live" | "replay";
  scenario: string;
  sim_rate_label: string;
  center: number;
  sigma: number;
  investigator_status: string;
  replay_speed?: number | null;
  events: MeasurementEvent[];
};

type RunEvent = {
  schema_version: string;
  run_id: string;
  sequence: number;
  recorded_at: string;
  type: string;
  payload: Record<string, unknown>;
};

type Citation = {
  id: string;
  table: string;
  field: string;
  value: string | number | boolean | null;
};

type Claim = {
  text: string;
  citations: Citation[];
};

type InvestigationReport = {
  schema_version: string;
  incident_id: string;
  status: string;
  claims: Claim[];
  root_cause: Claim;
};

type SkillProposal = {
  id: string;
  base_version_id: string;
  status: string;
  rationale: string;
  evidence: Citation[];
  proposed_step: string;
  patch: string;
};

type InvestigationMessage = {
  type: string;
  status?: string;
  events?: RunEvent[];
  event?: RunEvent;
  report?: InvestigationReport | null;
  proposal?: SkillProposal | null;
  replay_phase?: string | null;
  active_skill_version?: number;
};

const WIDTH = 940;
const HEIGHT = 360;
const PAD = 42;

function mergeRunEvents(current: RunEvent[], incoming: RunEvent[]) {
  const bySequence = new Map(current.map((event) => [event.sequence, event]));
  incoming.forEach((event) => bySequence.set(event.sequence, event));
  return [...bySequence.values()].sort((left, right) => left.sequence - right.sequence);
}

function eventPresentation(event: RunEvent, rejectedAttempts: Set<number>) {
  const { payload } = event;
  const text = typeof payload.text === "string" ? payload.text : "";
  if (event.type === "skill_load") {
    return {
      label: "OCAP SKILL LOADED",
      detail: `${String(payload.name)} v${String(payload.version)} · exact body delivered through MCP`,
      tone: "skill",
    };
  }
  if (event.type === "hypothesis") {
    return { label: "HYPOTHESIS", detail: text, tone: "hypothesis" };
  }
  if (event.type === "tool_call") {
    return {
      label: `BROKER TOOL · ${String(payload.tool)}`,
      detail: "Allowlisted evidence query started",
      tone: "tool",
    };
  }
  if (event.type === "evidence") {
    const result = payload.result as Record<string, unknown> | undefined;
    const structured = result?.structured_content as Record<string, unknown> | undefined;
    const rows = Array.isArray(structured?.result)
      ? (structured.result as Record<string, unknown>[])
      : [];
    const ids = rows.map((row) => String(row.id ?? "row")).join(", ");
    return {
      label: `EVIDENCE · ${String(payload.tool)}`,
      detail: `${rows.length} scoped row${rows.length === 1 ? "" : "s"} returned${ids ? ` · ${ids}` : ""}`,
      tone: "evidence",
    };
  }
  if (event.type === "verifier") {
    const passed = payload.passed === true;
    const failures = Array.isArray(payload.failures)
      ? (payload.failures as Record<string, unknown>[])
      : [];
    const firstFailure = failures[0];
    const citation = firstFailure?.citation as Record<string, unknown> | undefined;
    const rejectedAnchor = citation
      ? `${String(citation.table)}/${String(citation.id)}.${String(citation.field)}`
      : "structured report";
    const attempt = Number(payload.attempt ?? 0);
    return {
      label: passed
        ? "CITATIONS VERIFIED"
        : attempt >= 2
          ? "CLAIM REJECTED · RETRY EXHAUSTED"
          : "VERIFICATION REJECTED · RETRYING",
      detail: passed
        ? `${String(payload.citation_count ?? 0)} row-level citations rechecked against the factory database`
        : `${String(firstFailure?.claim ?? "Unverified claim")} · ${rejectedAnchor}${failures.length > 1 ? ` · +${failures.length - 1} more` : ""}`,
      tone: passed ? "verified" : "rejected",
    };
  }
  if (event.type === "decision") {
    const rejected = rejectedAttempts.has(Number(payload.attempt));
    return {
      label: rejected ? "REJECTED MODEL CONCLUSION" : "MODEL CONCLUSION · PENDING GATE",
      detail: text,
      tone: rejected ? "rejected" : "decision",
    };
  }
  if (event.type === "proposal") {
    return {
      label: "SKILL CHANGE PROPOSED",
      detail: `${String(payload.base_version_id)} · human approval required`,
      tone: "proposal",
    };
  }
  if (event.type === "runtime_error" || event.type === "skill_load_rejected") {
    return {
      label: "FAIL-CLOSED",
      detail: String(payload.reason ?? "Runtime boundary rejected this event"),
      tone: "rejected",
    };
  }
  return {
    label: "RUN CONTROL",
    detail: String(payload.state ?? payload.source ?? event.type),
    tone: "status",
  };
}

function chartCoordinates(events: MeasurementEvent[], center: number, sigma: number) {
  const visible = events.slice(-32);
  const minimum = center - sigma * 4.2;
  const maximum = center + sigma * 4.2;
  const x = (index: number) =>
    PAD + (index / Math.max(visible.length - 1, 1)) * (WIDTH - PAD * 2);
  const y = (value: number) =>
    PAD + ((maximum - value) / (maximum - minimum)) * (HEIGHT - PAD * 2);
  return { visible, x, y };
}

function ControlChart({
  events,
  center,
  sigma,
  alert,
}: {
  events: MeasurementEvent[];
  center: number;
  sigma: number;
  alert: boolean;
}) {
  const { visible, x, y } = chartCoordinates(events, center, sigma);
  const points = visible.map((event, index) => `${x(index)},${y(event.point.value)}`).join(" ");
  const lines = [
    { label: "+3σ", value: center + sigma * 3, danger: true },
    { label: "CENTER", value: center, danger: false },
    { label: "−3σ", value: center - sigma * 3, danger: true },
  ];

  return (
    <div className={`chart-shell ${alert ? "is-alert" : ""}`}>
      <div className="panel-heading">
        <div>
          <p className="eyebrow">WATCH / CHARACTERISTIC 01</p>
          <h2>Press-fit diameter</h2>
        </div>
        <div className="chart-reading">
          <span>LIVE READING</span>
          <strong>{events.at(-1)?.point.value.toFixed(4) ?? "—"}</strong>
          <small>mm</small>
        </div>
      </div>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label="Live SPC control chart">
        <defs>
          <pattern id="grid" width="47" height="36" patternUnits="userSpaceOnUse">
            <path d="M 47 0 L 0 0 0 36" fill="none" className="chart-grid" />
          </pattern>
          <filter id="signal-glow" x="-100%" y="-100%" width="300%" height="300%">
            <feGaussianBlur stdDeviation="5" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>
        <rect x="0" y="0" width={WIDTH} height={HEIGHT} fill="url(#grid)" />
        {lines.map((line) => (
          <g key={line.label}>
            <line
              x1={PAD}
              x2={WIDTH - PAD}
              y1={y(line.value)}
              y2={y(line.value)}
              className={line.danger ? "limit-line" : "center-line"}
            />
            <text x={WIDTH - PAD + 6} y={y(line.value) + 4} className="axis-label">
              {line.label}
            </text>
          </g>
        ))}
        <polyline points={points} className="measure-line" />
        {visible.map((event, index) => {
          const signaled = event.violations.length > 0;
          return (
            <circle
              key={event.point.id}
              cx={x(index)}
              cy={y(event.point.value)}
              r={signaled ? 7 : 3.8}
              className={signaled ? "signal-point" : "measure-point"}
              filter={signaled ? "url(#signal-glow)" : undefined}
            />
          );
        })}
      </svg>
      <div className="chart-footer">
        <span>UCL {(center + sigma * 3).toFixed(2)}</span>
        <span>μ {center.toFixed(2)}</span>
        <span>LCL {(center - sigma * 3).toFixed(2)}</span>
        <span>{events.length} samples observed</span>
      </div>
    </div>
  );
}

export default function App() {
  const [events, setEvents] = useState<MeasurementEvent[]>([]);
  const [snapshot, setSnapshot] = useState<Omit<Snapshot, "events" | "type"> | null>(null);
  const [streamStatus, setStreamStatus] = useState<"connecting" | "online" | "complete" | "offline">("connecting");
  const [investigationEvents, setInvestigationEvents] = useState<RunEvent[]>([]);
  const [investigationStatus, setInvestigationStatus] = useState("standing-by");
  const [investigationConnection, setInvestigationConnection] = useState<"idle" | "connecting" | "online" | "complete" | "offline">("idle");
  const [report, setReport] = useState<InvestigationReport | null>(null);
  const [proposal, setProposal] = useState<SkillProposal | null>(null);
  const [replaySpeed, setReplaySpeed] = useState(1);
  const [replayPhase, setReplayPhase] = useState<string | null>(null);
  const [activeSkillVersion, setActiveSkillVersion] = useState(1);
  const [approvalState, setApprovalState] = useState("pending-review");
  const [investigationGeneration, setInvestigationGeneration] = useState(0);
  const lastInvestigationSequence = useRef(0);
  const activityFeed = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const socket = new WebSocket(`${protocol}://${window.location.host}/ws/watch`);
    let streamErrored = false;
    socket.onopen = () => setStreamStatus("online");
    socket.onclose = () => setStreamStatus(streamErrored ? "offline" : "complete");
    socket.onerror = () => {
      streamErrored = true;
      setStreamStatus("offline");
    };
    socket.onmessage = (message) => {
      const payload = JSON.parse(message.data) as Snapshot | MeasurementEvent;
      if (payload.type === "snapshot") {
        const { events: initial, type: _type, ...metadata } = payload;
        setSnapshot(metadata);
        setReplaySpeed(metadata.replay_speed ?? 1);
        setEvents(initial);
      } else {
        setEvents((current) => [...current, payload]);
      }
    };
    return () => socket.close();
  }, []);

  const firstSignal = useMemo(
    () => events.find((event) => event.violations.length > 0),
    [events],
  );
  const current = events.at(-1);
  const alert = Boolean(firstSignal);
  const incident = events.find((event) => event.incident)?.incident;
  const mode = snapshot?.mode ?? "live";

  useEffect(() => {
    if (!incident?.id) return;
    let cancelled = false;
    let finished = false;
    let reconnectTimer: number | undefined;
    let activeSocket: WebSocket | undefined;
    lastInvestigationSequence.current = 0;
    setInvestigationEvents([]);
    setReport(null);
    setProposal(null);
    setInvestigationStatus("queued");

    const connect = () => {
      setInvestigationConnection("connecting");
      const protocol = window.location.protocol === "https:" ? "wss" : "ws";
      const cursor = lastInvestigationSequence.current;
      const socket = new WebSocket(
        `${protocol}://${window.location.host}/ws/investigate/${incident.id}?after=${cursor}`,
      );
      activeSocket = socket;
      socket.onopen = () => setInvestigationConnection("online");
      socket.onerror = () => setInvestigationConnection("offline");
      socket.onmessage = (message) => {
        const payload = JSON.parse(message.data) as InvestigationMessage;
        if (payload.type === "investigation_snapshot") {
          const incoming = payload.events ?? [];
          setInvestigationEvents((current) => mergeRunEvents(current, incoming));
          incoming.forEach((event) => {
            lastInvestigationSequence.current = Math.max(
              lastInvestigationSequence.current,
              event.sequence,
            );
          });
          setInvestigationStatus(payload.status ?? "investigating");
          if (payload.report) setReport(payload.report);
          if (payload.proposal) setProposal(payload.proposal);
          if (payload.replay_phase !== undefined) setReplayPhase(payload.replay_phase ?? null);
          if (payload.active_skill_version) setActiveSkillVersion(payload.active_skill_version);
          finished = ["completed", "inconclusive", "failed"].includes(
            payload.status ?? "",
          );
        } else if (payload.type === "investigation_event" && payload.event) {
          setInvestigationEvents((current) => mergeRunEvents(current, [payload.event!]));
          lastInvestigationSequence.current = Math.max(
            lastInvestigationSequence.current,
            payload.event.sequence,
          );
          setInvestigationStatus(payload.status ?? "investigating");
        } else if (payload.type === "investigation_finished") {
          setInvestigationStatus(payload.status ?? "complete");
          if (payload.report) setReport(payload.report);
          if (payload.proposal) setProposal(payload.proposal);
          if (payload.replay_phase !== undefined) setReplayPhase(payload.replay_phase ?? null);
          if (payload.active_skill_version) setActiveSkillVersion(payload.active_skill_version);
          finished = true;
        } else if (
          payload.type === "investigation_unavailable" ||
          payload.type === "investigation_not_found"
        ) {
          setInvestigationStatus("unavailable");
          finished = true;
        }
      };
      socket.onclose = () => {
        setInvestigationConnection(finished ? "complete" : "offline");
        if (!cancelled && !finished) reconnectTimer = window.setTimeout(connect, 750);
      };
    };

    connect();
    return () => {
      cancelled = true;
      activeSocket?.close();
      if (reconnectTimer !== undefined) window.clearTimeout(reconnectTimer);
    };
  }, [incident?.id, investigationGeneration]);

  const changeReplaySpeed = async (speed: number) => {
    const response = await fetch(`/api/replay/speed/${speed}`, { method: "POST" });
    if (response.ok) setReplaySpeed(speed);
  };

  const decideProposal = async (decision: "approve" | "reject") => {
    if (!proposal) return;
    setApprovalState(decision === "approve" ? "approving" : "rejecting");
    const response = await fetch(`/api/proposals/${proposal.id}/${decision}`, {
      method: "POST",
    });
    if (!response.ok) {
      setApprovalState("failed");
      return;
    }
    const result = await response.json() as Record<string, unknown>;
    setApprovalState(String(result.status ?? decision));
    setProposal((current) => current
      ? { ...current, status: String(result.status ?? decision) }
      : current);
    if (decision === "approve") {
      setActiveSkillVersion(2);
      if (mode === "replay") {
        lastInvestigationSequence.current = 0;
        setInvestigationEvents([]);
        setReport(null);
        setProposal(null);
        setReplayPhase("v2");
        setInvestigationGeneration((current) => current + 1);
      }
    }
  };

  const verifiedEvent = [...investigationEvents]
    .reverse()
    .find((event) => event.type === "verifier" && event.payload.passed === true);
  const citationCount = Number(verifiedEvent?.payload.citation_count ?? 0);
  const inconclusive = report?.status === "insufficient-evidence";
  const rejectedAttempts = new Set(
    investigationEvents
      .filter((event) => event.type === "verifier" && event.payload.passed === false)
      .map((event) => Number(event.payload.attempt)),
  );

  useEffect(() => {
    const feed = activityFeed.current;
    if (feed) feed.scrollTop = feed.scrollHeight;
  }, [investigationEvents.length]);

  return (
    <main className={alert ? "control-room alert-state" : "control-room"}>
      <header className="masthead">
        <div className="identity-block">
          <div className="watchdog-mark" aria-hidden="true"><span /></div>
          <div>
            <p className="eyebrow">AUTONOMOUS QUALITY ENGINEER</p>
            <h1>SPC WATCHDOG</h1>
          </div>
        </div>
        <div className="status-strip">
          {mode === "replay" && <span className="mode-badge replay">DETERMINISTIC REPLAY</span>}
          {mode === "replay" && (
            <div className="speed-control" aria-label="Replay speed">
              {[1, 2, 4].map((speed) => (
                <button
                  className={replaySpeed === speed ? "active" : ""}
                  key={speed}
                  onClick={() => void changeReplaySpeed(speed)}
                  type="button"
                >
                  {speed}×
                </button>
              ))}
            </div>
          )}
          <span className="mode-badge simulation">SIMULATION</span>
          <span className={`connection ${streamStatus === "online" || streamStatus === "complete" ? "online" : ""}`}>
            <i /> {streamStatus === "online" ? "STREAM ONLINE" : streamStatus === "complete" ? "STREAM COMPLETE" : streamStatus === "offline" ? "STREAM OFFLINE" : "CONNECTING"}
          </span>
        </div>
      </header>

      <section className="clock-rail" aria-label="Simulation clock">
        <div>
          <span className="rail-label">SIMULATION CLOCK</span>
          <strong>{current?.point.sim_timestamp.slice(11, 16) ?? "—:—"}</strong>
          <small>{current?.point.sim_timestamp.slice(0, 10) ?? "WAITING FOR STREAM"}</small>
        </div>
        <div className="clock-rate">
          <span>TIME COMPRESSION</span>
          <b>{snapshot?.sim_rate_label ?? "1 real second = 1 simulated hour"}</b>
        </div>
        <div className="line-id">
          <span>ASSET</span>
          <b>LINE 07 / PRESS 07</b>
        </div>
      </section>

      <section className="primary-grid">
        <ControlChart
          events={events}
          center={snapshot?.center ?? 10}
          sigma={snapshot?.sigma ?? 0.25}
          alert={alert}
        />

        <aside className={`verdict-panel ${alert ? "is-alert" : ""}`}>
          <p className="eyebrow">DETERMINISTIC VERDICT</p>
          <div className="verdict-icon"><span>{alert ? "!" : "✓"}</span></div>
          <h2>{alert ? "OUT OF CONTROL" : "PROCESS STABLE"}</h2>
          <p className="verdict-copy">
            {alert
              ? `Nelson Rule ${firstSignal?.violations[0].rule} fired at simulated hour ${firstSignal?.point.sim_hour}.`
              : "No Nelson rule violations in the observed window."}
          </p>
          <dl>
            <div><dt>Decision source</dt><dd>Deterministic code</dd></div>
            <div><dt>Model involved</dt><dd>None</dd></div>
            <div><dt>Incident</dt><dd>{incident?.id ?? "Not opened"}</dd></div>
          </dl>
        </aside>
      </section>

      <section className="investigation-grid">
        <article className={`activity-panel ${alert ? "is-active" : ""}`}>
          <div className="investigation-heading">
            <div>
              <p className="eyebrow">INVESTIGATE / {mode === "replay" ? "RECORDED CODEX TRACE" : "LIVE CODEX TRACE"}</p>
              <h2>Agent activity</h2>
            </div>
            <div className={`run-state ${investigationStatus}`}>
              <i /> {alert ? investigationStatus.replaceAll("-", " ") : "WAITING FOR SIGNAL"}
            </div>
          </div>
          <div className="activity-feed" aria-live="polite" ref={activityFeed}>
            {investigationEvents.length === 0 ? (
              <div className="feed-empty">
                <span>02</span>
                <p>
                  {alert
                    ? `Investigator ${investigationConnection === "offline" ? "reconnecting" : "is entering the sterile runtime"}…`
                    : "The deterministic engine will hand off an incident when a Nelson rule fires."}
                </p>
              </div>
            ) : (
              investigationEvents.map((event) => {
                const presentation = eventPresentation(event, rejectedAttempts);
                return (
                  <div
                    className={`activity-event ${presentation.tone}`}
                    key={`${event.run_id}-${event.sequence}`}
                  >
                    <span className="event-sequence">{String(event.sequence).padStart(2, "0")}</span>
                    <div>
                      <b>{presentation.label}</b>
                      <p>{presentation.detail}</p>
                    </div>
                    {event.payload.attempt !== undefined && (
                      <small>A{String(event.payload.attempt)}</small>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </article>

        <aside className={`report-panel ${report ? (inconclusive ? "is-inconclusive" : "is-verified") : ""}`}>
          <div className="investigation-heading">
            <div>
              <p className="eyebrow">INCIDENT REPORT</p>
              <h2>{report ? (inconclusive ? "Verified — inconclusive" : "Verified conclusion") : "Verification gate"}</h2>
            </div>
            {report && (
              <span className="verified-badge">✓ {citationCount} CITATIONS VERIFIED</span>
            )}
          </div>
          {report ? (
            <div className="report-content">
              <section className="root-cause">
                <span>{inconclusive ? "EVIDENCE LIMIT / NO ROOT CAUSE CONCLUDED" : "ROOT CAUSE / ELIMINATE-OR-IMPLICATE"}</span>
                <p>{report.root_cause.text}</p>
                <div className="citation-row">
                  {report.root_cause.citations.map((citation) => (
                    <code key={`${citation.table}-${citation.id}-${citation.field}`}>
                      {citation.table} · {citation.id} · {citation.field} = {String(citation.value)}
                    </code>
                  ))}
                </div>
              </section>
              <div className="claim-list">
                {report.claims.map((claim, index) => (
                  <section className="claim" key={`${claim.text}-${index}`}>
                    <span>{String(index + 1).padStart(2, "0")}</span>
                    <div>
                      <p>{claim.text}</p>
                      <small>{claim.citations.length} row-level source{claim.citations.length === 1 ? "" : "s"}</small>
                    </div>
                  </section>
                ))}
              </div>
            </div>
          ) : (
            <div className="report-locked">
              <div>⌁</div>
              <h3>Nothing renders before verification.</h3>
              <p>
                In live mode, every model-supplied table, row, field, and value is re-read
                from SQLite. Replay renders only the recorded gate result.
              </p>
            </div>
          )}
        </aside>
      </section>

      {(proposal || activeSkillVersion > 1) && (
        <section className={`learn-panel ${activeSkillVersion > 1 ? "is-approved" : ""}`}>
          <div className="learn-summary">
            <p className="eyebrow">LEARN / HUMAN-GATED OCAP CHANGE</p>
            <h2>
              {activeSkillVersion > 1
                ? "OCAP v2 active — next investigation starts smarter"
                : "The investigator found a gap in its playbook"}
            </h2>
            {proposal ? (
              <>
                <p>{proposal.rationale}</p>
                <div className="proposal-meta">
                  <span>BASE {proposal.base_version_id}</span>
                  <span>{proposal.evidence.length} VERIFIED EVIDENCE ROWS</span>
                  <span>STATUS {proposal.status.toUpperCase()}</span>
                </div>
                <div className="approval-actions">
                  <button
                    className="approve-button"
                    disabled={proposal.status !== "pending" || approvalState === "approving"}
                    onClick={() => void decideProposal("approve")}
                    type="button"
                  >
                    APPROVE &amp; ACTIVATE V2
                  </button>
                  <button
                    className="reject-button"
                    disabled={proposal.status !== "pending" || approvalState === "rejecting"}
                    onClick={() => void decideProposal("reject")}
                    type="button"
                  >
                    REJECT
                  </button>
                </div>
              </>
            ) : (
              <p className="approval-confirmation">
                ✓ Immutable v2 approved. Reset preserved the active version; replay phase {replayPhase ?? "v2"} loaded it through MCP.
              </p>
            )}
          </div>
          <div className="diff-panel">
            <span>{proposal ? "PROPOSED SKILL DIFF" : "MEASURED IMPROVEMENT"}</span>
            {proposal ? (
              <pre>{proposal.patch}</pre>
            ) : (
              <div className="improvement-grid">
                <div><b>V1</b><strong>6 calls</strong><small>genealogy before tool-life</small></div>
                <div className="improvement-arrow">→</div>
                <div><b>V2</b><strong>4 calls</strong><small>tool-life immediately after equipment</small></div>
              </div>
            )}
          </div>
        </section>
      )}

      <section className="stage-rail" aria-label="Product architecture">
        <div className="stage-chip complete"><b>01 WATCH</b><span>Deterministic Nelson engine</span></div>
        <div className={`stage-chip ${alert ? "current" : ""}`}><b>02 INVESTIGATE</b><span>Codex · GPT-5.6 Sol · MCP broker</span></div>
        <div className={`stage-chip ${proposal ? "current" : activeSkillVersion > 1 ? "complete" : ""}`}><b>03 LEARN</b><span>{activeSkillVersion > 1 ? "v2 active · human approved" : "Human approval required"}</span></div>
      </section>
    </main>
  );
}
