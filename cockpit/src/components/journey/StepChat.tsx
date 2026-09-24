import { useState } from "react";
import { getJourney } from "../../api";
import type { JourneyQuestion, JourneyStepId, JourneyTurnNote } from "../../types";

export interface TurnState {
  pending: boolean;
  /** Agent reply to the last message in this live exchange (cleared on step change). */
  reply: string | null;
  error: string | null;
}

/** The compact chat strip under a step's canvas (R3-R5): one prompt, 2-4 chips, a text box,
 *  and an "N earlier notes" toggle. It never grows into a transcript by default. */
export function StepChat({ brand, step, question, earlierCount, turn, locked, scopeLabel, onClearScope, onSend }: {
  brand: string;
  step: JourneyStepId;
  question: JourneyQuestion | null;
  earlierCount: number;
  turn: TurnState;
  locked: boolean;
  scopeLabel?: string | null;
  onClearScope?: () => void;
  /** Resolves true on success; the typed text is kept on failure for retry. */
  onSend: (message: string) => Promise<boolean>;
}) {
  const [text, setText] = useState("");
  const [lastFailed, setLastFailed] = useState<string | null>(null);
  const [history, setHistory] = useState<JourneyTurnNote[] | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);

  const disabled = turn.pending || locked;
  const send = async (message: string, fromInput: boolean) => {
    const m = message.trim();
    if (!m || disabled) return;
    const ok = await onSend(m);
    if (ok) {
      setLastFailed(null);
      if (fromInput) setText("");
      if (historyOpen) setHistory(null);
    } else {
      setLastFailed(m);
      if (!fromInput) setText(m);
    }
  };

  const toggleHistory = () => {
    const open = !historyOpen;
    setHistoryOpen(open);
    if (open && history === null) {
      setHistoryError(null);
      getJourney(brand, step)
        .then((s) => setHistory(s.steps.find((x) => x.step === step)?.history ?? []))
        .catch((e) => setHistoryError(String(e)));
    }
  };

  const prompt = locked
    ? "This step is confirmed and locked."
    : turn.reply ?? question?.question ?? "That covers this step. Keep what looks right, then confirm.";
  const chips = (question?.chips ?? []).slice(0, 4);

  return (
    <section className="step-chat" aria-label="Step chat">
      {scopeLabel && (
        <div className="step-chat-scope">
          Refining <strong>{scopeLabel}</strong>
          <button type="button" className="jc-link" onClick={onClearScope}>Back to Audience</button>
        </div>
      )}
      <div className="step-chat-prompt">
        {turn.pending ? <span className="step-chat-pending" role="status">Thinking&hellip;</span> : prompt}
      </div>
      {!locked && chips.length > 0 && (
        <div className="jc-chiplist">
          {chips.map((c) => (
            <button key={c} type="button" className="filter-chip" disabled={disabled} onClick={() => send(c, false)}>{c}</button>
          ))}
        </div>
      )}
      {turn.error && !turn.pending && (
        <div className="step-chat-error" role="alert">
          Couldn't reach the agent: {turn.error}
          {lastFailed && <button type="button" className="jc-link" onClick={() => send(lastFailed, text.trim() === lastFailed)}>Retry</button>}
        </div>
      )}
      <form className="step-chat-form" onSubmit={(e) => { e.preventDefault(); void send(text, true); }}>
        <input className="jc-input" value={text} disabled={disabled}
          placeholder={locked ? "Locked" : "Answer, or tell the agent what to change"}
          onChange={(e) => setText(e.target.value)} aria-label="Message the step agent" />
        <button type="submit" className="jc-btn jc-btn-keep" disabled={disabled || !text.trim()}>Send</button>
      </form>
      {earlierCount > 0 && (
        <button type="button" className="jc-link step-chat-toggle" onClick={toggleHistory} aria-expanded={historyOpen}>
          {historyOpen ? "Hide" : `${earlierCount} earlier note${earlierCount === 1 ? "" : "s"}`}
        </button>
      )}
      {historyOpen && (
        <div className="step-chat-history">
          {historyError && <div className="step-chat-error">{historyError}</div>}
          {!history && !historyError && <span className="jc-empty">Loading&hellip;</span>}
          {history?.map((h, i) => (
            <div key={i} className={`step-chat-note ${h.role === "user" ? "user" : "agent"}`}>
              <span className="step-chat-role">{h.role === "user" ? "You" : "Agent"}</span> {h.text}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
