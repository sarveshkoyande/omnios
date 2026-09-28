import { useEffect, useState } from "react";
import { flowSopChat, flowSopChatOpening } from "../../api";
import { Icon } from "../Icon";

/**
 * "Talk to the diagram" -- the Flow Editor (strategy/flow_sop/editor.py, ported from the
 * reference project's scripts/flow_editor.py). Each message goes through the model only to
 * decide *which* edit ("delete B7", "rename B3 to...", "if yes send the reminder, otherwise
 * stop"), and the edit itself is applied deterministically server-side against the real block
 * list -- a model that answers oddly produces a refusal, never a mangled diagram.
 *
 * One turn on screen at a time -- the question just asked, a thinking state, then the
 * confident answer -- not a growing, ever-scrolling transcript. `history` (what the model
 * reads back on the next turn) and `ops` (what gets replayed onto the diagram) still
 * accumulate across turns, same as before; they're just never rendered as a message list.
 * Asking a new question replaces what's on screen; the previous turn is archived into
 * `history` for context, not shown.
 *
 * Same centered card shape as BrandOverview's own "build something" launcher and the wizard
 * step of this same page (plan-launcher-fab/plan-launcher-backdrop/plan-launcher-card) --
 * not a side panel, and the two never show at once (the wizard's card only shows before a
 * flow is ready, this one only after).
 */

type Phase = "thinking" | "answered";

export function FlowEditorChat({ campaignId, audience, onMarkup }: {
  campaignId: number;
  audience: string;
  /** Called with the freshly edited SVG markup after an edit is applied, so the diagram
   *  viewer can show it without a re-fetch. */
  onMarkup: (svg: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [phase, setPhase] = useState<Phase>("thinking");
  const [question, setQuestion] = useState<string | null>(null);
  const [answer, setAnswer] = useState<string | null>(null);
  const [ops, setOps] = useState<Record<string, unknown>[]>([]);
  const [history, setHistory] = useState<string[]>([]);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [openedOnce, setOpenedOnce] = useState(false);

  useEffect(() => {
    if (!open || openedOnce) return;
    setOpenedOnce(true);
    setPhase("thinking");
    flowSopChatOpening(campaignId, audience)
      .then((r) => { setQuestion(null); setAnswer(r.reply); setPhase("answered"); })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [open, openedOnce, campaignId, audience]);

  const send = () => {
    const message = text.trim();
    if (!message || phase === "thinking") return;
    setText("");
    setError(null);
    setQuestion(message);
    setAnswer(null);
    setPhase("thinking");
    flowSopChat(campaignId, { message, audience, ops, history })
      .then((r) => {
        setOps(r.ops);
        setHistory(r.history);
        setAnswer(r.reply);
        setPhase("answered");
        if (r.action !== "unclear") onMarkup(r.svg);
      })
      .catch((e) => { setError(e instanceof Error ? e.message : String(e)); setPhase("answered"); });
  };

  if (!open) {
    return (
      <button type="button" className="plan-launcher-fab" aria-label="Talk to the diagram" onClick={() => setOpen(true)}>
        <Icon name="sparkles" size={24} />
      </button>
    );
  }

  return (
    <>
      <div className="plan-launcher-backdrop" onClick={() => setOpen(false)} />
      <div className="plan-launcher-card flow-editor-card" role="dialog" aria-modal="true" aria-label="Edit the flow">
        <button type="button" className="plan-launcher-close" aria-label="Close" onClick={() => setOpen(false)}>
          <Icon name="close" size={16} />
        </button>
        <h3>Edit this flow.</h3>
        <div className="flow-editor-turn">
          {question && <div className="flow-editor-msg flow-editor-msg-user">{question}</div>}
          {phase === "thinking" && (
            <div className="flow-editor-msg flow-editor-msg-agent flow-editor-msg-pending"><span /><span /><span /></div>
          )}
          {phase === "answered" && answer && <div className="flow-editor-msg flow-editor-msg-agent">{answer}</div>}
          {error && <div className="step-chat-error" role="alert">{error}</div>}
        </div>
        <form className="wiz-form-row" onSubmit={(e) => { e.preventDefault(); send(); }}>
          <input className="jc-input" placeholder='e.g. "delete B7" or "rename B3 to Efficacy"'
            value={text} disabled={phase === "thinking"} onChange={(e) => setText(e.target.value)} />
          <button type="submit" className="jc-btn jc-btn-keep" disabled={phase === "thinking" || !text.trim()}>Send</button>
        </form>
      </div>
    </>
  );
}
