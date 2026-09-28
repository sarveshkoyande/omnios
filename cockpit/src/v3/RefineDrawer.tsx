import { useState } from "react";
import { applyRefinement, refineArtifact, type RefineChange, type V3Artifact } from "../api";
import { Icon } from "../components/Icon";

/** C13: ask for a change in plain words; the LLM proposes field-level edits (strategy/
 *  v3_assist.refine), shown as old -> new diffs you accept or reject one by one. Only accepted
 *  ones are saved, together, as one new version. Nothing is rewritten silently. One turn on
 *  screen at a time, like the rest of this app's chats. */
export function RefineDrawer({ artifact, onApplied, onClose }: {
  artifact: V3Artifact;
  onApplied: (a: V3Artifact) => void;
  onClose: () => void;
}) {
  const [text, setText] = useState("");
  const [question, setQuestion] = useState<string | null>(null);
  const [status, setStatus] = useState<"idle" | "thinking" | "done" | "error">("idle");
  const [reply, setReply] = useState("");
  const [changes, setChanges] = useState<RefineChange[]>([]);
  const [decisions, setDecisions] = useState<Record<string, "accept" | "reject">>({});
  const [applying, setApplying] = useState(false);

  const send = () => {
    const q = text.trim();
    if (!q || status === "thinking") return;
    setQuestion(q);
    setText("");
    setStatus("thinking");
    setChanges([]);
    setDecisions({});
    refineArtifact(artifact.id, q)
      .then((r) => { setReply(r.reply); setChanges(r.changes); setStatus("done"); })
      .catch((e) => { setReply(e instanceof Error ? e.message : String(e)); setStatus("error"); });
  };

  const accepted = changes.filter((c) => decisions[c.field_id] === "accept");
  const apply = () => {
    if (!accepted.length) return;
    setApplying(true);
    applyRefinement(artifact.id, Object.fromEntries(accepted.map((c) => [c.field_id, c.new_value])), `Refined: ${question ?? ""}`.slice(0, 120))
      .then((a) => { onApplied(a); setChanges([]); setDecisions({}); setReply(`Applied ${accepted.length} change${accepted.length === 1 ? "" : "s"} as v${a.version}.`); })
      .catch((e) => setReply(e instanceof Error ? e.message : String(e)))
      .finally(() => setApplying(false));
  };

  return (
    <aside className="v3-refine" aria-label="Refine">
      <div className="v3-refine-head">
        <b><Icon name="sparkles" size={14} /> Refine</b>
        <button type="button" aria-label="Close refine" onClick={onClose}><Icon name="close" size={13} /></button>
      </div>
      <div className="v3-refine-body">
        {!question && <p className="v3-muted">Ask for a change in plain words, e.g. "tighten the objective" or "move the launch two weeks later". You'll see each proposed edit before anything is saved.</p>}
        {question && <div className="v3-ask-q">{question}</div>}
        {status === "thinking" && <div className="v3-ask-thinking"><span /><span /><span /></div>}
        {(status === "done" || status === "error") && reply && <p className={status === "error" ? "v3-ask-error" : "v3-refine-reply"}>{reply}</p>}
        {changes.map((c) => {
          const d = decisions[c.field_id];
          return (
            <div key={c.field_id} className={`v3-diff ${d ?? ""}`}>
              <b>{c.label}</b>
              <div className="v3-diff-old">{c.old_value}</div>
              <div className="v3-diff-new">{c.new_value}</div>
              {c.why && <em>{c.why}</em>}
              <div className="v3-diff-actions">
                <button type="button" className={d === "reject" ? "on" : ""} onClick={() => setDecisions((x) => ({ ...x, [c.field_id]: "reject" }))}>Reject</button>
                <button type="button" className={`accept ${d === "accept" ? "on" : ""}`} onClick={() => setDecisions((x) => ({ ...x, [c.field_id]: "accept" }))}>Accept</button>
              </div>
            </div>
          );
        })}
        {changes.length > 0 && (
          <button type="button" className="v3-refine-apply" disabled={!accepted.length || applying} onClick={apply}>
            {applying ? "Saving…" : `Apply ${accepted.length} accepted change${accepted.length === 1 ? "" : "s"}`}
          </button>
        )}
      </div>
      <form className="v3-refine-compose" onSubmit={(e) => { e.preventDefault(); send(); }}>
        <textarea rows={2} value={text} placeholder="What should change?" onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} />
        <button type="submit" disabled={!text.trim() || status === "thinking"}>Send</button>
      </form>
    </aside>
  );
}
