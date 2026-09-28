import { useRef, useState } from "react";
import { chatAsk } from "../api";
import { REGISTRY, type RegistryAgent } from "../agents";
import { Icon } from "../components/Icon";

/** Chat (A1): questions answered from the active brand's facts (strategy/v3_assist.chat),
 *  LLM-only, one turn on screen at a time. Suggests an agent when one would help. */
export function Chat({ activeBrand }: { activeBrand: string | null }) {
  const [text, setText] = useState("");
  const [turn, setTurn] = useState<
    { q: string; status: "thinking" } | { q: string; status: "done"; reply: string; agents: RegistryAgent[] } | { q: string; status: "error"; reply: string } | null
  >(null);
  const box = useRef<HTMLTextAreaElement>(null);

  const send = () => {
    const q = text.trim();
    if (!q || turn?.status === "thinking") return;
    setTurn({ q, status: "thinking" });
    setText("");
    if (box.current) box.current.style.height = "auto";
    chatAsk({
      question: q, brand: activeBrand,
      agents: REGISTRY.map((a) => ({ id: a.id, name: a.name, summary: a.summary, available: !a.tags.includes("coming-soon") })),
    })
      .then((r) => setTurn({ q, status: "done", reply: r.reply, agents: r.agent_ids.map((id) => REGISTRY.find((a) => a.id === id)).filter((a): a is RegistryAgent => Boolean(a)) }))
      .catch((e) => setTurn({ q, status: "error", reply: e instanceof Error ? e.message : String(e) }));
  };

  return (
    <div className="v3-home v3-chat">
      <div>
        <h1 className="v3-page-title">Chat</h1>
        <p className="v3-page-sub">{activeBrand ? <>Answers grounded in <b>{activeBrand}</b>'s brand kit</> : "Pick a brand in the switcher for brand-specific answers"}</p>
      </div>
      <div className="v3-chat-turn">
        {!turn && <p className="v3-muted">Ask about your brand, audience, messaging or how to use an agent.</p>}
        {turn && <div className="v3-ask-q">{turn.q}</div>}
        {turn?.status === "thinking" && <div className="v3-ask-thinking"><span /><span /><span /></div>}
        {turn?.status === "error" && <p className="v3-ask-error">{turn.reply}</p>}
        {turn?.status === "done" && (
          <>
            <div className="v3-chat-reply">{turn.reply}</div>
            {turn.agents.length > 0 && (
              <div className="v3-ask-agents">
                {turn.agents.map((a) => (
                  <a key={a.id} className="v3-ask-agent" href={a.route ?? `#/v3/app/${a.id}`}>
                    <span className="v3-app-icon"><Icon name={a.icon} size={15} /></span>
                    <span className="v3-ask-agent-text"><b>{a.name}</b><span>{a.summary}</span></span>
                    <span className="v3-ask-open">Open</span>
                  </a>
                ))}
              </div>
            )}
          </>
        )}
      </div>
      <form className="v3-ask" onSubmit={(e) => { e.preventDefault(); send(); }}>
        <div className="v3-ask-row">
          <Icon name="message" size={16} />
          <textarea ref={box} rows={1} value={text} placeholder="Ask Omni…"
            onChange={(e) => { setText(e.target.value); e.target.style.height = "auto"; e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`; }}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} />
          <button type="submit" className="v3-ask-send" disabled={!text.trim() || turn?.status === "thinking"}>Send</button>
        </div>
      </form>
    </div>
  );
}
