import { useCallback, useEffect, useMemo, useState } from "react";
import { getLiveSim, resolveLiveSim, runLiveSimCheck, seedLiveSimDemo } from "../../api";
import { Icon } from "../../components/Icon";
import type { BrandSummary } from "../../types";
import "./livesim.css";

/** Live simulation: the watched view of a brand's engagement plans -> campaigns -> journeys, as an
 *  outline with a timeline, plus what the nightly 12 am check found (updates waiting, change log).
 *  Backend: strategy/live_sim.py. The check changes only derived things (phases from dates) by itself;
 *  everything else waits here for Apply or Dismiss. */

interface Flow { id: number; name: string; status: string; origin: string }
interface Campaign { id: number; name: string; status: string; phase: string; start_date: string | null; end_date: string | null; flows: Flow[]; content?: { changed_steps: string[] } }
interface Plan { id: number; name: string; period_start: string | null; period_end: string | null; status: string; campaigns: Campaign[] }
interface Update {
  id: string; kind: string; status: string; title: string; detail?: string; proposal?: string; proposal_note?: string;
  evidence?: string; action?: string; href?: string; campaign_id?: number; raised_at?: string;
}
interface View {
  brand: string; tree: { engagement_plans: Plan[] }; updates: Update[]; log: { at: string; what: string; why: string }[];
  last_check: string | null; next_check: string; demo: boolean; demo_plan_ids: number[];
  journey_meta: Record<string, { sends?: number; hcps?: number; channels?: string[] }>;
}

const DAY = 86400000;
const fmt = (d: string | null) => (d ? new Date(d).toLocaleDateString(undefined, { month: "short", year: "2-digit" }) : "—");
const when = (d: string | null) => (d ? new Date(d).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "never");
const PHASE_LABEL: Record<string, string> = { running: "Running", planned: "Planned", ended: "Ended", unscheduled: "Unscheduled", closed: "Closed" };
const KIND_LABEL: Record<string, string> = { drift: "Brand content changed", no_journey: "Missing journey", brand_iq: "Brand Compass", plan_stale: "Plan out of date", signals: "Signal Scout", demo: "Demo" };

