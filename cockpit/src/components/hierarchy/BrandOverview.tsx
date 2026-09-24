import { useMemo, useState } from "react";
import { createPlan, scheduleCampaign } from "../../api";
import { go, href } from "../../route";
import type { BrandKit, BrandTree, TreeCampaign, TreePlan } from "../../types";
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
export function BrandOverview({ brand, tree, kit, onChanged }: {
  brand: string; tree: BrandTree; kit: BrandKit | null; onChanged: () => void;
}) {
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

          <div className="hier-master-divider" aria-hidden />

          <div className="hier-master-detail">
            {selected && <PlanDetail brand={brand} plan={selected} kit={kit} onChanged={onChanged} />}
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

/** A stable pseudo-random ratio in [0, 1) from a string seed -- used only where this page
 *  has no real number to show and needs one anyway (Budget/HCP funnel fallbacks), so the
 *  same plan always renders the same illustrative figures instead of reshuffling on every
 *  visit. Never used where a real value exists. */
function seeded(seed: string, salt = 0): number {
  let h = salt || 7;
  for (let i = 0; i < seed.length; i++) h = (Math.imul(h, 31) + seed.charCodeAt(i)) >>> 0;
  return (h % 10000) / 10000;
}

const money = (n: number) => `$${(n / 1000).toLocaleString(undefined, { maximumFractionDigits: 0 })}K`;

/** The plan's objective, spelled out large -- the one real fact worth headlining. An
 *  engagement plan has no objective field of its own; this reads the brand's (BrandKit's
 *  key_objective, same as the Brief & kit tab), because every plan under a brand shares it.
 *  Absent kit data gets the same honest fallback the rest of the app uses, not an invented
 *  objective. */
function PlanObjective({ kit, brand }: { kit: BrandKit | null; brand: string }) {
  return (
    <div className="hier-punch-card hier-objective">
      <span className="hier-punch-icon"><Icon name="target" size={20} /></span>
      <div className="hier-punch-body">
        <div className="hier-detail-subhead">Objective</div>
        {kit?.key_objective ? (
          <p className="hier-objective-text">{kit.key_objective}</p>
        ) : (
          <p className="hier-objective-text hier-objective-missing">
            No objective captured for {brand} yet.{" "}
            <a href={href({ kind: "journey", brand, step: "brief" })}>Set one in the Brief step →</a>
          </p>
        )}
        {kit?.success_measure && <p className="hier-objective-metric">Measured by {kit.success_measure.toLowerCase()}</p>}
      </div>
    </div>
  );
}

/** Budget, spaciously -- real money when a Campaign Plan run has written it (campaign.
 *  total_budget, from the Budget stage) onto any campaign in this plan; an illustrative,
 *  clearly-labelled split otherwise, so the section is never an empty box while still never
 *  passing off a made-up number as real. */
function PlanBudget({ brand, plan }: { brand: string; plan: TreePlan }) {
  const real = plan.campaigns.filter((c) => (c.total_budget ?? 0) > 0);
  const isReal = real.length > 0;
  const rows: { name: string; value: number; campaignId: number }[] = isReal
    ? real.map((c) => ({ name: c.name, value: c.total_budget!, campaignId: c.id }))
    : (plan.campaigns.length > 0 ? plan.campaigns : [{ id: 0, name: plan.name } as TreeCampaign]).map((c, i) => {
        const base = 250000 + seeded(`${brand}:${plan.id}:${c.id || i}`, 11) * 650000;
        return { name: c.name, value: Math.round(base / 5000) * 5000, campaignId: c.id };
      });
  const total = rows.reduce((n, r) => n + r.value, 0);
  const max = Math.max(...rows.map((r) => r.value), 1);

  return (
    <div className="hier-punch-card hier-budget">
      <span className="hier-punch-icon"><Icon name="wallet" size={20} /></span>
      <div className="hier-punch-body">
        <div className="hier-budget-head">
          <div className="hier-detail-subhead">Budget</div>
          {!isReal && <span className="illustrative-tag">Illustrative</span>}
        </div>
        <div className="hier-budget-total">{money(total)}</div>
        <div className="hier-budget-bars">
          {rows.map((r) => (
            <div className="hier-budget-bar-row" key={r.campaignId || r.name}>
              <span className="hier-budget-bar-label">{r.name}</span>
              <div className="hier-budget-bar-track">
                <div className="hier-budget-bar-fill" style={{ width: `${Math.max((r.value / max) * 100, 6)}%` }} />
              </div>
              <span className="hier-budget-bar-value">{money(r.value)}</span>
            </div>
          ))}
        </div>
        {!isReal && <p className="hier-detail-panel-note">No campaign here has run a Campaign Plan's Budget stage yet — shown split is a placeholder, not a committed number.</p>}
      </div>
    </div>
  );
}

const FUNNEL_STAGES = ["Awareness", "Consideration", "Trial", "Adoption"];

/** HCP funnel performance, as a shrinking-width funnel rather than a sentence. There's no
 *  measured funnel wired to a plan yet, so this is an illustrative, clearly-labelled
 *  distribution (seeded by brand so it's stable, not reshuffled) -- the same
 *  "illustrative heuristic" convention strategy/segment_profile.py already uses for the
 *  HCP adoption ladder elsewhere in this app. */
function HcpFunnel({ brand, plan }: { brand: string; plan: TreePlan }) {
  const seed = `${brand}:${plan.id}:funnel`;
  let pct = 100;
  const stages = FUNNEL_STAGES.map((label, i) => {
    const value = pct;
    pct = Math.round(pct * (0.45 + seeded(seed, i + 1) * 0.3));
    return { label, pct: value };
  });
  return (
    <div className="hier-punch-card hier-funnel">
      <span className="hier-punch-icon"><Icon name="users" size={20} /></span>
      <div className="hier-punch-body">
        <div className="hier-budget-head">
          <div className="hier-detail-subhead">HCP funnel performance</div>
          <span className="illustrative-tag">Illustrative</span>
        </div>
        <div className="hier-funnel-stages">
          {stages.map((s) => (
            <div className="hier-funnel-stage" key={s.label}>
              <div className="hier-funnel-bar-wrap">
                <div className="hier-funnel-bar" style={{ width: `${Math.max(s.pct, 8)}%` }} />
              </div>
              <span className="hier-funnel-label">{s.label}</span>
              <span className="hier-funnel-pct">{s.pct}%</span>
            </div>
          ))}
        </div>
        <p className="hier-detail-panel-note">Modeled distribution across the HCP adoption ladder -- not measured performance.</p>
      </div>
    </div>
  );
}

const DAY_MS = 86400000;
const toMs = (d: string) => new Date(`${d}T00:00:00`).getTime();
const iso = (ms: number) => new Date(ms).toISOString().slice(0, 10);

/** What range to plot: the campaigns' own dates (start_date/end_date, falling back to
 *  created_at..closed_at-or-today when unset) widened to cover the plan's own period when
 *  it has one -- so a campaign scheduled outside the plan's period is still visible. */
function timelineDomain(plan: TreePlan, ranges: Map<number, [number, number]>): [number, number] | null {
  const points: number[] = [];
  if (plan.period_start) points.push(toMs(plan.period_start));
  if (plan.period_end) points.push(toMs(plan.period_end));
  for (const [s, e] of ranges.values()) { points.push(s); points.push(e); }
  if (points.length === 0) return null;
  const min = Math.min(...points);
  const max = Math.max(...points, min + DAY_MS);
  const pad = Math.max((max - min) * 0.03, DAY_MS);
  return [min - pad, max + pad];
}

/** Campaigns laid out on a shared horizontal axis so it's clear at a glance which one runs
 *  when. Undated campaigns (the common case today) are listed below the axis instead of
 *  guessed onto it, with a one-click way to schedule them. */
function CampaignTimeline({ brand, plan, onChanged }: { brand: string; plan: TreePlan; onChanged: () => void }) {
  const [editing, setEditing] = useState<number | null>(null);

  const ranges = useMemo(() => {
    const m = new Map<number, [number, number]>();
    for (const c of plan.campaigns) {
      if (!c.start_date && !c.end_date) continue;
      const s = c.start_date ? toMs(c.start_date) : toMs(c.end_date!);
      const e = c.end_date ? toMs(c.end_date) : Math.max(s, Date.now());
      m.set(c.id, [s, Math.max(s, e)]);
    }
    return m;
  }, [plan.campaigns]);

  const domain = timelineDomain(plan, ranges);
  const scheduled = plan.campaigns.filter((c) => ranges.has(c.id));
  const unscheduled = plan.campaigns.filter((c) => !ranges.has(c.id));
  const today = Date.now();

  const save = (campaignId: number, s: string, e: string) => {
    scheduleCampaign(campaignId, s || null, e || null).then(() => { setEditing(null); onChanged(); }).catch(() => undefined);
  };

  return (
    <div className="hier-timeline">
      <div className="hier-detail-subhead">Timeline</div>
      {domain && scheduled.length > 0 && (
        <div className="hier-timeline-axis">
          <div className="hier-timeline-scale">
            <span>{iso(domain[0])}</span>
            <span>{iso(domain[1])}</span>
          </div>
          <div className="hier-timeline-track">
            {domain[0] <= today && today <= domain[1] && (
              <div className="hier-timeline-today" style={{ left: `${((today - domain[0]) / (domain[1] - domain[0])) * 100}%` }} title="Today" />
            )}
          </div>
          {scheduled.map((c) => {
            const [s, e] = ranges.get(c.id)!;
            const left = ((s - domain[0]) / (domain[1] - domain[0])) * 100;
            const width = Math.max(((e - s) / (domain[1] - domain[0])) * 100, 1.2);
            return (
              <div className="hier-timeline-row" key={c.id}>
                <a className="hier-timeline-label" href={href({ kind: "campaign", brand, planId: plan.id, campaignId: c.id })}>{c.name}</a>
                <div className="hier-timeline-lane">
                  <div className={`hier-timeline-bar bar-status-${c.status}`} style={{ left: `${left}%`, width: `${width}%` }}
                    title={`${c.start_date ?? "?"} – ${c.end_date ?? "ongoing"}`} />
                </div>
              </div>
            );
          })}
        </div>
      )}
      {scheduled.length === 0 && <p className="hier-hint">No campaigns are scheduled yet — set dates on a campaign below to plot it here.</p>}

      {unscheduled.length > 0 && (
        <div className="hier-timeline-unscheduled">
          {unscheduled.map((c) => (
            <ScheduleRow key={c.id} brand={brand} plan={plan} campaign={c}
              editing={editing === c.id} onEdit={() => setEditing(c.id)} onCancel={() => setEditing(null)} onSave={save} />
          ))}
        </div>
      )}
    </div>
  );
}

function ScheduleRow({ brand, plan, campaign, editing, onEdit, onCancel, onSave }: {
  brand: string; plan: TreePlan; campaign: TreeCampaign; editing: boolean;
  onEdit: () => void; onCancel: () => void; onSave: (campaignId: number, start: string, end: string) => void;
}) {
  const [s, setS] = useState(campaign.start_date ?? "");
  const [e, setE] = useState(campaign.end_date ?? "");
  if (!editing) {
    return (
      <div className="hier-timeline-row hier-timeline-row-unscheduled">
        <a className="hier-timeline-label" href={href({ kind: "campaign", brand, planId: plan.id, campaignId: campaign.id })}>{campaign.name}</a>
        <button type="button" className="hier-timeline-schedule-btn" onClick={onEdit}>Set dates</button>
      </div>
    );
  }
  return (
    <div className="hier-timeline-row hier-timeline-row-unscheduled">
      <span className="hier-timeline-label">{campaign.name}</span>
      <div className="hier-period">
        <label>From <input type="date" className="jc-input" value={s} onChange={(ev) => setS(ev.target.value)} /></label>
        <label>To <input type="date" className="jc-input" value={e} onChange={(ev) => setE(ev.target.value)} /></label>
        <button type="button" className="jc-btn jc-btn-keep" onClick={() => onSave(campaign.id, s, e)}>Save</button>
        <button type="button" className="jc-btn jc-btn-ghost" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  );
}

function PlanDetail({ brand, plan, kit, onChanged }: { brand: string; plan: TreePlan; kit: BrandKit | null; onChanged: () => void }) {
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

      <PlanObjective kit={kit} brand={brand} />
      <PlanBudget brand={brand} plan={plan} />
      <HcpFunnel brand={brand} plan={plan} />

      {plan.campaigns.length > 0 && <CampaignTimeline brand={brand} plan={plan} onChanged={onChanged} />}

      <a className="hier-brief-link" href={href({ kind: "brand", brand, tab: "workspace" })}>
        <Icon name="document" size={15} /> View the full brief &amp; kit <Icon name="arrowRight" size={13} />
      </a>

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
