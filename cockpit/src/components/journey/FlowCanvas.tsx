import { useCallback, useEffect, useMemo, useState } from "react";
import { ReactFlowProvider } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
// The Campaign Ops flow-builder, rendered from frontend/src through the Vite alias (KTD7).
import "@omni-frontend/workspace/stages/operations/flowbuilder.css";
import { Canvas } from "@omni-frontend/workspace/stages/operations/flowbuilder/canvas/Canvas";
import { useWorkflowStore } from "@omni-frontend/workspace/stages/operations/flowbuilder/store/useWorkflowStore";
import { campaignFlowToDocument } from "@omni-frontend/workspace/stages/operations/campaignAdapter";
import { layoutCampaignDocument } from "@omni-frontend/workspace/stages/operations/campaignLayout";
import type { CampaignFlow } from "@omni-frontend/workspace/types";
import { buildJourneyFlow, createCampaign, getCampaignDrift, getJourneyFlow, refreshCampaignSnapshot, journeyConfirm, journeyFlowKeep, journeyFlowTurn, journeyFlowUndo, journeyReopen } from "../../api";
import type { CampaignDrift, JourneyCampaignFlow, JourneyFlow, JourneyFlowOp, JourneyState, JourneyStep } from "../../types";
import { ValueView } from "./DraftValue";
import { StepChat, type TurnState } from "./StepChat";

const IDLE: TurnState = { pending: false, message: null, reply: null, outcome: null, advance: null, error: null };

function describeOp(op: JourneyFlowOp): string {
  switch (op.op) {
    case "add": return `Add ${op.type} "${op.label}"${op.after ? ` after ${op.after}` : ""}`;
    case "remove": return `Remove ${op.code}`;
    case "connect": return `Connect ${op.from} to ${op.to}`;
    case "change": return `Change ${op.code}: ${Object.entries(op.set).map(([k, v]) => `${k} = ${String(v)}`).join(", ")}`;
  }
}

/** Journey flow -> the flow-builder's CampaignFlow, with each node labelled by its stable block
 *  code (R17). Blocks that exist only in the draft are tagged so the draft reads as a draft. */
function toCampaignFlow(flow: JourneyCampaignFlow, keptCodes: Set<string> | null): CampaignFlow {
  return {
    nodes: flow.nodes.map((n) => {
      const code = n.data.block_code;
      const isNew = keptCodes !== null && (!code || !keptCodes.has(code));
      const label = `${code ? `${code} · ` : ""}${n.data.label}${isNew ? " (draft)" : ""}`;
      const day = typeof n.data.day === "number" ? n.data.day : n.data.day ? Number(n.data.day) || undefined : undefined;
      return { ...n, position: n.position ?? { x: 0, y: 0 }, data: { ...n.data, label, day } } as CampaignFlow["nodes"][number];
    }),
    edges: flow.edges,
  };
}

/** Read-only diagram (KTD8: edits come only through chat ops). Node dragging, handles and the
 *  canvas keyboard shortcuts are suppressed; pan and zoom stay available. */
function FlowDiagram({ flow, keptCodes }: { flow: JourneyCampaignFlow; keptCodes: Set<string> | null }) {
  const loadDocument = useWorkflowStore((s) => s.loadDocument);
  useEffect(() => {
    let live = true;
    const doc = campaignFlowToDocument(toCampaignFlow(flow, keptCodes), "Brand flow");
    loadDocument(doc);
    layoutCampaignDocument(doc).then((laid) => { if (live) loadDocument(laid); }).catch(() => undefined);
    return () => { live = false; };
  }, [flow, keptCodes, loadDocument]);

  return (
    <div className="jc-flow-diagram" onKeyDownCapture={(e) => e.stopPropagation()}>
      <ReactFlowProvider>
        <Canvas />
      </ReactFlowProvider>
    </div>
  );
}

