import { useState } from "react";
import { AGENTS, PHASES, type AgentEntry, type Phase } from "../agents";

/** Per-phase accent ink only -- the neumorphic system keeps one flat page background
 *  throughout (no gradients on the root surface), so the phase "feel" comes from this one
 *  tinted colour applied to the active tab, the icon well glyph, and each card's job title,
 *  not from restyling the page itself. */
const PHASE_TINT: Record<Phase, { ink: string }> = {
  strategy: { ink: "#3B4E8C" },
  ops: { ink: "#206657" },
  intelligence: { ink: "#6B4FA0" },
};

function AgentDetail({ agent, phase, onBack }: { agent: AgentEntry; phase: Phase; onBack: () => void }) {
  const tint = PHASE_TINT[phase];
  return (
    <div className="agent-library" style={{ ["--phase-ink" as string]: tint.ink }}>
      <button type="button" className="agent-detail-back" onClick={onBack}>&#8592; Back to Agent library</button>

      <div className="agent-detail-head">
        <div className="agent-card-top">
          {agent.access === "write" ? (
            <span className="access-pill access-write">Can edit</span>
          ) : (
            <span className="access-pill access-read">Read only</span>
          )}
        </div>
        <h1>{agent.name}</h1>
        <p className="agent-detail-job">{agent.job}</p>
        <p className="agent-detail-body">{agent.detail}</p>
      </div>

      <div className="agent-detail-grid">
        <section className="agent-detail-panel">
          <h2>What it's doing</h2>
          <p className="agent-detail-panel-note">
            Illustrative recent activity -- this app doesn't run a live activity log yet, so
            these are representative examples of this agent's real job, not a live feed.
          </p>
          <ul className="agent-activity-list">
            {agent.activity.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </section>

        <section className="agent-detail-panel">
          <h2>Where it gets information from</h2>
          <ul className="agent-source-list">
            {agent.sources.map((s) => (
              <li key={s.label}>
                <div className="agent-source-label">{s.label}</div>
                <div className="agent-source-detail">{s.detail}</div>
              </li>
            ))}
          </ul>
        </section>
      </div>

      <div className="agent-source">{agent.source}</div>
    </div>
  );
}

export function AgentLibrary() {
  const [phase, setPhase] = useState<Phase>("strategy");
  const [selected, setSelected] = useState<AgentEntry | null>(null);
  const tint = PHASE_TINT[phase];
  const info = PHASES.find((p) => p.id === phase)!;
  const agents = AGENTS[phase];

  if (selected) {
    return <AgentDetail agent={selected} phase={phase} onBack={() => setSelected(null)} />;
  }

  return (
    <div className="agent-library" style={{ ["--phase-ink" as string]: tint.ink }}>
      <div className="agent-hero">
        <div className="agent-hero-eyebrow">Agent library</div>
        <h1>Every capability, to deliver successful campaigns.</h1>
        <p>Three workspaces. Every agent underneath them, named, with what it actually does.</p>
      </div>

      <div className="phase-switcher">
        {PHASES.map((p) => (
          <button
            key={p.id}
            type="button"
            className={`phase-tab ${phase === p.id ? "active" : ""}`}
            onClick={() => setPhase(p.id)}
          >
            {p.label}
          </button>
        ))}
      </div>

      <div className="phase-tagline">{info.tagline}</div>

      <div className="agent-grid">
        {agents.map((a, i) => (
          <div className="agent-card" key={a.id} style={{ animationDelay: `${i * 40}ms` }}>
            <div className="agent-card-top">
              <button
                type="button"
                className={`access-pill access-pill-btn ${a.access === "write" ? "access-write" : "access-read"}`}
                onClick={() => setSelected(a)}
              >
                Read more &#8594;
              </button>
            </div>
            <h3>{a.name}</h3>
            <p className="agent-job">{a.job}</p>
            <p className="agent-detail">{a.detail}</p>
            <div className="agent-source">{a.source}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
