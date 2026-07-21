/** Live control chart and transparent investigation shell for the demo story. */

import { useEffect, useMemo, useState } from "react";

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
  events: MeasurementEvent[];
};

const WIDTH = 940;
const HEIGHT = 360;
const PAD = 42;

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

  useEffect(() => {
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const socket = new WebSocket(`${protocol}://${window.location.host}/ws/watch`);
    socket.onopen = () => setStreamStatus("online");
    socket.onclose = (event) => setStreamStatus(event.wasClean ? "complete" : "offline");
    socket.onerror = () => setStreamStatus("offline");
    socket.onmessage = (message) => {
      const payload = JSON.parse(message.data) as Snapshot | MeasurementEvent;
      if (payload.type === "snapshot") {
        const { events: initial, type: _type, ...metadata } = payload;
        setSnapshot(metadata);
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

      <section className="lower-grid">
        <article className="stage-card active">
          <div className="stage-number">01</div>
          <div>
            <p className="eyebrow">WATCH</p>
            <h3>{alert ? "Signal captured" : "Monitoring the line"}</h3>
            <p>Nelson Rules 1–3 evaluate every point. Statistics remain outside the agent.</p>
          </div>
        </article>
        <article className={`stage-card ${alert ? "queued" : ""}`}>
          <div className="stage-number">02</div>
          <div>
            <p className="eyebrow">INVESTIGATE</p>
            <h3>{alert ? (mode === "replay" ? "Recorded investigation queued" : "Codex investigator queued") : "Standing by"}</h3>
            <p>{snapshot?.investigator_status ?? "Checking live runtime prerequisites…"}</p>
          </div>
        </article>
        <article className="stage-card muted">
          <div className="stage-number">03</div>
          <div>
            <p className="eyebrow">LEARN</p>
            <h3>Human gate locked</h3>
            <p>No playbook changes without a reviewed diff and explicit approval.</p>
          </div>
        </article>
      </section>
    </main>
  );
}
