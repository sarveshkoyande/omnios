import { useEffect, useRef, useState } from "react";
import { Icon } from "../../components/Icon";
import type { CCAgent, CCItem } from "./api";
import { Rich } from "./Rich";

type PipelineItem = Extract<CCItem, { kind: "pipeline" }>;

/** The seven blueprint agents in order, so the card shows who's next before they start. */
const ROSTER = ["Document Analyst", "Salesforce Architect", "Flow QA Tester", "Visual Designer", "Tester Agent", "Flow Validator", "Technical Writer"];

function useElapsed(running: boolean, since: string): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [running]);
  const start = Date.parse(since);
  return Number.isNaN(start) ? 0 : Math.max(0, Math.floor((now - start) / 1000));
}

/** Camille's subagent list (ThinkingProcess): each agent's status and its latest message, plus
 *  the Live Reasoning panel with every agent's streamed thinking. */
export function PipelineCard({ item, live, onOpenReasoning }: { item: PipelineItem; live: boolean; onOpenReasoning: () => void }) {
  const running = live && item.status === "running";
  const elapsed = useElapsed(running, item.at);
  const byName = new Map(item.agents.map((a) => [a.name, a]));
  const lastStep = item.steps[item.steps.length - 1];
  return (
    <div className={`v3-cc-card v3-cc-pipeline ${running ? "running" : ""}`}>
      <div className="v3-cc-card-head">
        <span className="v3-cc-card-icon"><Icon name="layers" size={14} /></span>
        <div>
          <b>{item.refine ? "Refining the journey blueprint" : "Journey blueprint agents"}</b>
          <span>{running ? `Processing · ${elapsed}s${lastStep ? ` · ${lastStep.details}` : ""}` : item.status === "done" ? "All agents finished" : "Stopped before finishing"}</span>
        </div>
      </div>
      <ol className="v3-cc-agents">
        {ROSTER.map((name) => {
          const a: CCAgent | undefined = byName.get(name);
          const state = a ? a.status : "waiting";
          return (
            <li key={name} className={`v3-cc-agent ${state}`}>
              <span className="v3-cc-agent-dot">{state === "complete" ? <Icon name="check" size={10} /> : null}</span>
              <div>
                <b>{name}{a?.source === "rules" && <em className="v3-cc-src rules">Rules</em>}</b>
                <span>{a ? (a.status === "active" ? a.message : a.result ?? a.message) : "Waiting"}</span>
              </div>
            </li>
          );
        })}
      </ol>
      <button type="button" className={`v3-cc-reason-btn ${running ? "live" : ""}`} onClick={onOpenReasoning}>
        <Icon name="eye" size={13} /> Live reasoning
      </button>
    </div>
  );
}

/** Right-side panel with each agent's reasoning, following the stream while it runs. */
export function ReasoningDrawer({ item, live, onClose }: { item: PipelineItem; live: boolean; onClose: () => void }) {
  const body = useRef<HTMLDivElement>(null);
  const total = item.agents.reduce((n, a) => n + (a.reasoning?.length ?? 0), 0);
  useEffect(() => {
    if (live && body.current) body.current.scrollTop = body.current.scrollHeight;
  }, [total, live]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  const shown = item.agents.filter((a) => a.reasoning);
  return (
    <aside className="v3-refine v3-cc-reason" aria-label="Live reasoning">
      <div className="v3-refine-head">
        <b><Icon name="eye" size={14} /> Live reasoning{live && item.status === "running" && <span className="v3-cc-live-dot" />}</b>
        <button type="button" aria-label="Close" onClick={onClose}><Icon name="close" size={13} /></button>
      </div>
      <div className="v3-refine-body" ref={body}>
        {shown.length === 0 && <p className="v3-muted">The agents' reasoning appears here as they work.</p>}
        {shown.map((a) => (
          <div key={a.name} className="v3-cc-reason-card">
            <b>{a.name}</b>
            <Rich text={a.reasoning ?? ""} />
          </div>
        ))}
        {live && item.status === "running" && <div className="v3-ask-thinking"><span /><span /><span /></div>}
      </div>
    </aside>
  );
}
