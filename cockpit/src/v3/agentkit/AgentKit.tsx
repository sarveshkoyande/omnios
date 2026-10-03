import { useEffect, useRef } from "react";
import { Icon } from "../../components/Icon";
import "./agentkit.css";

/** Shared pieces for step-by-step agents (Brand IQ Agent, Signal Scout): the acknowledgement card the
 *  agent shows before it builds, the progress list (only finished steps + the current one), and the
 *  Live reasoning slide-in panel (same look as the Campaign Agent's). */

export type SkillStatus = "idle" | "running" | "done" | "error";
export interface AgentStep { id: string; name: string; skills: string[] }
export interface Ack {
  mode?: string; understood?: string; question?: string;
  have?: { what: string; detail?: string }[];
  missing?: { what: string; impact?: string }[];
  approach?: string[];
}
export interface ReasonEntry { id: string; title: string; status: SkillStatus; lines: string[]; error?: string }

export function AckCard({ ack, onConfirm, onEdit }: { ack: Ack; onConfirm: () => void; onEdit: () => void }) {
  return (
    <section className="v3-ak-ack">
      <div className="v3-ak-ack-head"><Icon name="sparkles" size={14} /><b>Here's what I've got</b></div>
      {ack.understood && <p>{ack.understood}</p>}
      {(ack.have ?? []).length > 0 && (
        <div className="v3-ak-list have">
          <em>Available</em>
          {ack.have!.map((h, i) => <div key={i}><Icon name="check" size={10} /><span><b>{h.what}</b>{h.detail ? ` — ${h.detail}` : ""}</span></div>)}
        </div>
      )}
      {(ack.missing ?? []).length > 0 && (
        <div className="v3-ak-list missing">
          <em>Not available</em>
          {ack.missing!.map((m, i) => <div key={i}><span className="v3-ak-x">–</span><span><b>{m.what}</b>{m.impact ? ` — ${m.impact}` : ""}</span></div>)}
        </div>
      )}
      {(ack.approach ?? []).length > 0 && (
        <div className="v3-ak-list">
          <em>How I'll build it</em>
          <ol>{ack.approach!.map((a, i) => <li key={i}>{a}</li>)}</ol>
        </div>
      )}
      {ack.question && <p className="v3-ak-q">{ack.question}</p>}
      <div className="v3-ak-ack-actions">
        <button type="button" className="v3-cc-btn primary" onClick={onConfirm}>Looks good, build it</button>
        <button type="button" className="v3-cc-btn" onClick={onEdit}>Let me add more</button>
      </div>
    </section>
  );
}

/** Finished steps as compact rows, the current step expanded with its sub-tasks so far; later steps hidden. */
export function StepProgress({ steps, skillNames, status, currentStep, done }: {
  steps: AgentStep[]; skillNames: Record<string, string>; status: Record<string, SkillStatus>;
  currentStep: number; done: boolean;
}) {
  return (
    <div className="v3-ak-progress">
      {steps.map((st, i) => {
        if (i > currentStep && !done) return null;
        const finished = done || i < currentStep;
        const failed = st.skills.filter((k) => status[k] === "error").length;
        if (finished) {
          return (
            <div key={st.id} className="v3-ak-row done">
              <span className="v3-ak-dot"><Icon name="check" size={9} /></span>
              <b>{st.name}</b>
              {failed > 0 && <small className="v3-ak-warn">{failed} part{failed > 1 ? "s" : ""} didn't finish</small>}
            </div>
          );
        }
        return (
          <div key={st.id} className="v3-ak-row current">
            <div className="v3-ak-row-head"><span className="v3-ak-dot"><span className="v3-cc-spinner small" /></span><b>{st.name}</b></div>
            <ul>
              {st.skills.filter((k) => (status[k] ?? "idle") !== "idle").map((k) => (
                <li key={k} className={status[k]}>
                  {status[k] === "running" ? <span className="v3-cc-spinner small" /> : status[k] === "done" ? <Icon name="check" size={9} /> : <span className="v3-ak-x">!</span>}
                  {skillNames[k] ?? k}{status[k] === "running" ? "…" : ""}
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}

export function ReasoningPanel({ entries, live, onClose }: { entries: ReasonEntry[]; live: boolean; onClose: () => void }) {
  const body = useRef<HTMLDivElement>(null);
  const total = entries.reduce((n, e) => n + e.lines.length + (e.status === "running" ? 1 : 0), 0);
  useEffect(() => { if (body.current) body.current.scrollTop = body.current.scrollHeight; }, [total]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <aside className="v3-refine v3-cc-reason" aria-label="Live reasoning">
      <div className="v3-refine-head">
        <b><Icon name="eye" size={14} /> Live reasoning{live && <span className="v3-cc-live-dot" />}</b>
        <button type="button" aria-label="Close" onClick={onClose}><Icon name="close" size={13} /></button>
      </div>
      <div className="v3-refine-body" ref={body}>
        {entries.length === 0 && <p className="v3-muted">The agent's reasoning appears here as it works.</p>}
        {entries.map((e) => (
          <div key={e.id} className="v3-cc-reason-card">
            <b>{e.title}</b>
            {e.status === "running" && <div className="v3-ask-thinking"><span /><span /><span /></div>}
            {e.lines.length > 0 && <ul className="v3-ak-lines">{e.lines.map((l, i) => <li key={i}>{l}</li>)}</ul>}
            {e.status === "error" && <p className="v3-cc-banner error">{e.error}</p>}
          </div>
        ))}
      </div>
    </aside>
  );
}

export function ReasoningButton({ live, onClick }: { live: boolean; onClick: () => void }) {
  return (
    <button type="button" className="v3-ak-reason-btn" onClick={onClick}>
      <Icon name="eye" size={13} /> Live reasoning{live && <span className="v3-cc-live-dot" />}
    </button>
  );
}
