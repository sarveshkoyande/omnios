import { useState } from "react";
import { Icon } from "../../components/Icon";
import type { CCItem } from "./api";
import { AssumptionCard } from "./AssumptionCard";
import { PipelineCard } from "./Pipeline";
import { QuestionCard } from "./QuestionCard";
import { Rich } from "./Rich";

type ProgressItem = Extract<CCItem, { kind: "progress" }>;

/** Camille's thinking steps: each step the Campaign Consultant reported, the last one live. */
function ProgressCard({ item, live }: { item: ProgressItem; live: boolean }) {
  const [open, setOpen] = useState(false);
  const running = live && item.status === "running";
  const last = item.steps[item.steps.length - 1];
  if (!running) {
    return (
      <div className="v3-cc-progress-done">
        <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
          <Icon name="check" size={12} /> <span>{last?.details ?? "Done"}</span>
          {item.steps.length > 1 && <Icon name="chevronDown" size={11} />}
        </button>
        {open && <ul>{item.steps.map((s, i) => <li key={i}><b>{s.title}</b> {s.details}</li>)}</ul>}
      </div>
    );
  }
  return (
    <div className="v3-cc-card v3-cc-progress">
      {item.steps.map((s, i) => (
        <div key={i} className={`v3-cc-progress-step ${i === item.steps.length - 1 ? "active" : ""}`}>
          <span className="v3-cc-progress-mark">{i === item.steps.length - 1 ? <span className="v3-cc-spinner" /> : <Icon name="check" size={11} />}</span>
          <div><b>{s.title}</b><span>{s.details}</span></div>
        </div>
      ))}
      {!item.steps.length && <div className="v3-ask-thinking"><span /><span /><span /></div>}
    </div>
  );
}

export function Conversation({ items, liveIds, busy, onAnswers, onAcceptAssumptions, onResolveAssumptions, onOpenReasoning }: {
  items: CCItem[];
  /** Items created by the step that's running now. */
  liveIds: Set<string>;
  busy: boolean;
  onAnswers: (text: string) => void;
  onAcceptAssumptions: () => void;
  onResolveAssumptions: (text: string) => void;
  onOpenReasoning: (itemId: string) => void;
}) {
  return (
    <div className="v3-cc-thread" aria-live="polite">
      {items.map((it) => {
        switch (it.kind) {
          case "user":
            return (
              <div key={it.id} className="v3-cc-user">
                {it.file_name && <span className="v3-cc-file"><Icon name="document" size={12} /> {it.file_name}</span>}
                {it.text}
              </div>
            );
          case "agent":
            return <div key={it.id} className="v3-cc-agent-msg"><span className="v3-cc-agent-avatar" aria-hidden>AI</span><Rich text={it.text} /></div>;
          case "progress":
            return <ProgressCard key={it.id} item={it} live={liveIds.has(it.id)} />;
          case "questions":
            return <QuestionCard key={it.id} questions={it.questions} answered={it.answered} disabled={busy} onSubmit={onAnswers} />;
          case "assumptions":
            return <AssumptionCard key={it.id} assumptions={it.assumptions} resolved={it.resolved} disabled={busy}
              onAccept={onAcceptAssumptions} onResolve={onResolveAssumptions} />;
          case "pipeline":
            return <PipelineCard key={it.id} item={it} live={liveIds.has(it.id)} onOpenReasoning={() => onOpenReasoning(it.id)} />;
          default:
            return null;
        }
      })}
    </div>
  );
}
