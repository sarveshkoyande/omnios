import { useEffect, useState } from "react";
import { buildJourneyFlow, getJourneyFlow } from "../../api";
import type { JourneyFlow } from "../../types";

/** Flow slot until U7's FlowCanvas lands: waiting reasons, a "Build flow" button, and a
 *  plain list of blocks with their stable codes. Deliberately no diagram. */
export function FlowPlaceholder({ brand, labels }: { brand: string; labels: Record<string, string> }) {
  const [flow, setFlow] = useState<JourneyFlow | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    getJourneyFlow(brand).then((f) => { if (live) setFlow(f); }).catch((e) => { if (live) setError(String(e)); });
    return () => { live = false; };
  }, [brand]);

  const build = () => {
    setBusy(true);
    setError(null);
    buildJourneyFlow(brand).then(setFlow).catch((e) => setError(String(e))).finally(() => setBusy(false));
  };

  if (error && !flow) return <div className="jc-card"><div className="step-chat-error">{error}</div></div>;
  if (!flow) return <div className="jc-card"><span className="jc-empty">Loading flow&hellip;</span></div>;
  return (
    <div className="jc-card">
      {flow.status === "waiting" && (
        <div className="jc-waiting">Flow is waiting on {flow.waiting.map((s) => labels[s] ?? s).join(", ")}. Confirm those steps and the flow can be built by rules.</div>
      )}
      {flow.status !== "waiting" && (
        <div className="draft-bar-actions">
          <button type="button" className="jc-btn jc-btn-keep" disabled={busy} onClick={build}>
            {busy ? "Building…" : flow.status === "built" ? "Rebuild flow" : "Build flow"}
          </button>
        </div>
      )}
      {error && <div className="step-chat-error">{error}</div>}
      {flow.status === "built" && flow.flow && (
        <ol className="jc-flow-list">
          {flow.flow.nodes.map((n) => (
            <li key={n.id}>
              <span className="claim-id">{n.data.block_code ?? n.id}</span>
              <span className="pill pill-outline">{n.type}</span>
              <span>{n.data.label}</span>
              {n.data.day !== undefined && <span className="jc-muted">Day {n.data.day}</span>}
              {n.data.channel && <span className="jc-muted">{n.data.channel}</span>}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
