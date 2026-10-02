import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createEngagementPlan, engagementAnswer, engagementClarify, engagementDraft, engagementRead,
  getEngagementFramework, getEngagementPlan, listEngagementPlans,
  type EngagementIndustry, type EngagementPlan,
} from "../../api";
import { Icon } from "../../components/Icon";
import type { BrandSummary } from "../../types";
import "../campaignplanner/campaignPlanner.css";
import "../iq.css";
import "./engagement.css";

/** The Engagement Planner (docs/redesign/engagement-plan.md): the next N months for one brand.
 *  Left: the agent conversation, the way the Briefing Agent works (read, ask <=3 questions,
 *  review <=3 assumptions, draft). Right: the plan -- Overview (with funnels), Shift map,
 *  Portfolio, Timeline, Budget. Brand IQ is the only input; every item names its source. */

type Any = Record<string, unknown>;
const txt = (v: unknown) => (v === null || v === undefined ? "" : String(v));
const arr = (v: unknown) => (Array.isArray(v) ? (v as Any[]) : []);
const STEPS = ["Frame", "Read", "Clarify", "Assumptions", "Draft"];
const STEP_INDEX: Record<string, number> = { read: 1, clarify: 2, assumptions: 3, draft: 4 };
type Tab = "overview" | "shifts" | "portfolio" | "timeline" | "budget";

function errText(e: unknown): string {
  const s = String(e);
  const i = s.indexOf("{");  // our API's own JSON error envelope: {"detail": "..."}
  if (i >= 0) {
    try { const d = JSON.parse(s.slice(i)).detail; if (typeof d === "string") return d; } catch { /* not JSON */ }
  }
  return s;
}

