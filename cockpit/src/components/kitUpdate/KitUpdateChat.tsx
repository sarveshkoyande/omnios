import { useState } from "react";
import type { KitChatMessage } from "../../types";

/** The per-tab chat thread UI -- same message-list/input shell shape every tab-chat needs,
 *  data-driven off one section's history so the 5 tabs share one implementation instead
 *  of 5 hand-written UIs. */
export function KitUpdateChat({ history, onSend, sending }: {
  history: KitChatMessage[];
  onSend: (message: string) => void;
  sending: boolean;
}) {
  const [draft, setDraft] = useState("");

  const send = () => {
    const text = draft.trim();
    if (!text || sending) return;
    onSend(text);
    setDraft("");
  };

  return (
    <div className="kit-chat">
      <div className="kit-chat-messages">
        {history.length === 0 && (
          <p className="kit-chat-empty">No conversation yet for this section.</p>
        )}
        {history.map((m, i) => (
          <div className={`kit-chat-msg kit-chat-msg-${m.role}`} key={i}>
            <div className="kit-chat-msg-role">{m.role === "user" ? "You" : (m.agent_id || "Agent")}</div>
            <div className="kit-chat-msg-text">{m.text}</div>
          </div>
        ))}
        {sending && <div className="kit-chat-msg kit-chat-msg-assistant kit-chat-thinking">Thinking&hellip;</div>}
      </div>
      <div className="kit-chat-input-row">
        <textarea
          className="kit-chat-input"
          placeholder="Ask this section's agent to change something…"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
        />
        <button type="button" className="kit-chat-send" onClick={send} disabled={!draft.trim() || sending}>
          Send
        </button>
      </div>
    </div>
  );
}
