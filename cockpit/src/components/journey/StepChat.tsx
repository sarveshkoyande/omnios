import { useEffect, useRef, useState } from "react";
import { getJourney } from "../../api";
import type { JourneyQuestion, JourneyStepId, JourneyTurnNote } from "../../types";

export interface TurnOutcome {
  mode: "llm" | "fallback" | "ops";
  /** Readable list of what the agent drafted. */
  changes: string[];
  dropped: string[];
}

export interface TurnState {
  pending: boolean;
  /** The message behind the live exchange, shown above the thinking steps. */
  message: string | null;
  /** Agent reply to that message (cleared on step change). */
  reply: string | null;
  outcome: TurnOutcome | null;
  error: string | null;
}

/** The step's pending drafts, surfaced as the dock's CTAs so they are settled here only. */
export interface DockDrafts {
  count: number;
  status: string;
  busy: boolean;
  /** Why the step can't be confirmed even once drafts are kept (e.g. Kit flags); keep still works. */
  confirmBlocked: string | null;
  /** True once every required field is kept or covered by a pending draft. */
  complete: boolean;
  error: string | null;
  onKeep: () => Promise<void>;
  onUndo: () => Promise<void>;
  onConfirm: () => Promise<void>;
  onReopen: () => Promise<void>;
}

const PENDING_STEPS = (stepLabel: string) => [
  "Reading your message",
  `Checking ${stepLabel} against the brand kit`,
  "Drafting changes",
];

function doneSteps(stepLabel: string, o: TurnOutcome): string[] {
  const steps = [
    "Read your message",
    o.mode === "llm" ? `Asked the ${stepLabel} agent`
      : o.mode === "ops" ? "Read it as a direct edit"
      : "Agent unavailable, used the rules engine",
    o.changes.length
      ? `Drafted ${o.changes.length} change${o.changes.length === 1 ? "" : "s"}: ${o.changes.join("; ")}`
      : "No changes needed",
  ];
  if (o.dropped.length) steps.push(`Couldn't use: ${o.dropped.join(", ")}`);
  return steps;
}

/** Floating agent dock for a journey step: a compact composer that expands upward on send to
 *  show your message, the agent's thinking steps and its reply. Its CTAs keep, undo or
 *  confirm the step's drafts, which is the only place those are settled. */
