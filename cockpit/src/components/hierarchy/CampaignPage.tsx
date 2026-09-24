import { useEffect, useState } from "react";
import { createFlow, getJourney, renameCampaign, startCampaignPlan } from "../../api";
import { go, href } from "../../route";
import type { JourneyStepId, TreeCampaign } from "../../types";
import { DriftBanner } from "../DriftBanner";
import { CreateForm, FLOW_ORIGIN, StatusPill, when } from "./shared";

const STEP_LABEL: Record<string, string> = { brief: "Brief", audience: "Audience", message: "Message", kit: "Kit", flow: "Flow" };

/** A campaign: its Campaign Plan (optional) and its flows (F-R3, F-R4, F-R5). */
export function CampaignPage({ brand, planId, campaign, onChanged }: {
  brand: string; planId: number; campaign: TreeCampaign; onChanged: () => void;
}) {
  const [waiting, setWaiting] = useState<JourneyStepId[] | null>(null);
  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState(campaign.name);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const closed = campaign.status === "closed";

  useEffect(() => {
    let live = true;
    getJourney(brand).then((s) => { if (live) setWaiting(s.steps.find((x) => x.step === "flow")?.waiting ?? []); })
      .catch(() => { if (live) setWaiting([]); });
    return () => { live = false; };
  }, [brand]);

  const run = <T,>(p: Promise<T>): Promise<T> => {
    setBusy(true);
    setError(null);
    return p.catch((e) => { setError(e instanceof Error ? e.message : String(e)); throw e; }).finally(() => setBusy(false));
  };
  const startPlan = () => run(startCampaignPlan(campaign.id)).then(() => {
    onChanged();
    go({ kind: "campaign-plan", brand, planId, campaignId: campaign.id });
  }).catch(() => undefined);
  const addFlow = (flowName: string) => run(createFlow(campaign.id, flowName)).then((f) => {
    onChanged();
    const id = "flow_id" in f ? f.flow_id : null;
    if (id) go({ kind: "flow", brand, planId, campaignId: campaign.id, flowId: id });
  }).catch(() => undefined);
  const rename = () => run(renameCampaign(campaign.id, name.trim())).then(() => { setRenaming(false); onChanged(); }).catch(() => undefined);

  return (
    <div className="hier-page">
      <div className="hier-head">
        <div>
          <div className="kit-update-eyebrow">Campaign</div>
          {renaming ? (
            <div className="hier-edit">
              <input className="jc-input" value={name} onChange={(e) => setName(e.target.value)} aria-label="Campaign name" />
              <div className="hier-create-actions">
                <button type="button" className="jc-btn jc-btn-keep" disabled={busy || !name.trim()} onClick={rename}>Save</button>
                <button type="button" className="jc-btn jc-btn-ghost" onClick={() => setRenaming(false)}>Cancel</button>
              </div>
            </div>
          ) : (
            <h1 className="kit-update-title">{campaign.name} <StatusPill status={campaign.status} /></h1>
          )}
          <div className="hier-meta">Created {when(campaign.created_at)}{closed && campaign.closed_at ? ` · closed ${when(campaign.closed_at)}` : ""}</div>
        </div>
        {!renaming && !closed && <div className="hier-head-actions"><button type="button" className="jc-btn" onClick={() => setRenaming(true)}>Rename</button></div>}
      </div>
      {error && <div className="step-chat-error" role="alert">{error}</div>}
      {!closed && <DriftBanner campaignId={campaign.id} reloadKey={campaign.updated_at} onUpdated={onChanged} />}

      <section className="jc-card">
        <div className="hier-section-head"><h2>Campaign Plan</h2></div>
        {campaign.has_campaign_plan ? (
          <div className="hier-row">
            <span>{campaign.versions ? `Version ${campaign.versions} deployed` : "In progress"} — the phased plan for this campaign.</span>
            <a className="jc-btn jc-btn-keep" href={href({ kind: "campaign-plan", brand, planId, campaignId: campaign.id })}>Open Campaign Plan</a>
          </div>
        ) : (
          <div className="hier-row">
            <span className="hier-hint">No Campaign Plan. A campaign can be flows only, or start one any time.</span>
            {!closed && <button type="button" className="jc-btn" disabled={busy} onClick={startPlan}>Start a Campaign Plan</button>}
          </div>
        )}
      </section>

      <section className="jc-card">
        <div className="hier-section-head">
          <h2>Flows</h2>
          {!closed && waiting !== null && (waiting.length > 0 ? (
            <span className="hier-needs">
              New flows need the brand's{" "}
              {waiting.map((s, i) => (
                <span key={s}>{i > 0 ? ", " : ""}<a href={href({ kind: "journey", brand, step: s })}>{STEP_LABEL[s]}</a></span>
              ))}{" "}confirmed first.
            </span>
          ) : (
            <CreateForm label="New flow" placeholder="Flow name, e.g. Email nurture" busy={busy} error={null} onSubmit={addFlow} submitLabel="Build flow" />
          ))}
        </div>
        {campaign.flows.length === 0 ? <div className="jc-empty">No flows yet.</div> : (
          <ul className="hier-list">
            {campaign.flows.map((f) => (
              <li key={f.id}>
                <a href={href({ kind: "flow", brand, planId, campaignId: campaign.id, flowId: f.id })}>{f.name}</a>
                <StatusPill status={f.status} />
                <span className="hier-meta">{FLOW_ORIGIN[f.origin] ?? f.origin} · updated {when(f.updated_at)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
