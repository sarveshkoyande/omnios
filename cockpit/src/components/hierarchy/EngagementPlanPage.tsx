import { useState } from "react";
import { createCampaign, startCampaignPlan, updatePlan } from "../../api";
import { go, href } from "../../route";
import type { TreePlan } from "../../types";
import { CreateForm, periodLabel, StatusPill, when } from "./shared";

/** An engagement plan: its period and status, and its campaigns (F-R2). */
export function EngagementPlanPage({ brand, plan, onChanged }: { brand: string; plan: TreePlan; onChanged: () => void }) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(plan.name);
  const [start, setStart] = useState(plan.period_start ?? "");
  const [end, setEnd] = useState(plan.period_end ?? "");
  const [start2, setStart2] = useState<"plan" | "flows">("plan");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = <T,>(p: Promise<T>): Promise<T> => {
    setBusy(true);
    setError(null);
    return p.catch((e) => { setError(e instanceof Error ? e.message : String(e)); throw e; }).finally(() => setBusy(false));
  };

  const save = () => run(updatePlan(plan.id, { name: name.trim(), period_start: start || null, period_end: end || null }))
    .then(() => { setEditing(false); onChanged(); }).catch(() => undefined);
  const setStatus = (status: "active" | "closed") => run(updatePlan(plan.id, { status })).then(onChanged).catch(() => undefined);

  const newCampaign = (campaignName: string) => run((async () => {
    const c = await createCampaign(plan.id, campaignName);
    if (start2 === "plan") {
      await startCampaignPlan(c.id);
      onChanged();
      go({ kind: "campaign-plan", brand, planId: plan.id, campaignId: c.id });
    } else {
      onChanged();
      go({ kind: "campaign", brand, planId: plan.id, campaignId: c.id });
    }
  })()).catch(() => undefined);

  const closed = plan.status === "closed";
  return (
    <div className="hier-page">
      <div className="hier-head">
        <div>
          <div className="kit-update-eyebrow">Engagement plan</div>
          {editing ? (
            <div className="hier-edit">
              <input className="jc-input" value={name} onChange={(e) => setName(e.target.value)} aria-label="Engagement plan name" />
              <div className="hier-period">
                <label>Starts <input type="date" className="jc-input" value={start} onChange={(e) => setStart(e.target.value)} /></label>
                <label>Ends <input type="date" className="jc-input" value={end} onChange={(e) => setEnd(e.target.value)} /></label>
              </div>
              <div className="hier-create-actions">
                <button type="button" className="jc-btn jc-btn-keep" disabled={busy || !name.trim()} onClick={save}>Save</button>
                <button type="button" className="jc-btn jc-btn-ghost" onClick={() => setEditing(false)}>Cancel</button>
              </div>
            </div>
          ) : (
            <>
              <h1 className="kit-update-title">{plan.name} <StatusPill status={plan.status} /></h1>
              <div className="hier-meta">{periodLabel(plan.period_start, plan.period_end) ?? "No period set"} · created {when(plan.created_at)}</div>
            </>
          )}
        </div>
        {!editing && (
          <div className="hier-head-actions">
            <button type="button" className="jc-btn" onClick={() => setEditing(true)}>Edit</button>
            <button type="button" className="jc-btn" disabled={busy} onClick={() => setStatus(closed ? "active" : "closed")}>
              {closed ? "Reopen plan" : "Close plan"}
            </button>
          </div>
        )}
      </div>
      {error && <div className="step-chat-error" role="alert">{error}</div>}

      <section className="jc-card">
        <div className="hier-section-head">
          <h2>Campaigns</h2>
          {!closed && (
            <CreateForm label="New campaign" placeholder="Campaign name" busy={busy} error={null} onSubmit={newCampaign}>
              <fieldset className="hier-choice">
                <legend>Start with</legend>
                <label><input type="radio" checked={start2 === "plan"} onChange={() => setStart2("plan")} />
                  <span><strong>A campaign plan</strong> — phased, reviewed at each step</span></label>
                <label><input type="radio" checked={start2 === "flows"} onChange={() => setStart2("flows")} />
                  <span><strong>Flows only</strong> — go straight to channel sequences</span></label>
              </fieldset>
            </CreateForm>
          )}
        </div>
        {plan.campaigns.length === 0 ? <div className="jc-empty">No campaigns yet.</div> : (
          <table className="hier-table">
            <thead><tr><th>Campaign</th><th>Status</th><th>Campaign Plan</th><th>Flows</th><th>Brand content</th><th>Updated</th></tr></thead>
            <tbody>
              {plan.campaigns.map((c) => (
                <tr key={c.id}>
                  <td><a href={href({ kind: "campaign", brand, planId: plan.id, campaignId: c.id })}>{c.name}</a></td>
                  <td><StatusPill status={c.status} /></td>
                  <td>{c.has_campaign_plan ? (c.versions ? `v${c.versions}` : "Started") : "—"}</td>
                  <td>{c.flows.length}</td>
                  <td>{!c.content.tracked ? <span className="hier-hint">Not tracked</span>
                    : c.content.changed_steps.length ? <span className="hier-warn">Changed: {c.content.changed_steps.join(", ")}</span> : "Up to date"}</td>
                  <td>{when(c.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