export function StepChat({ brand, step, stepLabel, question, earlierCount, turn, locked, scopeLabel, onClearScope, onSend, drafts, onDismiss }: {
  brand: string;
  step: JourneyStepId;
  stepLabel: string;
  question: JourneyQuestion | null;
  earlierCount: number;
  turn: TurnState;
  locked: boolean;
  scopeLabel?: string | null;
  onClearScope?: () => void;
  /** Resolves true on success; the typed text is kept on failure for retry. */
  onSend: (message: string) => Promise<boolean>;
  drafts: DockDrafts;
  /** Collapse the expanded exchange. */
  onDismiss: () => void;
}) {
  const [text, setText] = useState("");
  const [lastFailed, setLastFailed] = useState<string | null>(null);
  const [history, setHistory] = useState<JourneyTurnNote[] | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const threadRef = useRef<HTMLDivElement>(null);

  const expanded = turn.message !== null;
  const disabled = turn.pending || locked;

  useEffect(() => {
    if (!turn.pending) return;
    setTick(0);
    const t = window.setInterval(() => setTick((n) => n + 1), 900);
    return () => window.clearInterval(t);
  }, [turn.pending]);

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight });
  }, [turn.pending, turn.reply, tick]);

  useEffect(() => {
    if (!expanded) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && !turn.pending) onDismiss(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [expanded, turn.pending, onDismiss]);

  // Grow the composer with what's typed, up to a few lines.
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 132)}px`;
  }, [text]);

  const send = async (message: string, fromInput: boolean) => {
    const m = message.trim();
    if (!m || disabled) return;
    if (fromInput) setText("");
    const ok = await onSend(m);
    if (ok) {
      setLastFailed(null);
      if (historyOpen) setHistory(null);
    } else {
      setLastFailed(m);
      setText(m);
    }
  };

  const act = (fn: () => Promise<void>) => { void fn().then(onDismiss, () => undefined); };

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

  const confirmed = drafts.status === "confirmed";
  const canConfirm = drafts.complete && drafts.confirmBlocked === null;
  const prompt = locked
    ? "This step is confirmed and locked."
    : question?.question ?? "That covers this step. Keep what looks right, then confirm.";
  const chips = locked ? [] : (question?.chips ?? []).slice(0, 4);
  const pendingSteps = PENDING_STEPS(stepLabel);
  const shownPending = pendingSteps.slice(0, Math.min(pendingSteps.length, tick + 1));

  const ctas = (
    <div className="agent-dock-ctas">
      {drafts.count > 0 && !locked && (
        <>
          <button type="button" className="jc-btn jc-btn-keep" disabled={drafts.busy}
            onClick={() => act(canConfirm ? async () => { await drafts.onKeep(); await drafts.onConfirm(); } : drafts.onKeep)}>
            {canConfirm ? "Keep & confirm step" : "Keep changes"}
          </button>
          <button type="button" className="jc-btn" disabled={drafts.busy} onClick={() => act(drafts.onUndo)}>Undo changes</button>
        </>
      )}
      {drafts.count === 0 && !confirmed && !locked && canConfirm && (
        <button type="button" className="jc-btn jc-btn-keep" disabled={drafts.busy} onClick={() => act(drafts.onConfirm)}>Confirm step</button>
      )}
      {confirmed && (
        <button type="button" className="jc-btn" disabled={drafts.busy} onClick={() => act(drafts.onReopen)}>Reopen step</button>
      )}
      {expanded && <button type="button" className="jc-btn jc-btn-ghost" onClick={onDismiss}>Close</button>}
    </div>
  );

  return (
    <section className={`agent-dock ${expanded ? "expanded" : ""}`} aria-label={`${stepLabel} agent`}>
      {expanded && (
        <div className="agent-dock-thread" ref={threadRef} aria-live="polite">
          <div className="agent-dock-user">{turn.message}</div>
          <ol className="agent-dock-steps">
            {(turn.pending ? shownPending : turn.outcome ? doneSteps(stepLabel, turn.outcome) : []).map((s, i, arr) => {
              const running = turn.pending && i === arr.length - 1;
              return (
                <li key={s} className={running ? "running" : "done"}>
                  <span className="agent-dock-step-dot" aria-hidden />
                  {s}{running ? "…" : ""}
                </li>
              );
            })}
          </ol>
          {turn.reply && !turn.pending && (
            <div className="agent-dock-reply">
              <span className="agent-dock-avatar" aria-hidden>AI</span>
              <p>{turn.reply}</p>
            </div>
          )}
          {turn.error && !turn.pending && (
            <div className="step-chat-error" role="alert">
              Couldn't reach the agent: {turn.error}
              {lastFailed && <button type="button" className="jc-link" onClick={() => send(lastFailed, text.trim() === lastFailed)}>Retry</button>}
            </div>
          )}
          {!turn.pending && ctas}
        </div>
      )}

      {!expanded && (
        <div className="agent-dock-head">
          <span className="agent-dock-avatar" aria-hidden>AI</span>
          <div className="agent-dock-prompt">
            {prompt}
            {drafts.count > 0 && !locked && (
              <span className="agent-dock-count">{drafts.count} change{drafts.count === 1 ? "" : "s"} ready to review</span>
            )}
            {drafts.confirmBlocked && drafts.count === 0 && !confirmed && <span className="agent-dock-count">{drafts.confirmBlocked}</span>}
          </div>
          {ctas}
        </div>
      )}
      {drafts.error && <div className="step-chat-error" role="alert">{drafts.error}</div>}

      {scopeLabel && (
        <div className="step-chat-scope">
          Refining <strong>{scopeLabel}</strong>
          <button type="button" className="jc-link" onClick={onClearScope}>Back to Audience</button>
        </div>
      )}
      {!expanded && chips.length > 0 && (
        <div className="jc-chiplist">
          {chips.map((c) => (
            <button key={c} type="button" className="filter-chip" disabled={disabled} onClick={() => send(c, false)}>{c}</button>
          ))}
        </div>
      )}
      <form className="agent-dock-form" onSubmit={(e) => { e.preventDefault(); void send(text, true); }}>
        <textarea ref={inputRef} className="jc-input agent-dock-input" rows={1} value={text} disabled={disabled}
          placeholder={locked ? "Locked" : `Message the ${stepLabel} agent`}
          onChange={(e) => setText(e.target.value)} aria-label="Message the step agent"
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void send(text, true); } }} />
        <button type="submit" className="jc-btn jc-btn-keep" disabled={disabled || !text.trim()}>Send</button>
      </form>
      {earlierCount > 0 && !expanded && (
        <button type="button" className="jc-link step-chat-toggle" onClick={toggleHistory} aria-expanded={historyOpen}>
          {historyOpen ? "Hide" : `${earlierCount} earlier note${earlierCount === 1 ? "" : "s"}`}
        </button>
      )}
      {historyOpen && !expanded && (
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