export function FlowCanvas({ brand, labels, step, onState }: {
  brand: string;
  labels: Record<string, string>;
  step: JourneyStep;
  onState: (s: JourneyState) => void;
}) {
  const [flow, setFlow] = useState<JourneyFlow | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [turn, setTurn] = useState<TurnState>(IDLE);

  const reload = () => getJourneyFlow(brand).then(setFlow);
  // Idea 5: the flow's campaign keeps the brand content it was built from; say when it moved on.
  const [drift, setDrift] = useState<CampaignDrift | null>(null);
  const [compare, setCompare] = useState(false);
  const campaignId = flow?.status === "built" ? flow.campaign_id : null;
  useEffect(() => {
    let live = true;
    if (campaignId == null) { setDrift(null); return; }
    getCampaignDrift(campaignId).then((d) => { if (live) setDrift(d); }).catch(() => undefined);
    return () => { live = false; };
  }, [campaignId, flow]);
  const updateContent = () => {
    if (campaignId == null) return;
    run(refreshCampaignSnapshot(campaignId).then(async (d) => { setDrift(d); setCompare(false); await reload(); }));
  };

  useEffect(() => {
    let live = true;
    getJourneyFlow(brand).then((f) => { if (live) setFlow(f); }).catch((e) => { if (live) setError(String(e)); });
    return () => { live = false; };
  }, [brand]);

  const run = (p: Promise<unknown>) => {
    setBusy(true);
    setError(null);
    p.catch((e) => setError(e instanceof Error ? e.message : String(e))).finally(() => setBusy(false));
  };

  // R22: a brand with engagement plans picks the campaign its Journey flow goes into.
  const [placement, setPlacement] = useState("");
  const [newCampaign, setNewCampaign] = useState("");
  const build = () => run((async () => {
    let campaignId: number | undefined;
    if (flow?.needs_campaign && flow.status !== "built") {
      if (placement.startsWith("new:")) {
        campaignId = (await createCampaign(Number(placement.slice(4)), newCampaign.trim())).id;
      } else if (placement) {
        campaignId = Number(placement);
      }
    }
    setFlow(await buildJourneyFlow(brand, campaignId));
  })());
  const placementMissing = !!flow?.needs_campaign && flow.status !== "built"
    && (!placement || (placement.startsWith("new:") && !newCampaign.trim()));
  /** Dock CTA: rejects on failure so the dock stays open to show the error. */
  const settle = async (p: Promise<JourneyState>) => {
    setBusy(true);
    setError(null);
    try {
      onState(await p);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      throw e;
    } finally {
      setBusy(false);
    }
  };
  const dismissTurn = useCallback(() => setTurn(IDLE), []);

  const sendTurn = async (message: string): Promise<boolean> => {
    setTurn({ pending: true, message, reply: null, outcome: null, advance: null, error: null });
    try {
      const r = await journeyFlowTurn(brand, { message });
      setFlow(r.flow);
      setTurn({
        pending: false, message, reply: r.reply, error: null, advance: null,
        outcome: { mode: r.mode, changes: (r.flow.draft?.ops ?? []).map(describeOp), dropped: [] },
      });
      return true;
    } catch (e) {
      setTurn((t) => ({ ...t, pending: false, error: e instanceof Error ? e.message : String(e) }));
      return false;
    }
  };

  // Memoised so the diagram only reloads when the flow itself changes.
  const keptCodes = useMemo(() => (flow?.draft && flow.flow
    ? new Set(flow.flow.nodes.map((n) => n.data.block_code).filter((c): c is string => !!c))
    : null), [flow]);
  const shown = flow?.draft?.flow ?? flow?.flow ?? null;
  const draftOps = flow?.draft?.ops ?? [];
  const confirmBlocked = flow?.status !== "built" ? "Build the flow first." : null;

  if (error && !flow) return <div className="jc-card"><div className="step-chat-error">{error}</div></div>;
  if (!flow) return <div className="jc-card"><span className="jc-empty">Loading flow&hellip;</span></div>;
  return (
    <>
      <div className="jc-card">
        {flow.status === "waiting" && (
          <div className="jc-waiting">Flow is waiting on {flow.waiting.map((s) => labels[s] ?? s).join(", ")}. Confirm those steps and the flow can be built by rules.</div>
        )}
        {flow.needs_campaign && flow.status === "not_built" && (
          <div className="jc-flow-placement">
            <label className="jc-field-label" htmlFor="flow-placement">This brand already has engagement plans. Put this flow in</label>
            <select id="flow-placement" className="jc-input" value={placement} disabled={busy}
              onChange={(e) => setPlacement(e.target.value)}>
              <option value="">Choose a campaign…</option>
              {(flow.campaigns ?? []).map((c) => (
                <option key={c.id} value={String(c.id)}>{c.engagement_plan} › {c.name}</option>
              ))}
              {(flow.engagement_plans ?? []).map((p) => (
                <option key={`new-${p.id}`} value={`new:${p.id}`}>{p.name} › New campaign…</option>
              ))}
            </select>
            {placement.startsWith("new:") && (
              <input className="jc-input" placeholder="Campaign name" value={newCampaign} disabled={busy}
                onChange={(e) => setNewCampaign(e.target.value)} aria-label="New campaign name" />
            )}
          </div>
        )}
        {flow.status !== "waiting" && (
          <div className="draft-bar-actions">
            <button type="button" className="jc-btn jc-btn-keep" disabled={busy || draftOps.length > 0 || placementMissing} onClick={build}>
              {busy ? "Working…" : flow.status === "built" ? "Rebuild flow" : "Build flow"}
            </button>
          </div>
        )}
        {error && <div className="step-chat-error" role="alert">{error}</div>}
        {drift?.has_drift && (
          <div className="jc-drift" role="status">
            <div className="jc-drift-head">
              <span>
                The brand's {Object.keys(drift.changed).map((s) => labels[s] ?? s).join(", ")} changed since this
                campaign was built. This flow still uses the earlier content.
              </span>
              <span className="jc-drift-actions">
                <button type="button" className="jc-link" onClick={() => setCompare((c) => !c)}>{compare ? "Hide" : "Compare"}</button>
                <button type="button" className="jc-btn jc-btn-keep" disabled={busy} onClick={updateContent}>Update to current content</button>
              </span>
            </div>
            {compare && (
              <dl className="jc-drift-list">
                {Object.entries(drift.changed).flatMap(([step, changes]) => (changes ?? []).map((c) => (
                  <div key={`${step}-${c.key}`} className="jc-drift-row">
                    <dt>{labels[step] ?? step} · {c.label}</dt>
                    <dd><span className="jc-drift-then"><ValueView value={c.then} /></span><span aria-hidden>→</span><ValueView value={c.now} /></dd>
                  </div>
                )))}
              </dl>
            )}
          </div>
        )}
        {flow.dropped.length > 0 && (
          <div className="jc-waiting">
            {flow.dropped.length} kept edit{flow.dropped.length === 1 ? "" : "s"} could not be reapplied:
            <ul className="jc-flow-ops">{flow.dropped.map((d, i) => <li key={i}>{describeOp(d.op)} ({d.reason})</li>)}</ul>
          </div>
        )}
        {flow.draft && (
          <div className="jc-flow-draft-note">
            Draft edit, not kept yet:
            <ul className="jc-flow-ops">{draftOps.map((op, i) => <li key={i}>{describeOp(op)}</li>)}</ul>
          </div>
        )}
        {shown && (
          <div className={flow.draft ? "jc-flow-frame is-draft" : "jc-flow-frame"}>
            <FlowDiagram flow={shown} keptCodes={keptCodes} />
          </div>
        )}
      </div>
      {flow.status === "built" && (
        <>
          <StepChat brand={brand} step="flow" stepLabel={step.label} question={step.question} earlierCount={step.earlier_count}
            turn={turn} locked={false} onSend={sendTurn} onDismiss={dismissTurn}
            drafts={{
              count: draftOps.length, status: step.status, busy, confirmBlocked, error: null, complete: true,
              onKeep: () => settle(journeyFlowKeep(brand)),
              onUndo: () => settle(journeyFlowUndo(brand)),
              onConfirm: () => settle(journeyConfirm(brand, "flow")),
              onReopen: () => settle(journeyReopen(brand, "flow")),
            }} />
        </>
      )}
    </>
  );
}
