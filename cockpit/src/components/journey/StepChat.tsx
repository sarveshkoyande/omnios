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
  /** Set when the message answered the step's question: the dock counts down, keeps the
   *  drafted answer and moves on, instead of asking for a keep/confirm click. */
  advance: { stepDone: boolean; nextLabel: string | null } | null;
  error: string | null;
}

const COUNTDOWN = 5;

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
  onKeep: () => Promise<unknown>;
  onUndo: () => Promise<unknown>;
  onConfirm: () => Promise<unknown>;
  onReopen: () => Promise<unknown>;
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
 *  show your message, the agent's thinking steps and its reply. An answer to the step's
 *  question counts down and advances on its own; otherwise its CTAs settle the drafts. */
export function StepChat({ brand, step, stepLabel, question, earlierCount, turn, locked, scopeLabel, onClearScope, onSend, drafts, onDismiss, onAdvance, idlePrompt, unit = "step" }: {
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
  /** Keeps the answered drafts and moves to the next question (or confirms the step). */
  onAdvance?: () => Promise<void>;
  /** The collapsed dock's prompt when there's no open question. */
  idlePrompt?: string;
  /** What the confirm/reopen buttons act on ("step" in the Journey, "flow" on a flow page). */
  unit?: string;
}) {
  const [text, setText] = useState("");
  const [lastFailed, setLastFailed] = useState<string | null>(null);
  const [history, setHistory] = useState<JourneyTurnNote[] | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const threadRef = useRef<HTMLDivElement>(null);

  const [count, setCount] = useState<number | null>(null);
  const [leaving, setLeaving] = useState(false);

  const expanded = turn.message !== null;
  const disabled = turn.pending || locked;
  const advancing = !!turn.advance && !!onAdvance && !turn.pending && !turn.error;

  // Answer acknowledged: count down, animate the exchange out, then keep and move on.
  useEffect(() => {
    if (!advancing || !onAdvance) { setCount(null); setLeaving(false); return; }
    setCount(COUNTDOWN);
    setLeaving(false);
    let n = COUNTDOWN;
    let exit: number | undefined;
    const t = window.setInterval(() => {
      n -= 1;
      setCount(n);
      if (n > 0) return;
      window.clearInterval(t);
      setLeaving(true);
      exit = window.setTimeout(() => {
        onAdvance().catch(() => { setLeaving(false); setCount(null); });
      }, 380);
    }, 1000);
    return () => { window.clearInterval(t); window.clearTimeout(exit); };
    // Restart only for a new acknowledged answer, not on every parent render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [advancing, turn.reply]);

  const undoAnswer = () => {
    setCount(null);
    void drafts.onUndo().then(onDismiss, () => undefined);
  };

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

  const act = (fn: () => Promise<unknown>) => { void fn().then(onDismiss, () => undefined); };

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
    : question?.question ?? idlePrompt ?? "That covers this step.";
  const chips = locked ? [] : (question?.chips ?? []).slice(0, 4);
  const pendingSteps = PENDING_STEPS(stepLabel);
  const shownPending = pendingSteps.slice(0, Math.min(pendingSteps.length, tick + 1));

  const saveDrafts = () => act(canConfirm && !question
    ? async () => { await drafts.onKeep(); await drafts.onConfirm(); }
    : drafts.onKeep);

  // Shown after an advance fails: settle the answer by hand.
  const retryCtas = (
    <div className="agent-dock-ctas">
      {drafts.count > 0 && !locked && (
        <>
          <button type="button" className="jc-btn jc-btn-keep" disabled={drafts.busy} onClick={saveDrafts}>Save answer</button>
          <button type="button" className="jc-btn" disabled={drafts.busy} onClick={() => act(drafts.onUndo)}>Discard</button>
        </>
      )}
      <button type="button" className="jc-btn jc-btn-ghost" onClick={onDismiss}>Close</button>
    </div>
  );

  const idleCtas = (
    <div className="agent-dock-ctas">
      {drafts.count === 0 && !confirmed && !locked && canConfirm && (
        <button type="button" className="jc-btn jc-btn-keep" disabled={drafts.busy} onClick={() => act(drafts.onConfirm)}>Confirm {unit}</button>
      )}
      {confirmed && drafts.count === 0 && (
        <button type="button" className="jc-btn jc-btn-ghost" disabled={drafts.busy} onClick={() => act(drafts.onReopen)}>Reopen {unit}</button>
      )}
    </div>
  );

  return (
    <section className={`agent-dock ${expanded ? "expanded" : ""}`} aria-label={`${stepLabel} agent`}>
      {expanded && (
        <div className={`agent-dock-thread ${leaving ? "leaving" : ""}`} ref={threadRef} aria-live="polite">
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
          {advancing && count !== null && (
            <div className="agent-dock-countdown" role="status">
              <span className="agent-dock-count-ring" key={count}>{Math.max(count, 1)}</span>
              <span>
                {turn.advance?.stepDone
                  ? `${stepLabel} is complete. Confirming${turn.advance.nextLabel ? `, then on to ${turn.advance.nextLabel}` : ""}…`
                  : "Next question coming up…"}
              </span>
              <button type="button" className="jc-link" disabled={drafts.busy || leaving} onClick={undoAnswer}>Undo</button>
            </div>
          )}
          {!turn.pending && !(advancing && count !== null) && (turn.advance ? retryCtas : (
            <div className="agent-dock-ctas">
              <button type="button" className="jc-btn jc-btn-ghost" onClick={onDismiss}>Close</button>
            </div>
          ))}
        </div>
      )}

      {!expanded && (
        <div className="agent-dock-head" key={prompt}>
          <span className="agent-dock-avatar" aria-hidden>AI</span>
          <div className="agent-dock-prompt">
            {prompt}
            {drafts.count > 0 && !locked && (
              <span className="agent-dock-count">
                {drafts.count} earlier answer{drafts.count === 1 ? "" : "s"} not saved yet
                {" · "}<button type="button" className="jc-link" disabled={drafts.busy} onClick={saveDrafts}>Save</button>
                {" · "}<button type="button" className="jc-link" disabled={drafts.busy} onClick={() => act(drafts.onUndo)}>Discard</button>
              </span>
            )}
            {drafts.confirmBlocked && drafts.count === 0 && !confirmed && <span className="agent-dock-count">{drafts.confirmBlocked}</span>}
          </div>
          {idleCtas}
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
