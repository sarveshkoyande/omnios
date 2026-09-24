import { useState } from "react";
import { AGENTS, PHASE_TINT, PHASES, type LibraryAgent, type Phase } from "../agents";
import { Icon } from "./Icon";

/** Read more: what the agent does, what it works from, and where it runs. An agent that is on
 *  the product list but not built yet says so instead of claiming live behaviour. */
function AgentDetail({ agent, onBack }: { agent: LibraryAgent; onBack: () => void }) {
  return (
    <div className="agent-library">
      <button type="button" className="agent-detail-back" onClick={onBack}><Icon name="arrowLeft" size={15} /> Back to Agent library</button>

      <div className="agent-detail-head">
        <span className="agent-icon agent-icon-lg"><Icon name={agent.icon} size={26} /></span>
        <h1>{agent.name}</h1>
        <p className="agent-detail-summary">{agent.summary}</p>
        {agent.inDevelopment && <span className="agent-status-pill">In development</span>}
      </div>

      <div className="agent-detail-grid">
        <section className="agent-detail-panel">
          <h2>What it does</h2>
          <p className="agent-detail-body">{agent.about}</p>
          {agent.inDevelopment && (
            <p className="agent-detail-panel-note">In development: not yet running in this app.</p>
          )}
        </section>

        {agent.worksFrom && agent.worksFrom.length > 0 && (
          <section className="agent-detail-panel">
            <h2>Works from</h2>
            <ul className="agent-source-list">
              {agent.worksFrom.map((s) => (
                <li key={s.label}>
                  <div className="agent-source-label">{s.label}</div>
                  <div className="agent-source-detail">{s.detail}</div>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>

      {agent.builtOn && <div className="agent-source">Built on {agent.builtOn}</div>}
    </div>
  );
}

function AgentCard({ agent, index, onOpen }: { agent: LibraryAgent; index: number; onOpen: () => void }) {
  const wip = agent.status === "wip";
  const body = (
    <>
      <div className="agent-card-top">
        <span className="agent-icon"><Icon name={agent.icon} size={20} /></span>
        {wip && <span className="agent-status-pill">WIP</span>}
      </div>
      <h3>{agent.name}</h3>
      <p className="agent-summary">{agent.summary}</p>
      {!wip && <span className="agent-read-more">Read more <Icon name="arrowRight" size={13} /></span>}
    </>
  );
  const style = { animationDelay: `${index * 30}ms` };
  if (wip) {
    return <div className="agent-card is-wip" style={style} aria-disabled="true">{body}</div>;
  }
  return <button type="button" className="agent-card" style={style} onClick={onOpen}>{body}</button>;
}

export function AgentLibrary() {
  const [phase, setPhase] = useState<Phase>("strategy");
  const [selected, setSelected] = useState<LibraryAgent | null>(null);
  const info = PHASES.find((p) => p.id === phase)!;

  if (selected) {
    return <AgentDetail agent={selected} onBack={() => setSelected(null)} />;
  }

  return (
    <div className="agent-library" style={{ ["--phase-ink" as string]: PHASE_TINT[phase] }}>
      <div className="agent-hero">
        <div className="agent-hero-eyebrow">Agent library</div>
        <h1>{info.label}</h1>
        <div className="phase-switcher" role="tablist">
          {PHASES.map((p) => (
            <button
              key={p.id}
              type="button"
              role="tab"
              aria-selected={phase === p.id}
              className={`phase-tab ${phase === p.id ? "active" : ""}`}
              onClick={() => setPhase(p.id)}
            >
              {p.label}
            </button>
          ))}
        </div>
        <p>{info.tagline}</p>
      </div>

      <div className="agent-grid" key={phase}>
        {AGENTS[phase].map((a, i) => (
          <AgentCard key={a.id} agent={a} index={i} onOpen={() => setSelected(a)} />
        ))}
      </div>
    </div>
  );
}
