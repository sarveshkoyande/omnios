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

/** The brand's brief and message context -- an engagement plan has none of its own; this is
 *  the same brand kit the Brief & kit tab reads, in words. Every sentence is built only from
 *  fields the kit actually carries (BrandKit's own optional-field discipline). */
function BriefContext({ kit }: { kit: BrandKit | null }) {
  if (!kit) return null;
  const brief: string[] = [];
  if (kit.indication) brief.push(`indicated for ${kit.indication}`);
  if (kit.lifecycle_stage) brief.push(`at the ${kit.lifecycle_stage.toLowerCase()} stage`);
  const briefSentence = brief.length ? `${kit.company || "This brand"} is ${brief.join(", ")}.` : null;

  const objective = kit.key_objective ? `The current objective is ${kit.key_objective.toLowerCase().replace(/\.$/, "")}.` : null;
  const metric = kit.success_measure ? `Success is measured by ${kit.success_measure.toLowerCase()}.` : null;
  const audience = kit.primary_audience ? `It's aimed primarily at ${kit.primary_audience.toLowerCase()}.` : null;
  const message = kit.positioning_statement ? `Positioned as: “${kit.positioning_statement}”` : kit.core_claim ? `Core claim: “${kit.core_claim}”` : null;

  if (!briefSentence && !objective && !metric && !audience && !message) return null;

  return (
    <div className="hier-brief">
      <div className="hier-detail-subhead">Brief &amp; message</div>
      {(briefSentence || objective) && <p className="hier-detail-summary">{[briefSentence, objective].filter(Boolean).join(" ")}</p>}
      {(audience || metric) && <p className="hier-detail-summary">{[audience, metric].filter(Boolean).join(" ")}</p>}
      {message && <p className="hier-detail-summary hier-brief-message">{message}</p>}
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

      <BriefContext kit={kit} />

      {plan.campaigns.length > 0 && <CampaignTimeline brand={brand} plan={plan} onChanged={onChanged} />}

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