export function EngagementPlanner({ brands, activeBrand, planId }: { brands: BrandSummary[]; activeBrand: string | null; planId?: string }) {
  const brand = activeBrand ?? brands[0]?.brand ?? null;
  const [plans, setPlans] = useState<EngagementPlan[]>([]);
  const [plan, setPlan] = useState<EngagementPlan | null>(null);
  const [fw, setFw] = useState<Any | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [months, setMonths] = useState(6);
  const [industry, setIndustry] = useState<EngagementIndustry>("pharma");
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [autoAssume, setAutoAssume] = useState(false);
  const [decisions, setDecisions] = useState<Record<string, { status: string; note?: string }>>({});
  const [tab, setTab] = useState<Tab>("overview");

  const refreshList = useCallback(() => {
    if (!brand) return;
    listEngagementPlans(brand).then((r) => setPlans(r.plans)).catch(() => setPlans([]));
  }, [brand]);
  useEffect(refreshList, [refreshList]);

  useEffect(() => {
    if (!planId) { setPlan(null); return; }
    // Starting a plan sets the URL to its id; don't reload a plan we already hold.
    setPlan((cur) => {
      if (cur?.id !== planId) getEngagementPlan(planId).then(setPlan).catch((e) => setError(errText(e)));
      return cur?.id === planId ? cur : null;
    });
  }, [planId]);

  useEffect(() => {
    const ind = (plan?.industry ?? industry) as EngagementIndustry;
    getEngagementFramework(ind).then(setFw).catch(() => setFw(null));
  }, [plan?.industry, industry]);

  const body = (plan?.body ?? {}) as Any;
  const agent = (body.agent ?? {}) as Any;
  const stepIdx = plan ? (STEP_INDEX[txt(agent.step)] ?? 0) : 0;
  const drafted = agent.step === "draft";

  const run = async (label: string, fn: () => Promise<EngagementPlan>) => {
    setBusy(label); setError(null);
    try { const p = await fn(); setPlan(p); refreshList(); return p; }
    catch (e) { setError(errText(e)); return null; }
    finally { setBusy(null); }
  };

  const start = async () => {
    if (!brand) return;
    const p = await run("Creating the plan…", () => createEngagementPlan({ brand, industry, months }));
    if (!p) return;
    window.location.hash = `#/v3/agent/engagement-planner/${p.id}`;
    const r = await run("Reading Brand IQ…", () => engagementRead(p.id));
    if (r) await run("Looking for real gaps…", () => engagementClarify(p.id));
  };

  const submitAnswers = async () => {
    if (!plan) return;
    const r = await run("Checking assumptions…", () => engagementAnswer(plan.id, answers, autoAssume));
    if (r && autoAssume) await run("Drafting the plan…", () => engagementDraft(plan.id));
  };

  const doDraft = () => plan && run("Drafting the plan…", () => engagementDraft(plan.id, decisions));

  if (!brand) return <p className="v3-empty">Add a brand first: an engagement plan belongs to one brand.</p>;

  return (
    <div className="v3-ws v3-cc v3-ep">
      <div className="v3-ws-top">
        <span className="v3-ep-title">{plan ? plan.title : `New engagement plan — ${brand}`}</span>
        {plan && <span className="v3-ws-save">v{plan.version} · {plan.period_start} → {plan.period_end}{plan.stale ? " · based on an older brand plan — review" : ""}</span>}
        <span className="v3-ws-top-actions">
          {plans.length > 0 && (
            <select className="v3-ep-select" value={plan?.id ?? ""} onChange={(e) => { window.location.hash = e.target.value ? `#/v3/agent/engagement-planner/${e.target.value}` : "#/v3/agent/engagement-planner"; }}>
              <option value="">+ New plan</option>
              {plans.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
            </select>
          )}
        </span>
      </div>

      <div className="v3-ws-body">
        <aside className="v3-ws-inputs">
          <div className="v3-ws-scroll">
            <div className="v3-ws-head">
              <span className="v3-app-icon lg"><Icon name="map" size={20} /></span>
              <div className="v3-ws-head-text">
                <h1>Engagement Planner</h1>
                <p>Plans the next months for {brand}: who to engage, what must change, which campaigns, when. Reads Brand IQ only.</p>
              </div>
            </div>

            <ol className="v3-cc-stepper" aria-label="Engagement plan progress">
              {STEPS.map((s, i) => (
                <li key={s} className={i < stepIdx ? "done" : i === stepIdx ? "active" : ""}>
                  <span>{i < stepIdx ? <Icon name="check" size={9} /> : i + 1}</span>{s}
                </li>
              ))}
            </ol>

            {error && <p className="v3-cc-banner error">{error}</p>}
            {busy && <p className="v3-ep-busy"><span className="v3-cc-spinner small" /> {busy}</p>}

            {!plan && (
              <section className="v3-ep-card">
                <b>Frame</b>
                <label className="v3-ep-field"><span>Brand</span><em>{brand} (switch brand in the rail)</em></label>
                <label className="v3-ep-field"><span>Period</span>
                  <select value={months} onChange={(e) => setMonths(Number(e.target.value))}>
                    {((fw?.period as Any | undefined)?.options_months as number[] | undefined ?? [3, 6, 9, 12]).map((m) => <option key={m} value={m}>{m} months{m === 6 ? " (default)" : ""}</option>)}
                  </select>
                </label>
                <label className="v3-ep-field"><span>Industry</span>
                  <select value={industry} onChange={(e) => setIndustry(e.target.value as EngagementIndustry)}>
                    <option value="pharma">Pharma</option>
                    <option value="investment_banking">Investment banking</option>
                  </select>
                </label>
                <button type="button" className="v3-cc-btn primary wide" disabled={!!busy} onClick={start}>Start planning</button>
              </section>
            )}

            {plan && arr(body.sources).length > 0 && (
              <section className="v3-ep-card">
                <b>Read from Brand IQ</b>
                <p className="v3-muted">{arr(body.sources).length} items from {txt(agent.brand_iq_plan) || "the active plan"}.</p>
                <div className="v3-ep-srcs">
                  {Object.entries(arr(body.sources).reduce<Record<string, number>>((m, s) => { m[txt(s.page)] = (m[txt(s.page)] ?? 0) + 1; return m; }, {}))
                    .map(([page, n]) => <span key={page}>{page} · {n}</span>)}
                </div>
                {arr(agent.gaps).map((g) => <p key={txt(g.what)} className="v3-iq-needs">Missing in Brand IQ: {txt(g.what)} ({txt(g.page)})</p>)}
              </section>
            )}

            {plan && agent.step === "clarify" && (
              <section className="v3-ep-card">
                <b>{arr(agent.questions).length ? "A few questions" : "No questions needed"}</b>
                {arr(agent.questions).map((q) => (
                  <div key={txt(q.id)} className="v3-ep-q">
                    <p>{txt(q.question)}</p>
                    {Boolean(q.why) && <small className="v3-muted">{txt(q.why)}</small>}
                    <div className="v3-ep-opts">
                      {arr(q.options).map((o) => (
                        <button key={String(o)} type="button" className={`v3-ep-opt ${answers[txt(q.id)] === String(o) ? "on" : ""}`}
                          onClick={() => setAnswers((a) => ({ ...a, [txt(q.id)]: String(o) }))}>{String(o)}</button>
                      ))}
                    </div>
                    <input className="v3-ep-input" placeholder="Or type your own answer" value={arr(q.options).map(String).includes(answers[txt(q.id)] ?? "") ? "" : (answers[txt(q.id)] ?? "")}
                      onChange={(e) => setAnswers((a) => ({ ...a, [txt(q.id)]: e.target.value }))} />
                  </div>
                ))}
                <label className="v3-cc-toggle"><input type="checkbox" checked={autoAssume} onChange={(e) => setAutoAssume(e.target.checked)} /> Auto-assume — accept the agent's assumptions and draft straight away</label>
                <button type="button" className="v3-cc-btn primary wide" disabled={!!busy} onClick={submitAnswers}>Continue</button>
              </section>
            )}

            {plan && agent.step === "assumptions" && (
              <section className="v3-ep-card">
                <b>{arr(body.assumptions).length ? "Assumptions to check" : "No assumptions needed"}</b>
                {arr(body.assumptions).map((a) => {
                  const d = decisions[txt(a.id)]?.status ?? "accepted";
                  return (
                    <div key={txt(a.id)} className="v3-ep-q">
                      <p>{txt(a.text)}</p>
                      <div className="v3-ep-opts">
                        <button type="button" className={`v3-ep-opt ${d === "accepted" ? "on" : ""}`} onClick={() => setDecisions((m) => ({ ...m, [txt(a.id)]: { status: "accepted" } }))}>Accept</button>
                        <button type="button" className={`v3-ep-opt ${d === "changed" ? "on" : ""}`} onClick={() => setDecisions((m) => ({ ...m, [txt(a.id)]: { status: "changed", note: m[txt(a.id)]?.note } }))}>Change</button>
                        <button type="button" className={`v3-ep-opt ${d === "rejected" ? "on" : ""}`} onClick={() => setDecisions((m) => ({ ...m, [txt(a.id)]: { status: "rejected" } }))}>Reject</button>
                      </div>
                      {d === "changed" && <input className="v3-ep-input" placeholder="What should it assume instead?" value={decisions[txt(a.id)]?.note ?? ""}
                        onChange={(e) => setDecisions((m) => ({ ...m, [txt(a.id)]: { status: "changed", note: e.target.value } }))} />}
                    </div>
                  );
                })}
                <button type="button" className="v3-cc-btn primary wide" disabled={!!busy} onClick={doDraft}>Draft the plan</button>
              </section>
            )}

            {plan && drafted && (
              <section className="v3-ep-card">
                <b>Plan drafted</b>
                <p className="v3-muted">Review it on the right. Each campaign can open the Campaign Planner pre-filled for this brand.</p>
                <button type="button" className="v3-cc-btn wide" disabled={!!busy} onClick={doDraft}>Redraft</button>
              </section>
            )}
          </div>
        </aside>

        <section className="v3-ws-output v3-ep-out">
          {!drafted ? (
            <div className="v3-ws-empty">
              <Icon name="map" size={28} />
              <b>Your engagement plan appears here</b>
              <span>Frame it on the left. The agent reads Brand IQ, asks only what's missing, then drafts objectives, the shift map, campaigns, timeline and relative budget.</span>
            </div>
          ) : (
            <PlanView plan={plan!} fw={fw} tab={tab} setTab={setTab} />
          )}
        </section>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ the plan */

function Src({ s }: { s: unknown }) {
  return s ? <small className="v3-iq-src">Source: {Array.isArray(s) ? s.join(", ") : txt(s)}</small> : null;
}

/** Funnel in the look of the classic brand overview's HcpFunnel, fed only with the plan's real
 *  values: the shape tapers by stage; the text shows today -> target, or "Needs input". */
function Funnel({ audience, stages }: { audience: Any; stages: string[] }) {
  const f = (audience.funnel ?? {}) as Record<string, { today?: unknown; target?: unknown }>;
  const widths = [100, 84, 68, 52, 40];
  return (
    <article className="v3-ep-funnel">
      <b>{txt(audience.name)}</b>
      <div className="hier-funnel-shape">
        {stages.map((st, i) => {
          const v = f[st] ?? {};
          const has = v.today != null || v.target != null;
          const next = widths[i + 1] ?? widths[i] * 0.8;
          const bottom = (next / widths[i]) * 100;
          return (
            <div key={st} className={`hier-funnel-seg hier-funnel-seg-${Math.min(i, 3)}`}
              style={{ width: `${widths[i] ?? 36}%`, clipPath: `polygon(0 0, 100% 0, ${50 + bottom / 2}% 100%, ${50 - bottom / 2}% 100%)` }}>
              <span className="hier-funnel-seg-label">{st}</span>
              <span className="hier-funnel-seg-value">{has ? `${txt(v.today) || "?"} → ${txt(v.target) || "?"}` : "Needs input"}</span>
            </div>
          );
        })}
      </div>
      <small className="v3-muted">{txt(audience.why_now)}</small>
    </article>
  );
}

function PlanView({ plan, fw, tab, setTab }: { plan: EngagementPlan; fw: Any | null; tab: Tab; setTab: (t: Tab) => void }) {
  const b = (plan.body ?? {}) as Any;
  const objectives = arr(b.objectives), audiences = arr(b.audiences), shifts = arr(b.shifts), campaigns = arr(b.campaigns);
  const funnels = (fw?.funnel_stages ?? {}) as Record<string, string[]>;
  const owned = useMemo(() => new Set(campaigns.flatMap((c) => arr(c.shift_refs).map(String))), [campaigns]);
  const orphans = shifts.filter((s) => !owned.has(`${txt(s.audience_id)}:${txt(s.objective_id)}`));
  const audName = (id: unknown) => txt(audiences.find((a) => a.id === id)?.name) || txt(id);
  const objName = (id: unknown) => txt(objectives.find((o) => o.id === id)?.objective) || txt(id);
  const sit = (b.situation ?? {}) as Any;

  return (
    <div className="v3-ep-plan">
      <div className="v3-ws-output-tabs v3-ep-tabs">
        {(["overview", "shifts", "portfolio", "timeline", "budget"] as Tab[]).map((t) => (
          <button key={t} type="button" className={tab === t ? "active" : ""} onClick={() => setTab(t)}>
            {{ overview: "Overview", shifts: "Shift map", portfolio: "Portfolio", timeline: "Timeline", budget: "Budget & KPIs" }[t]}
          </button>
        ))}
      </div>

      {tab === "overview" && (<>
        <div className={`v3-iq-banner ${orphans.length ? "warn" : "ok"}`}>
          {orphans.length ? `${orphans.length} shift(s) have no campaign yet.` : `Every shift is owned by a campaign · ${campaigns.length} campaigns · ${objectives.length} objectives`}
        </div>
        {Boolean(sit.narrative) && <p className="v3-iq-lede-lg">{txt(sit.narrative)}</p>}
        <h3 className="v3-iq-h3">Objectives</h3>
        <div className="v3-iq-objs">
          {objectives.map((o, i) => (
            <article key={txt(o.id)} className={txt(o.priority).toLowerCase()}>
              <div className="v3-iq-obj-top"><span className="v3-iq-obj-n">{i + 1}</span><span className="v3-iq-tier">{txt(o.priority)}</span></div>
              <b>{txt(o.objective)}</b>
              <span>{txt(o.baseline)} → {txt(o.target)}{o.by ? ` · by ${txt(o.by)}` : ""}</span>
              <Src s={o.source} />
            </article>
          ))}
        </div>
        <h3 className="v3-iq-h3">Audience funnels — today → target</h3>
        <div className="v3-ep-funnels">
          {audiences.map((a) => <Funnel key={txt(a.id)} audience={a} stages={funnels[txt(a.funnel_type)] ?? Object.keys((a.funnel ?? {}) as Any)} />)}
        </div>
      </>)}

      {tab === "shifts" && (
        <div className="v3-iq-tablewrap">
          <table className="v3-iq-grid v3-ep-shiftgrid">
            <thead><tr><th />{objectives.map((o) => <th key={txt(o.id)}>{txt(o.objective)}</th>)}</tr></thead>
            <tbody>{audiences.map((a) => (
              <tr key={txt(a.id)}><th>{txt(a.name)}</th>{objectives.map((o) => {
                const s = shifts.find((x) => x.audience_id === a.id && x.objective_id === o.id);
                const orphan = s && !owned.has(`${txt(a.id)}:${txt(o.id)}`);
                return (
                  <td key={txt(o.id)} className={s ? (orphan ? "orphan" : "") : "empty"}>
                    {s ? (<div className="v3-ep-shift">
                      <p><em>From</em>{txt(s.from)}</p>
                      <p><em>To</em><b>{txt(s.to)}</b></p>
                      <p><em>Barrier</em>{txt(s.barrier)}</p>
                      <p><em>Message</em>{txt(s.message)}</p>
                      {Boolean(s.moment) && <p><em>Moment</em>{txt(s.moment)}</p>}
                      {orphan && <span className="v3-iq-threat high">No campaign</span>}
                      <Src s={s.source} />
                    </div>) : <span className="v3-muted">—</span>}
                  </td>
                );
              })}</tr>
            ))}</tbody>
          </table>
        </div>
      )}

      {tab === "portfolio" && (
        <div className="v3-ep-camps">
          {campaigns.map((c) => (
            <article key={txt(c.id)}>
              <div className="v3-iq-comp2-top"><b>{txt(c.name)}</b><span className="v3-iq-tier">{txt(c.weight).replace(/%$/, "")}% budget</span></div>
              <span className="v3-iq-comp2-meta">{txt(c.type)} · {txt(c.start)} → {txt(c.end)} · {arr(c.audience_ids).map(audName).join(", ")}</span>
              <p><em>Message</em>{txt(c.message)}</p>
              <p><em>Shifts</em>{arr(c.shift_refs).map((r) => { const [a, o] = String(r).split(":"); return `${audName(a)} → ${objName(o)}`; }).join("; ")}</p>
              <p><em>Channels</em>{arr(c.channels).map(String).join(" · ")}</p>
              <p><em>KPI</em>{txt(c.kpi)}</p>
              <a className="v3-cc-btn" href={`#/v3/agent/campaign-planner/for/${encodeURIComponent(plan.brand)}/0/0`}>Create campaign plan</a>
              <Src s={c.source} />
            </article>
          ))}
        </div>
      )}

      {tab === "timeline" && <Timeline plan={plan} campaigns={campaigns} moments={arr(b.fixed_moments)} />}

      {tab === "budget" && (<>
        {(["by_objective", "by_audience", "by_channel"] as const).map((k) => {
          const m = ((b.budget ?? {}) as Any)[k] as Record<string, number> | undefined;
          const entries = Object.entries(m ?? {});
          const max = Math.max(1, ...entries.map(([, v]) => Number(v)));
          const label = (id: string) => (k === "by_objective" ? objName(id) : k === "by_audience" ? audName(id) : id);
          return (
            <section key={k} className="v3-ep-budget">
              <h3 className="v3-iq-h3">Relative budget {k.replace("by_", "by ")}</h3>
              {entries.length ? entries.map(([id, v]) => (
                <div key={id} className="hier-budget-bar-row">
                  <span className="hier-budget-bar-label">{label(id)}</span>
                  <div className="hier-budget-bar-track"><div className="hier-budget-bar-fill" style={{ width: `${Math.max((Number(v) / max) * 100, 6)}%` }} /></div>
                  <span className="hier-budget-bar-value">{txt(v).replace(/%$/, "")}%</span>
                </div>
              )) : <p className="v3-iq-needs">Needs input</p>}
            </section>
          );
        })}
        <h3 className="v3-iq-h3">KPI tree</h3>
        <div className="v3-iq-tablewrap"><table className="v3-iq-table"><thead><tr><th>Objective</th><th>KPI</th><th>Leading indicators</th></tr></thead>
          <tbody>{arr(((b.measurement ?? {}) as Any).kpi_tree).map((k, i) => (
            <tr key={i}><td>{objName(k.objective_id)}</td><td>{txt(k.kpi)}</td><td>{arr(k.leading_indicators).map(String).join("; ")}</td></tr>
          ))}</tbody></table></div>
        <h3 className="v3-iq-h3">Risks</h3>
        <div className="v3-iq-tablewrap"><table className="v3-iq-table"><thead><tr><th>Risk</th><th>Likelihood</th><th>Impact</th><th>Mitigation</th></tr></thead>
          <tbody>{arr(b.risks).map((r, i) => (<tr key={i}><td>{txt(r.risk)}</td><td>{txt(r.likelihood)}</td><td>{txt(r.impact)}</td><td>{txt(r.mitigation)}</td></tr>))}</tbody></table></div>
      </>)}
    </div>
  );
}

/** A simple month Gantt over the plan period: campaigns as bars, fixed moments as markers. */
function Timeline({ plan, campaigns, moments }: { plan: EngagementPlan; campaigns: Any[]; moments: Any[] }) {
  const start = new Date(`${plan.period_start}T00:00:00`);
  const monthsList = Array.from({ length: plan.months }, (_, i) => new Date(start.getFullYear(), start.getMonth() + i, 1));
  const idx = (ym: unknown) => {
    const [y, m] = txt(ym).slice(0, 7).split("-").map(Number);
    if (!y || !m) return -1;
    return (y - start.getFullYear()) * 12 + (m - 1 - start.getMonth());
  };
  const clamp = (n: number) => Math.min(Math.max(n, 0), plan.months - 1);
  return (
    <div className="v3-ep-gantt" style={{ ["--cols" as string]: plan.months }}>
      <div className="v3-ep-gantt-row head"><span />{monthsList.map((d) => <span key={d.toISOString()}>{d.toLocaleString(undefined, { month: "short", year: "2-digit" })}</span>)}</div>
      {moments.length > 0 && (
        <div className="v3-ep-gantt-row moments"><span>Fixed moments</span>
          <div className="v3-ep-gantt-track">{moments.map((m, i) => {
            const c = idx(m.date);
            return c < 0 || c >= plan.months ? null : <i key={i} style={{ left: `calc(${(c + 0.5) / plan.months * 100}% - 5px)` }} title={`${txt(m.label)} (${txt(m.date)})`} />;
          })}</div>
        </div>
      )}
      {campaigns.map((c) => {
        const s = clamp(idx(c.start)), e = clamp(idx(c.end));
        return (
          <div key={txt(c.id)} className="v3-ep-gantt-row"><span>{txt(c.name)}</span>
            <div className="v3-ep-gantt-track"><b style={{ left: `${s / plan.months * 100}%`, width: `${(e - s + 1) / plan.months * 100}%` }}>{txt(c.type)}</b></div>
          </div>
        );
      })}
      {moments.length > 0 && <ul className="v3-ep-moments">{moments.map((m, i) => <li key={i}><b>{txt(m.date)}</b> {txt(m.label)} <small className="v3-muted">{txt(m.type)}</small></li>)}</ul>}
    </div>
  );
}
