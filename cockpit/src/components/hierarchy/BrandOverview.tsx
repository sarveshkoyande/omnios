import { useMemo, useState } from "react";
import { createPlan } from "../../api";
import { go, href } from "../../route";
import type { BrandTree, TreePlan } from "../../types";
import { Icon } from "../Icon";
import { CreateForm, periodLabel, StatusPill, when } from "./shared";

/** The launcher card, cropped to just its own size and anchored bottom-right (not a
 *  full-width sticky bar) -- clicking the AI button opens it, typing a name and sending
 *  starts a new engagement plan the same way "+ New engagement plan" does. */
function PlanLauncher({ brand, plans, onChanged }: { brand: string; plans: TreePlan[]; onChanged: () => void }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const latest = plans[0];

  const submit = () => {
    if (!text.trim()) return;
    setBusy(true);
    setError(null);
    createPlan(brand, { name: text.trim() })
      .then((p) => { onChanged(); go({ kind: "plan", brand, planId: p.id }); })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setBusy(false));
  };

  return (
    <>
      {open && (
        <>
          <div className="plan-launcher-backdrop" onClick={() => setOpen(false)} />
          <div className="plan-launcher-card" role="dialog" aria-modal="true" aria-label="Build your next campaign">
            <button type="button" className="plan-launcher-close" aria-label="Close" onClick={() => setOpen(false)}>
              <Icon name="close" size={16} />
            </button>
            <h3>Let&rsquo;s build your next agentic campaign.</h3>
            <p className="plan-launcher-sub">Describe your engagement plan and let AI build and optimize it.</p>
            <div className="plan-launcher-chips">
              <span className="plan-launcher-chip"><Icon name="document" size={16} /><span><b>Brand</b>{brand}</span></span>
              {latest && <span className="plan-launcher-chip"><Icon name="target" size={16} /><span><b>Latest plan</b>{latest.name}</span></span>}
            </div>
            <form className="plan-launcher-form" onSubmit={(e) => { e.preventDefault(); submit(); }}>
              <textarea
                className="jc-input plan-launcher-input"
                rows={2}
                placeholder="Describe what you want to make…"
                value={text}
                disabled={busy}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }}
                autoFocus
              />
              <button type="submit" className="plan-launcher-send" disabled={busy || !text.trim()} aria-label="Send">
                <Icon name="arrowRight" size={20} />
              </button>
            </form>
            {error && <div className="step-chat-error" role="alert">{error}</div>}
          </div>
        </>
      )}
      <button type="button" className="plan-launcher-fab" aria-label="Build with AI" onClick={() => setOpen((v) => !v)}>
        <Icon name="sparkles" size={26} />
      </button>
    </>
  );
}

/** Idea 7: a brand's engagement plans, master-detail -- a searchable one-line list on the
 *  left, the selected plan's campaigns and status on the right. No table, no filters. */
export function BrandOverview({ brand, tree, onChanged }: { brand: string; tree: BrandTree; onChanged: () => void }) {
  const all = tree.engagement_plans;
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(all[0]?.id ?? null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? all.filter((p) => p.name.toLowerCase().includes(q)) : all;
  }, [all, query]);

  const selected = all.find((p) => p.id === selectedId) ?? filtered[0] ?? null;

  const create = (name: string) => {
    setBusy(true);
    setError(null);
    createPlan(brand, { name })
      .then((p) => { onChanged(); go({ kind: "plan", brand, planId: p.id }); })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setBusy(false));
  };

  return (
    <div className="hier-page hier-page-master">
      <div className="hier-head">
        <div>
          <div className="kit-update-eyebrow">Brand overview</div>
          <h1 className="kit-update-title">{brand}</h1>
        </div>
        <CreateForm label="New engagement plan" placeholder="Engagement plan name, e.g. Q4 2026 HFrEF Launch Push" busy={busy} error={error} onSubmit={create} />
      </div>

      {all.length === 0 ? (
        <div className="jc-card hier-empty">
          <p>No engagement plans yet. An engagement plan groups a period&rsquo;s campaigns, for example a quarter.</p>
          <p className="hier-hint">Use “+ New engagement plan” above to start one.</p>
        </div>
      ) : (
        <div className="hier-master">
          <div className="hier-master-list">
            <div className="hier-search">
              <Icon name="search" size={15} />
              <input
                className="hier-search-input"
                placeholder="Search plans…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                aria-label="Search engagement plans"
              />
            </div>
            <div className="hier-plan-list" role="listbox" aria-label="Engagement plans">
              {filtered.length === 0 && <div className="jc-empty">No plans match “{query}”.</div>}
              {filtered.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  role="option"
                  aria-selected={selected?.id === p.id}
                  className={`hier-plan-row ${selected?.id === p.id ? "active" : ""}`}
                  onClick={() => setSelectedId(p.id)}
                >
                  <span className="hier-plan-row-name">{p.name}</span>
                  <span className="hier-plan-row-sub">
                    {periodLabel(p.period_start, p.period_end) ?? `${p.campaigns.length} campaign${p.campaigns.length === 1 ? "" : "s"}`}
                  </span>
                </button>
              ))}
            </div>
          </div>

          <div className="hier-master-detail">
            {selected && <PlanDetail brand={brand} plan={selected} />}
          </div>
        </div>
      )}

      {all.length > 0 && <PlanLauncher brand={brand} plans={all} onChanged={onChanged} />}
    </div>
  );
}

/** A sentence, not a row of pills -- what this plan is, in words, from real fields only
 *  (no invented goals or budgets). */
function planSummary(plan: TreePlan): string {
  const period = periodLabel(plan.period_start, plan.period_end);
  const n = plan.campaigns.length;
  const campaignPhrase = n === 0
    ? "It has no campaigns yet."
    : `It covers ${n} campaign${n === 1 ? "" : "s"}: ${plan.campaigns.map((c) => c.name).join(", ")}.`;
  return `${period ? `Runs ${period}. ` : "No period is set for this plan. "}${campaignPhrase}`;
}

function PlanDetail({ brand, plan }: { brand: string; plan: TreePlan }) {
  const drifted = plan.campaigns.filter((c) => c.content.changed_steps.length > 0).length;
  return (
    <div className="hier-detail-card">
      <div className="hier-detail-head">
        <div>
          <a className="hier-detail-name" href={href({ kind: "plan", brand, planId: plan.id })}>{plan.name}</a>
          <StatusPill status={plan.status} />
        </div>
      </div>

      <p className="hier-detail-summary">{planSummary(plan)}</p>
      {drifted > 0 && (
        <p className="hier-detail-summary hier-summary-warn">
          {drifted} of its campaign{drifted === 1 ? "" : "s"} {drifted === 1 ? "has" : "have"} changed brand content since it was last built.
        </p>
      )}

      <div className="hier-detail-campaigns">
        <div className="hier-detail-subhead">Associated campaigns</div>
        {plan.campaigns.length === 0 ? (
          <p className="hier-hint hier-indent">No campaigns yet.</p>
        ) : (
          plan.campaigns.map((c) => (
            <a key={c.id} className="hier-campaign-row" href={href({ kind: "campaign", brand, planId: plan.id, campaignId: c.id })}>
              <span className="hier-campaign-row-name">{c.name}</span>
              <span className="hier-campaign-row-meta">
                {c.flows.length} flow{c.flows.length === 1 ? "" : "s"} · Updated {when(c.updated_at)}
              </span>
              <StatusPill status={c.status} />
            </a>
          ))
        )}
      </div>
    </div>
  );
}