export function LiveSimulation({ brands, activeBrand }: { brands: BrandSummary[]; activeBrand: string | null }) {
  const [brand, setBrand] = useState<string | null>(activeBrand);
  useEffect(() => {
    setBrand(activeBrand ?? (brands.some((b) => b.brand === "Jardiance") ? "Jardiance" : brands[0]?.brand ?? null));
  }, [activeBrand, brands]);
  const [view, setView] = useState<View | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const [open, setOpen] = useState<Record<number, boolean>>({});
  const [busyId, setBusyId] = useState<string | null>(null);
  const [showDone, setShowDone] = useState(false);

  const load = useCallback(() => {
    if (!brand) return;
    setError(null);
    getLiveSim<View>(brand).then(setView).catch((e) => setError(String(e)));
  }, [brand]);
  useEffect(() => { setView(null); load(); }, [load]);

  const runCheck = async () => {
    if (!brand) return;
    setChecking(true);
    try { await runLiveSimCheck(brand); load(); }
    catch (e) { setError(String(e)); }
    finally { setChecking(false); }
  };
  const loadDemo = async () => {
    if (!brand) return;
    try { await seedLiveSimDemo(brand); await runLiveSimCheck(brand); load(); }
    catch (e) { setError(String(e)); }
  };
  const resolve = async (u: Update, action: "apply" | "dismiss") => {
    if (!brand) return;
    setBusyId(u.id);
    try { await resolveLiveSim(brand, u.id, action); load(); }
    catch (e) { setError(String(e)); }
    finally { setBusyId(null); }
  };

  const byStart = (a: string | null, b: string | null) => (a ?? "9999").localeCompare(b ?? "9999");
  const plans = useMemo(() => (view?.tree.engagement_plans ?? [])
    .map((p) => ({ ...p, campaigns: [...p.campaigns].sort((a, b) => byStart(a.start_date, b.start_date)) }))
    .sort((a, b) => byStart(a.period_start, b.period_start)), [view]);
  // Timeline range: every plan's and campaign's dates, padded a month either side.
  const range = useMemo(() => {
    const ds = plans.flatMap((p) => [p.period_start, p.period_end, ...p.campaigns.flatMap((c) => [c.start_date, c.end_date])])
      .filter(Boolean).map((d) => new Date(d as string).getTime());
    if (!ds.length) return null;
    return { from: Math.min(...ds) - 15 * DAY, to: Math.max(...ds) + 15 * DAY };
  }, [plans]);
  const pos = (s: string | null, e: string | null) => {
    if (!range || (!s && !e)) return null;
    const a = new Date(s ?? e!).getTime(), b = new Date(e ?? s!).getTime();
    const w = range.to - range.from;
    return { left: `${((a - range.from) / w) * 100}%`, width: `${Math.max(1.5, ((b - a) / w) * 100)}%` };
  };
  const todayLeft = range ? `${((Date.now() - range.from) / (range.to - range.from)) * 100}%` : null;
  const months = useMemo(() => {
    if (!range) return [];
    const out: { label: string; left: string }[] = [];
    const d = new Date(range.from); d.setDate(1); d.setMonth(d.getMonth() + 1);
    const step = Math.max(1, Math.ceil((range.to - range.from) / (30 * DAY) / 10));
    while (d.getTime() < range.to) {
      out.push({ label: d.toLocaleDateString(undefined, { month: "short" }) + (d.getMonth() < step ? ` ’${String(d.getFullYear()).slice(2)}` : ""),
        left: `${((d.getTime() - range.from) / (range.to - range.from)) * 100}%` });
      d.setMonth(d.getMonth() + step);
    }
    return out;
  }, [range]);

  const waiting = (view?.updates ?? []).filter((u) => u.status === "waiting");
  const done = (view?.updates ?? []).filter((u) => u.status !== "waiting");
  const updatesFor = (cid: number) => waiting.filter((u) => u.campaign_id === cid);
  const campaigns = plans.flatMap((p) => p.campaigns);
  const journeys = campaigns.flatMap((c) => c.flows);
  const demoPlans = new Set(view?.demo_plan_ids ?? []);

  if (!brand) return <p className="v3-empty">Add a brand first.</p>;

  return (
    <div className="v3-ls">
      <div className="v3-ls-head">
        <div>
          <h1 className="v3-page-title">Live simulation {view?.demo && <span className="v3-ls-demo">Demo data</span>}</h1>
          <p className="v3-page-sub">
            <b>{brand}</b> · engagement plans → campaigns → journeys, checked every night at 12:00 am.
            {!activeBrand && brands.length > 1 && (
              <select className="v3-ls-brand" value={brand} onChange={(e) => setBrand(e.target.value)}>
                {brands.map((b) => <option key={b.brand}>{b.brand}</option>)}
              </select>
            )}
          </p>
        </div>
        <div className="v3-ls-strip">
          <div><em>Last check</em><b>{when(view?.last_check ?? null)}</b></div>
          <div><em>Next check</em><b>{when(view?.next_check ?? null)}</b></div>
          <div><em>Plans</em><b>{plans.length}</b></div>
          <div><em>Running</em><b>{campaigns.filter((c) => c.phase === "running").length}</b></div>
          <div><em>Journeys</em><b>{journeys.length}</b></div>
          <div><em>Waiting</em><b className={waiting.length ? "warn" : ""}>{waiting.length}</b></div>
          <button type="button" className="v3-cc-btn primary" disabled={checking} onClick={runCheck}>
            {checking ? <><span className="v3-cc-spinner small" /> Checking…</> : <><Icon name="refresh" size={13} /> Run check now</>}
          </button>
        </div>
      </div>
      {error && <p className="v3-cc-banner error">{error}</p>}

      <div className="v3-ls-body">
        <section className="v3-ls-tree">
          {view && !plans.length ? (
            <div className="v3-ws-empty">
              <Icon name="layers" size={28} />
              <b>No engagement plans for {brand} yet</b>
              <span>Save a plan from the Engagement Planner, or load the demo tree.</span>
              {brand === "Jardiance" && <button type="button" className="v3-cc-btn primary" onClick={loadDemo}>Load the Jardiance demo</button>}
            </div>
          ) : !view ? <p className="v3-muted">Loading…</p> : (
            <>
              <div className="v3-ls-row v3-ls-axis">
                <div className="v3-ls-name" />
                <div className="v3-ls-track">
                  {months.map((m) => <span key={m.left} style={{ left: m.left }}>{m.label}</span>)}
                </div>
              </div>
              {plans.map((p) => {
                const isOpen = open[p.id] ?? true;
                return (
                  <div key={p.id} className="v3-ls-plan">
                    <div className="v3-ls-row plan" onClick={() => setOpen((o) => ({ ...o, [p.id]: !isOpen }))}>
                      <div className="v3-ls-name">
                        <span className={`v3-ls-caret ${isOpen ? "open" : ""}`}><Icon name="chevronDown" size={12} /></span>
                        <b title={p.name}>{p.name}</b>
                        {demoPlans.has(p.id) && <span className="v3-ls-demo sm">Demo</span>}
                        <small>{fmt(p.period_start)} – {fmt(p.period_end)} · {p.campaigns.length} campaign{p.campaigns.length === 1 ? "" : "s"}</small>
                      </div>
                      <div className="v3-ls-track">
                        {todayLeft && <i className="v3-ls-today" style={{ left: todayLeft }} />}
                        {pos(p.period_start, p.period_end) && <span className="v3-ls-bar plan" style={pos(p.period_start, p.period_end)!} />}
                      </div>
                    </div>
                    {isOpen && p.campaigns.map((c) => {
                      const ups = updatesFor(c.id);
                      return (
                        <div key={c.id}>
                          <a className="v3-ls-row campaign" href={`#/v3/agent/briefing-agent/for/${encodeURIComponent(brand)}/${p.id}/${c.id}`} title="Open in the Campaign Planning Agent">
                            <div className="v3-ls-name">
                              <span className="v3-ls-indent" />
                              <Icon name="target" size={13} />
                              <span className="v3-ls-cname" title={c.name}>{c.name}</span>
                              <span className={`v3-ls-phase ${c.phase}`}>{PHASE_LABEL[c.phase] ?? c.phase}</span>
                              {ups.length > 0 && <span className="v3-ls-flag" title={ups.map((u) => u.title).join("\n")}><Icon name="alertTriangle" size={11} /> {ups.length}</span>}
                            </div>
                            <div className="v3-ls-track">
                              {todayLeft && <i className="v3-ls-today" style={{ left: todayLeft }} />}
                              {pos(c.start_date, c.end_date) ? <span className={`v3-ls-bar ${c.phase}`} style={pos(c.start_date, c.end_date)!} /> : <span className="v3-ls-nodate">No dates</span>}
                            </div>
                          </a>
                          {c.flows.map((f) => {
                            const m = view.journey_meta[String(f.id)];
                            return (
                              <a key={f.id} className="v3-ls-row journey" href={`#/v3/agent/flow-planner/for/${encodeURIComponent(brand)}/${p.id}/${c.id}`} title="Open in the Flow Planner Agent">
                                <div className="v3-ls-name">
                                  <span className="v3-ls-indent" /><span className="v3-ls-indent" />
                                  <Icon name="route" size={12} />
                                  <span className="v3-ls-jname" title={f.name}>{f.name}</span>
                                  <span className={`v3-ls-jstatus ${f.status}`}>{f.status === "confirmed" ? "Approved" : f.status === "built" ? "Built" : "Draft"}</span>
                                </div>
                                <div className="v3-ls-track meta">
                                  {m ? <span>{m.sends} sends · {m.hcps?.toLocaleString()} HCPs · {(m.channels ?? []).join(", ")}</span> : <span className="v3-muted">Journey</span>}
                                </div>
                              </a>
                            );
                          })}
                          {!c.flows.length && c.phase !== "ended" && (
                            <a className="v3-ls-row journey missing" href={`#/v3/agent/flow-planner/for/${encodeURIComponent(brand)}/${p.id}/${c.id}`}>
                              <div className="v3-ls-name"><span className="v3-ls-indent" /><span className="v3-ls-indent" /><Icon name="plus" size={12} /><span>Build the journey</span></div>
                              <div className="v3-ls-track" />
                            </a>
                          )}
                        </div>
                      );
                    })}
                  </div>
                );
              })}
            </>
          )}
        </section>

        <aside className="v3-ls-side">
          <section className="v3-ls-card">
            <h3><Icon name="alertTriangle" size={14} /> Updates waiting <span>{waiting.length}</span></h3>
            {!waiting.length && <p className="v3-muted">Nothing waiting. The next check runs at {when(view?.next_check ?? null)}.</p>}
            {waiting.map((u) => (
              <div key={u.id} className={`v3-ls-update ${u.kind}`}>
                <span className="v3-ls-kind">{KIND_LABEL[u.kind] ?? u.kind}</span>
                <b>{u.title}</b>
                {u.detail && <p>{u.detail}</p>}
                {u.proposal && <p className="v3-ls-prop"><em>Proposed</em>{u.proposal}{u.evidence && <small> · {u.evidence}</small>}</p>}
                {u.proposal_note && <p className="v3-muted">{u.proposal_note}</p>}
                <div className="v3-ls-actions">
                  {u.action === "refresh" && <button type="button" className="v3-cc-btn primary" disabled={busyId === u.id} onClick={() => resolve(u, "apply")}>Apply · refresh the campaign</button>}
                  {u.action === "open" && u.href && <a className="v3-cc-btn primary" href={u.href} onClick={() => resolve(u, "apply")}>Open</a>}
                  {u.action === "acknowledge" && <button type="button" className="v3-cc-btn primary" disabled={busyId === u.id} onClick={() => resolve(u, "apply")}>Done</button>}
                  <button type="button" className="v3-cc-btn" disabled={busyId === u.id} onClick={() => resolve(u, "dismiss")}>Dismiss</button>
                </div>
              </div>
            ))}
            {done.length > 0 && (
              <button type="button" className="v3-link" onClick={() => setShowDone((v) => !v)}>{showDone ? "Hide" : "Show"} {done.length} handled</button>
            )}
            {showDone && done.map((u) => (
              <div key={u.id} className="v3-ls-update handled"><span className="v3-ls-kind">{u.status}</span><b>{u.title}</b></div>
            ))}
          </section>
          <section className="v3-ls-card">
            <h3><Icon name="refresh" size={14} /> Change log</h3>
            {!(view?.log ?? []).length && <p className="v3-muted">Nothing changed by itself yet.</p>}
            {(view?.log ?? []).slice(0, 30).map((l, i) => (
              <div key={i} className="v3-ls-log"><small>{when(l.at)}</small><span>{l.what}</span><em>{l.why}</em></div>
            ))}
          </section>
          <p className="v3-ls-note">The check changes only what follows from dates (a campaign's phase) by itself. Content, audiences and journeys change only when you apply an update. {view?.demo ? "Demo plans, journey numbers and the demo updates are illustrative." : ""}</p>
        </aside>
      </div>
    </div>
  );
}

