import { useCallback, useEffect, useMemo, useState } from "react";
import { ReactFlowProvider } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import "@omni-frontend/workspace/stages/operations/flowbuilder.css";
import { Canvas } from "@omni-frontend/workspace/stages/operations/flowbuilder/canvas/Canvas";
import { useWorkflowStore } from "@omni-frontend/workspace/stages/operations/flowbuilder/store/useWorkflowStore";
import { buildFlow, flowAction, flowTurn, getFlow } from "../../api";
import { href } from "../../route";
import type { AnyFlow, DocumentFlow, HierFlow, JourneyFlow } from "../../types";
import { DriftBanner } from "../DriftBanner";
import { describeOp, FlowDiagram, IDLE } from "../journey/FlowCanvas";
import { StepChat, type TurnState } from "../journey/StepChat";
import { FLOW_ORIGIN, StatusPill } from "./shared";

/** A Campaign Plan's Operations diagram (a "document" flow), shown read-only here; it is
 *  edited in the Campaign Plan's own editor (hierarchy plan KTD7). */
function DocumentDiagram({ doc }: { doc: unknown }) {
  const loadDocument = useWorkflowStore((s) => s.loadDocument);
  const [bad, setBad] = useState(false);
  useEffect(() => {
    try {
      loadDocument(doc as Parameters<typeof loadDocument>[0]);
      setBad(false);
    } catch {
      setBad(true);
    }
  }, [doc, loadDocument]);
  if (bad) return <div className="jc-empty">This diagram can't be shown here; open it in the Campaign Plan.</div>;
  return (
    <div className="jc-flow-diagram" onKeyDownCapture={(e) => e.stopPropagation()}>
      <ReactFlowProvider><Canvas /></ReactFlowProvider>
    </div>
  );
}

export function FlowPage({ brand, planId, campaignId, meta, onChanged }: {
  brand: string; planId: number; campaignId: number; meta: HierFlow; onChanged: () => void;
}) {
  const [flow, setFlow] = useState<AnyFlow | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [turn, setTurn] = useState<TurnState>(IDLE);

  const reload = useCallback(() => getFlow(meta.id).then(setFlow), [meta.id]);
  useEffect(() => { reload().catch((e) => setError(String(e))); }, [reload]);

  const rules = flow && flow.kind !== "document" ? (flow as JourneyFlow) : null;
  const keptCodes = useMemo(() => (rules?.draft && rules.flow
    ? new Set(rules.flow.nodes.map((n) => n.data.block_code).filter((c): c is string => !!c))
    : null), [rules]);

  const act = async (p: Promise<AnyFlow>) => {
    setBusy(true);
    setError(null);
    try {
      setFlow(await p);
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      throw e;
    } finally {
      setBusy(false);
    }
  };
  const sendTurn = async (message: string): Promise<boolean> => {
    setTurn({ pending: true, message, reply: null, outcome: null, advance: null, error: null });
    try {
      const r = await flowTurn(meta.id, { message });
      setFlow(r.flow);
      setTurn({ pending: false, message, reply: r.reply, error: null, advance: null,
        outcome: { mode: r.mode, changes: (r.flow.draft?.ops ?? []).map(describeOp), dropped: [] } });
      return true;
    } catch (e) {
      setTurn((t) => ({ ...t, pending: false, error: e instanceof Error ? e.message : String(e) }));
      return false;
    }
  };
  const dismissTurn = useCallback(() => setTurn(IDLE), []);

  if (error && !flow) return <div className="hier-page"><div className="error-banner">{error}</div></div>;
  if (!flow) return <div className="loading">Loading flow&hellip;</div>;

  const header = (
    <div className="hier-head">
      <div>
        <div className="kit-update-eyebrow">Flow</div>
        <h1 className="kit-update-title">{meta.name} <StatusPill status={meta.status} /></h1>
        <div className="hier-meta">{FLOW_ORIGIN[meta.origin] ?? meta.origin}</div>
      </div>
    </div>
  );

  if (flow.kind === "document") {
    const d = flow as DocumentFlow;
    return (
      <div className="hier-page">
        {header}
        <section className="jc-card">
          <div className="hier-row">
            <span>{d.frozen ? "A frozen copy of the diagram from when this campaign was moved to another brand."
              : "This is the Campaign Plan's Operations diagram. Edit it in the Campaign Plan."}</span>
            {!d.frozen && <a className="jc-btn jc-btn-keep" href={href({ kind: "campaign-plan", brand, planId, campaignId })}>Open Campaign Plan</a>}
          </div>
          {d.document ? <div className="jc-flow-frame"><DocumentDiagram doc={d.document} /></div>
            : <div className="jc-empty">No diagram saved yet.</div>}
        </section>
      </div>
    );
  }

  const f = flow as JourneyFlow;
  const shown = f.draft?.flow ?? f.flow ?? null;
  const draftOps = f.draft?.ops ?? [];
  const confirmed = meta.status === "confirmed";
  return (
    <div className="hier-page">
      {header}
      <section className="jc-card">
        {f.status === "waiting" && <div className="jc-waiting">This flow is waiting on the brand's {f.waiting.join(", ")}.</div>}
        {f.status !== "waiting" && (
          <div className="draft-bar-actions">
            <button type="button" className="jc-btn jc-btn-keep" disabled={busy || draftOps.length > 0}
              onClick={() => { act(buildFlow(meta.id)).catch(() => undefined); }}>
              {busy ? "Working…" : f.status === "built" ? "Rebuild flow" : "Build flow"}
            </button>
          </div>
        )}
        {error && <div className="step-chat-error" role="alert">{error}</div>}
        {f.status === "built" && <DriftBanner campaignId={campaignId} reloadKey={flow} onUpdated={() => { void reload(); onChanged(); }} subject="This flow" />}
        {f.dropped.length > 0 && (
          <div className="jc-waiting">
            {f.dropped.length} kept edit{f.dropped.length === 1 ? "" : "s"} could not be reapplied:
            <ul className="jc-flow-ops">{f.dropped.map((d, i) => <li key={i}>{describeOp(d.op)} ({d.reason})</li>)}</ul>
          </div>
        )}
        {f.draft && (
          <div className="jc-flow-draft-note">
            Draft edit, not kept yet:
            <ul className="jc-flow-ops">{draftOps.map((op, i) => <li key={i}>{describeOp(op)}</li>)}</ul>
          </div>
        )}
        {shown && <div className={f.draft ? "jc-flow-frame is-draft" : "jc-flow-frame"}><FlowDiagram flow={shown} keptCodes={keptCodes} /></div>}
      </section>
      {f.status === "built" && (
        <StepChat brand={brand} step="flow" stepLabel="Flow" question={null} earlierCount={0}
          idlePrompt="Tell me what to change in this flow, for example: add an SMS reminder after B3."
          turn={turn} locked={false} onSend={sendTurn} onDismiss={dismissTurn} unit="flow"
          drafts={{
            count: draftOps.length, status: confirmed ? "confirmed" : "drafted", busy, confirmBlocked: null, error: null, complete: true,
            onKeep: () => act(flowAction(meta.id, "keep")),
            onUndo: () => act(flowAction(meta.id, "undo")),
            onConfirm: () => act(flowAction(meta.id, "confirm")),
            onReopen: () => act(flowAction(meta.id, "reopen")),
          }} />
      )}
    </div>
  );
}
