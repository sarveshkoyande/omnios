import { useMemo, useState } from "react";
import { createPlan } from "../../api";
import { go, href } from "../../route";
import type { BrandTree } from "../../types";
import { CreateForm, periodLabel, StatusPill, when } from "./shared";

/** Idea 7: a brand's engagement plans, their campaigns and flows, with status rolled up. */
export function BrandOverview({ brand, tree, onChanged }: { brand: string; tree: BrandTree; onChanged: () => void }) {
  const [planStatus, setPlanStatus] = useState<"all" | "active" | "closed">("all");
  const [campaignStatus, setCampaignStatus] = useState<"all" | "open" | "closed">("all");
  const [driftOnly, setDriftOnly] = useState(false);
  const [expanded, setExpanded] = useState<Set<number>>(() => new Set(tree.engagement_plans.filter((p) => p.status === "active").map((p) => p.id)));
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const all = tree.engagement_plans;
  const campaigns = all.flatMap((p) => p.campaigns);
  const summary = {
    plans: all.filter((p) => p.status === "active").length,
    campaigns: campaigns.filter((c) => c.status !== "closed").length,
    flows: campaigns.reduce((n, c) => n + c.flows.length, 0),
    drift: campaigns.filter((c) => c.status !== "closed" && c.content.changed_steps.length > 0).length,
  };

  const plans = useMemo(() => all
    .filter((p) => planStatus === "all" || p.status === planStatus)
    .map((p) => ({
      ...p,
      shown: p.campaigns.filter((c) =>
        (campaignStatus === "all" || (campaignStatus === "closed" ? c.status === "closed" : c.status !== "closed"))
        && (!driftOnly || c.content.changed_steps.length > 0)),
    }))
    .filter((p) => !driftOnly || p.shown.length > 0), [all, planStatus, campaignStatus, driftOnly]);

  const create = (name: string) => {
    setBusy(true);
    setError(null);
    createPlan(brand, { name, period_start: start || null, period_end: end || null })
      .then((p) => { onChanged(); go({ kind: "plan", brand, planId: p.id }); })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setBusy(false));
  };

  const toggle = (id: number) => setExpanded((s) => {
    const n = new Set(s);
    if (n.has(id)) n.delete(id); else n.add(id);
    return n;
  });

  return (
    <div className="hier-page">
      <div className="hier-head">
        <div>
          <div className="kit-update-eyebrow">Brand overview</div>
          <h1 className="kit-update-title">{brand}</h1>
        </div>
        <CreateForm label="New engagement plan" placeholder="Engagement plan name, e.g. Q3 2026" busy={busy} error={error} onSubmit={create}>
          <div className="hier-period">
            <label>Starts <input type="date" className="jc-input" value={start} onChange={(e) => setStart(e.target.value)} /></label>
            <label>Ends <input type="date" className="jc-input" value={end} onChange={(e) => setEnd(e.target.value)} /></label>
            <span className="hier-hint">Optional</span>
          </div>
        </CreateForm>
      </div>

      <div className="hier-summary" aria-label="Summary">
        <span><strong>{summary.plans}</strong> active engagement plan{summary.plans === 1 ? "" : "s"}</span>
        <span><strong>{summary.campaigns}</strong> open campaign{summary.campaigns === 1 ? "" : "s"}</span>
        <span><strong>{summary.flows}</strong> flow{summary.flows === 1 ? "" : "s"}</span>
        <span className={summary.drift ? "hier-summary-warn" : ""}><strong>{summary.drift}</strong> with changed brand content</span>
      </div>

      {all.length === 0 ? (
        <div className="jc-card hier-empty">
          <p>No engagement plans yet. An engagement plan groups a period's campaigns, for example a quarter.</p>
          <p className="hier-hint">Use “+ New engagement plan” above to start one.</p>
        </div>
      ) : (
        <>
          <div className="hier-filters">
            <label>Plans
              <select className="jc-input" value={planStatus} onChange={(e) => setPlanStatus(e.target.value as typeof planStatus)}>
                <option value="all">All</option><option value="active">Active</option><option value="closed">Closed</option>
              </select>
            </label>
            <label>Campaigns
              <select className="jc-input" value={campaignStatus} onChange={(e) => setCampaignStatus(e.target.value as typeof campaignStatus)}>
                <option value="all">All</option><option value="open">Open</option><option value="closed">Closed</option>
              </select>
            </label>
            <label className="hier-check"><input type="checkbox" checked={driftOnly} onChange={(e) => setDriftOnly(e.target.checked)} /> Changed brand content only</label>
          </div>
          {plans.length === 0 && <div className="jc-empty">Nothing matches these filters.</div>}
          {plans.map((p) => {
            const open = expanded.has(p.id);
            const drifted = p.campaigns.filter((c) => c.content.changed_steps.length > 0).length;
            return (
              <section key={p.id} className="jc-card hier-plan">
                <div className="hier-plan-head">
                  <button type="button" className="hier-expand" aria-expanded={open} onClick={() => toggle(p.id)}>{open ? "▾" : "▸"}</button>
                  <a className="hier-plan-name" href={href({ kind: "plan", brand, planId: p.id })}>{p.name}</a>
                  <StatusPill status={p.status} />
                  <span className="hier-meta">
                    {periodLabel(p.period_start, p.period_end) ?? "No period"} · {p.campaigns.length} campaign{p.campaigns.length === 1 ? "" : "s"}
                    {" · "}{p.campaigns.reduce((n, c) => n + c.flows.length, 0)} flows{drifted ? ` · ${drifted} with changed content` : ""}
                  </span>
                </div>
                {open && (
                  p.shown.length === 0 ? <div className="jc-empty hier-indent">No campaigns{p.campaigns.length ? " match" : " yet"}.</div> : (
                    <table className="hier-table">
                      <thead><tr><th>Campaign</th><th>Status</th><th>Campaign Plan</th><th>Flows</th><th>Brand content</th><th>Updated</th></tr></thead>
                      <tbody>
                        {p.shown.map((c) => (
                          <tr key={c.id}>
                            <td><a href={href({ kind: "campaign", brand, planId: p.id, campaignId: c.id })}>{c.name}</a></td>
                            <td><StatusPill status={c.status} /></td>
                            <td>{c.has_campaign_plan ? (c.versions ? `v${c.versions}` : "Started") : "—"}</td>
                            <td>{c.flows.length}</td>
                            <td>{!c.content.tracked ? <span className="hier-hint">Not tracked</span>
                              : c.content.changed_steps.length ? <span className="hier-warn">Changed: {c.content.changed_steps.join(", ")}</span>
                              : "Up to date"}</td>
                            <td>{when(c.updated_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )
                )}
              </section>
            );
          })}
        </>
      )}
    </div>
  );
}
