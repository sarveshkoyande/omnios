import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createEngagementPlan, engagementCheck, engagementChoose, engagementClassify, engagementDiagnose,
  engagementDraft, engagementOptions, getEngagementFramework, getEngagementPlan,
  listEngagementPlans, ackEngagement, publishEngagementPlan, uploadAgentIntake, type EngagementPlan,
} from "../../api";
import { AckCard, ReadyIntake, ReasoningButton, ReasoningPanel, type Ack, type ReasonEntry } from "../agentkit/AgentKit";
import { Icon } from "../../components/Icon";
import type { BrandSummary } from "../../types";
import "../campaignplanner/campaignPlanner.css";
import "../iq.css";
import "./engagement.css";

/** The Engagement Planner v2 (docs/redesign/engagement-plan-v2.md): the next N months for one
 *  pharma brand. Left: the agent conversation -- read Brand IQ, classify the brand's situation,
 *  diagnose where patients are lost, root causes and strategic options, you choose, it drafts,
 *  then feasibility + red team. Right: the diagnosis and the plan. Brand IQ is the only input. */

type Any = Record<string, unknown>;
const txt = (v: unknown) => (v === null || v === undefined ? "" : String(v));
const arr = (v: unknown) => (Array.isArray(v) ? (v as Any[]) : []);
const STEPS = ["Understand the brand", "Diagnose", "Choose the strategy", "Draft & check"];
const STEP_INDEX: Record<string, number> = { read: 0, classify: 1, diagnose: 1, options: 2, decide: 2, draft: 3, check: 4 };
type Tab = "diagnosis" | "overview" | "shifts" | "portfolio" | "timeline" | "budget" | "checks";

function errText(e: unknown): string {
  const s = String(e);
  const i = s.indexOf("{");  // our API's own JSON error envelope: {"detail": "..."}
  if (i >= 0) {
    try { const d = JSON.parse(s.slice(i)).detail; if (typeof d === "string") return d; } catch { /* not JSON */ }
  }
  return s;
}

/** Engagement Planner, four agent steps: 1 understand (intake -> acknowledgement -> your OK), 2 diagnose
 *  (situation + leaky bucket, with your corrections and answers), 3 choose the strategy, 4 draft & check.
 *  The plan is the main canvas; Live reasoning is a slide-in panel. */
export function EngagementPlanner({ brands, activeBrand, planId }: { brands: BrandSummary[]; activeBrand: string | null; planId?: string }) {
  const brand = activeBrand ?? brands[0]?.brand ?? null;
  const [plans, setPlans] = useState<EngagementPlan[]>([]);
  const [plan, setPlan] = useState<EngagementPlan | null>(null);
  const [fw, setFw] = useState<Any | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [months, setMonths] = useState(6);
  const [files, setFiles] = useState<File[]>([]);
  const [notes, setNotes] = useState("");
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [override, setOverride] = useState<Record<string, string>>({});
  const [picked, setPicked] = useState<string[]>([]);
  const [note, setNote] = useState("");
  const [tab, setTab] = useState<Tab>("diagnosis");
  const [showReasoning, setShowReasoning] = useState(false);

  const refreshList = useCallback(() => {
    if (!brand) return;
    listEngagementPlans(brand).then((r) => setPlans(r.plans)).catch(() => setPlans([]));
  }, [brand]);
  useEffect(refreshList, [refreshList]);
  useEffect(() => { getEngagementFramework().then(setFw).catch(() => setFw(null)); }, []);

  useEffect(() => {
    if (!planId) { setPlan(null); return; }
    setPlan((cur) => {
      if (cur?.id !== planId) getEngagementPlan(planId).then(setPlan).catch((e) => setError(errText(e)));
      return cur?.id === planId ? cur : null;
    });
  }, [planId]);

  const body = (plan?.body ?? {}) as Any;
  const agent = (body.agent ?? {}) as Any;
  const ack = (agent.ack ?? null) as Ack | null;
  const step = txt(agent.step);
  const cls = (body.classification ?? null) as Any | null;
  const bucket = (body.bucket ?? null) as Any | null;
  const options = arr(body.options);
  const rec = (body.recommendation ?? null) as Any | null;
  const drafted = step === "draft" || step === "check";
  const stepIdx = plan ? (STEP_INDEX[step] ?? 0) : 0;
  const allDone = step === "check";

  useEffect(() => { if (rec?.id && !picked.length) setPicked([txt(rec.id)]); }, [rec?.id]);  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (drafted) setTab("overview"); }, [drafted]);

  const run = async (label: string, fn: () => Promise<EngagementPlan>) => {
    setBusy(label); setError(null);
    try { const p = await fn(); setPlan(p); refreshList(); return p; }
    catch (e) { setError(errText(e)); return null; }
    finally { setBusy(null); }
  };

  /** Step 1: create the plan, store the documents + notes, and let the agent acknowledge what it has. */
  const start = async () => {
    if (!brand) return;
    const p = await run("Creating the plan…", () => createEngagementPlan({ brand, months }));
    if (!p) return;
    window.location.hash = `#/v3/agent/engagement-planner/${p.id}`;
    setBusy("Reading your documents and Brand IQ…");
    try { await uploadAgentIntake("engagement-planner", p.id, files, notes); }
    catch (e) { setError(errText(e)); setBusy(null); return; }
    await run("Reading your documents and Brand IQ…", () => ackEngagement(p.id));
  };

  /** Step 2, after your OK. */
  const confirm = async () => {
    if (!plan) return;
    if (!(await run("Classifying the brand's situation…", () => engagementClassify(plan.id)))) return;
    await run("Diagnosing where patients are lost…", () => engagementDiagnose(plan.id));
  };

  const reclassify = async () => {
    if (!plan) return;
    if (!(await run("Updating the situation…", () => engagementClassify(plan.id, override)))) return;
    await run("Re-diagnosing…", () => engagementDiagnose(plan.id));
    setOverride({});
  };

  const seeOptions = () => plan && run("Finding root causes and options…", () => engagementOptions(plan.id, answers));

  const decideAndDraft = async () => {
    if (!plan || !picked.length) return;
    if (!(await run("Recording your choice…", () => engagementChoose(plan.id, picked, note || undefined)))) return;
    if (!(await run("Drafting the plan…", () => engagementDraft(plan.id)))) return;
    await run("Checking feasibility and red-teaming…", () => engagementCheck(plan.id));
  };

  const published = (body.published ?? null) as Any | null;
  const save = () => plan && run("Saving the plan and its campaigns…", () => publishEngagementPlan(plan.id));

  if (!brand) return <p className="v3-empty">Add a brand first: an engagement plan belongs to one brand.</p>;
  const lifecycle = arr(fw?.lifecycle), archetypes = arr(fw?.archetypes), access = arr(fw?.access);
  const checks = (body.checks ?? null) as Any | null;

  // What each finished step concluded, for the progress rows and the reasoning panel.
  const summaries: string[] = [
    ack?.understood ?? "",
    bucket ? `${txt(bucket.indication)} · ${arr(bucket.leaks).length} leak(s)` : "",
    arr((body.chosen_option as Any | undefined)?.ids).length ? `Chose ${arr((body.chosen_option as Any).ids).map(String).join(" + ")}` : "",
    checks ? `${arr(checks.feasibility).length} feasibility issue(s), ${arr(checks.red_team).length} red-team point(s)` : "",
  ];
  const entries: ReasonEntry[] = [];
  if (ack) entries.push({ id: "ack", title: "Understanding the brand", status: "done", lines: [ack.understood ?? "", ...(ack.approach ?? [])].filter(Boolean) });
  if (cls) entries.push({ id: "cls", title: "Classifying the situation", status: "done",
    lines: [`${txt((cls.labels as Any | undefined)?.lifecycle)} · ${txt((cls.labels as Any | undefined)?.archetype)} · ${txt((cls.labels as Any | undefined)?.access)}`,
      ...arr(cls.evidence).map((e) => `${txt(e.point)} (${txt(e.source)})`)] });
  if (bucket) entries.push({ id: "dx", title: "Diagnosing the leaky bucket", status: "done",
    lines: [txt(bucket.why_this_indication), ...arr(bucket.leaks).map((l) => `${txt(l.id)} · ${txt(l.stage)}: ${txt(l.finding)}`)].filter(Boolean) });
  if (options.length) entries.push({ id: "opt", title: "Root causes and options", status: "done",
    lines: [...arr(body.root_causes).map((r) => `${txt(r.leak)} — ${txt(r.audience)}: ${txt(r.belief)}`), rec?.why ? `Recommend ${txt(rec.id)}: ${txt(rec.why)}` : ""].filter(Boolean) });
  if (drafted) entries.push({ id: "draft", title: "Drafting the plan", status: "done", lines: [txt((body.situation as Any | undefined)?.narrative)].filter(Boolean) });
  if (checks) entries.push({ id: "check", title: "Feasibility and red team", status: "done",
    lines: arr(checks.red_team).map((r) => `[${txt(r.severity)}] ${txt(r.issue)} → ${txt(r.fix)}`) });
  if (busy) entries.push({ id: "busy", title: busy, status: "running", lines: [] });

  const row = (i: number) => (
    <div key={i} className="v3-ak-row done">
      <span className="v3-ak-dot"><Icon name="check" size={9} /></span>
      <b>{STEPS[i]}</b>
      {summaries[i] && <small className="v3-ep-row-sum">{summaries[i]}</small>}
    </div>
  );

  return (
    <div className="v3-ws v3-cc v3-ep">
      <div className="v3-ws-top">
        <span className="v3-ep-title">{plan ? plan.title : `New engagement plan — ${brand}`}</span>
        {plan && <span className="v3-ws-save">v{plan.version} · {plan.period_start} → {plan.period_end}{plan.stale ? " · based on an older brand plan — review" : ""}</span>}
        <span className="v3-ws-top-actions">
          {plans.length > 0 && (
            <select className="v3-ep-select" value={plan?.id ?? ""} onChange={(e) => { window.location.hash = e.target.value ? `#/v3/agent/engagement-planner/${e.target.value}` : "#/v3/agent/engagement-planner"; }}>
              <option value="">+ New plan</option>
              {plans.map((p) => <option key={p.id} value={p.id}>{p.title} (v{p.version})</option>)}
            </select>
          )}
          {drafted && (
            <button type="button" className="v3-cc-btn primary" disabled={!!busy} onClick={save}
              title="Save the plan and its campaigns to Campaigns & Journeys">
              {published ? "Save again" : "Save plan"}
            </button>
          )}
          <ReasoningButton live={Boolean(busy)} onClick={() => setShowReasoning((v) => !v)} />
        </span>
      </div>

      <div className="v3-ws-body">
        <aside className="v3-ws-inputs">
          <div className="v3-ws-scroll">
            <div className="v3-ws-head">
              <span className="v3-app-icon lg"><Icon name="map" size={20} /></span>
              <div className="v3-ws-head-text">
                <h1>Engagement Planner (Old)</h1>
                <p>Finds where {brand} loses patients, why, and what would move the people behind it — then plans the next months around it.</p>
              </div>
            </div>

            <ol className="v3-cc-stepper" aria-label="Engagement plan progress">
              {STEPS.map((s, i) => (
                <li key={s} className={i < stepIdx || allDone ? "done" : i === stepIdx ? "active" : ""}>
                  <span>{i < stepIdx || allDone ? <Icon name="check" size={9} /> : i + 1}</span>{s}
                </li>
              ))}
            </ol>

            {!plan && (
              <ReadyIntake brand={brand} startLabel="Start planning" busy={!!busy} busyLabel={busy} onStart={start}
                files={files} setFiles={setFiles} notes={notes} setNotes={setNotes}
                addLabel="Add objectives or other details" notesLabel="What should this plan achieve?"
                placeholder="What should this plan achieve? Leave empty to plan from Brand IQ.">
                <label className="v3-ep-field"><span>Period</span>
                  <select value={months} disabled={!!busy} onChange={(e) => setMonths(Number(e.target.value))}>
                    {((fw?.period as Any | undefined)?.options_months as number[] | undefined ?? [3, 6, 9, 12]).map((m) => <option key={m} value={m}>{m} months{m === 6 ? " (default)" : ""}</option>)}
                  </select>
                </label>
              </ReadyIntake>
            )}

            {plan && (
              <div className="v3-ak-progress">
                {Array.from({ length: Math.min(stepIdx, STEPS.length) }, (_, i) => row(i))}

                {stepIdx === 0 && (
                  ack ? <AckCard ack={ack} onConfirm={confirm} onEdit={() => { window.location.hash = "#/v3/agent/engagement-planner"; }} />
                    : !busy && <button type="button" className="v3-cc-btn primary wide" onClick={() => run("Reading your documents and Brand IQ…", () => ackEngagement(plan.id))}>Read Brand IQ</button>
                )}

                {stepIdx === 1 && (
                  <div className="v3-ak-row current">
                    <div className="v3-ak-row-head"><span className="v3-ak-dot">{busy ? <span className="v3-cc-spinner small" /> : 2}</span><b>{STEPS[1]}</b></div>
                    {cls && (
                      <div className="v3-ep-sub">
                        <em>Brand situation {txt(cls.status) === "confirmed" ? "· confirmed" : txt(cls.status) === "from brand plan" ? "· from the brand plan" : "· proposed"}</em>
                        {([["lifecycle", "Lifecycle", lifecycle], ["archetype", "Therapy type", archetypes], ["access", "Access", access]] as [string, string, Any[]][]).map(([k, label, opts]) => (
                          <label key={k} className="v3-ep-field"><span>{label}</span>
                            <select value={override[k] ?? txt(cls[k])} onChange={(e) => setOverride((o) => ({ ...o, [k]: e.target.value }))} disabled={!!busy}>
                              {!cls[k] && <option value="">Needs input</option>}
                              {opts.map((o) => <option key={txt(o.id)} value={txt(o.id)}>{txt(o.label)}</option>)}
                            </select>
                          </label>
                        ))}
                        {Object.keys(override).length > 0 && <button type="button" className="v3-cc-btn wide" disabled={!!busy} onClick={reclassify}>Confirm and re-diagnose</button>}
                      </div>
                    )}
                    {bucket && step === "diagnose" && (
                      <div className="v3-ep-sub">
                        <em>{arr(bucket.questions).length ? "Questions from the diagnosis" : "The diagnosis is complete"}</em>
                        {arr(bucket.questions).map((q) => (
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
                        <button type="button" className="v3-cc-btn primary wide" disabled={!!busy} onClick={seeOptions}>See strategic options</button>
                      </div>
                    )}
                    {busy && <small className="v3-ep-busy-line">{busy}</small>}
                  </div>
                )}

                {stepIdx === 2 && (
                  <div className="v3-ak-row current">
                    <div className="v3-ak-row-head"><span className="v3-ak-dot">{busy ? <span className="v3-cc-spinner small" /> : 3}</span><b>{STEPS[2]}</b></div>
                    {options.length > 0 && (
                      <div className="v3-ep-sub">
                        <em>Pick one, or several to combine</em>
                        {options.map((o) => {
                          const on = picked.includes(txt(o.id));
                          return (
                            <button key={txt(o.id)} type="button" className={`v3-ep-option ${on ? "on" : ""}`} disabled={!!busy}
                              onClick={() => setPicked((p) => (on ? p.filter((x) => x !== txt(o.id)) : [...p, txt(o.id)]))}>
                              <span className="v3-ep-option-top"><b>{txt(o.id)} · {txt(o.name)}</b>{rec?.id === o.id && <em>Recommended</em>}</span>
                              <span>{txt(o.thesis)}</span>
                              <span className="v3-ep-option-meta">Cost {txt(o.relative_cost)} · Risk {txt(o.risk)} · {txt(o.time_to_effect)}</span>
                              <span className="v3-ep-option-give"><b>You give up:</b> {txt(o.trade_off)}</span>
                            </button>
                          );
                        })}
                        {Boolean(rec?.why) && <p className="v3-ep-rec"><b>Why {txt(rec?.id)}:</b> {txt(rec?.why)}</p>}
                        <input className="v3-ep-input" placeholder="Anything to add for the draft (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
                        <button type="button" className="v3-cc-btn primary wide" disabled={!!busy || !picked.length} onClick={decideAndDraft}>Draft the plan</button>
                      </div>
                    )}
                    {busy && <small className="v3-ep-busy-line">{busy}</small>}
                  </div>
                )}

                {stepIdx === 3 && (
                  <div className="v3-ak-row current">
                    <div className="v3-ak-row-head"><span className="v3-ak-dot"><span className="v3-cc-spinner small" /></span><b>{STEPS[3]}</b></div>
                    <small className="v3-ep-busy-line">{busy ?? "Waiting for the feasibility check…"}</small>
                    {!busy && <button type="button" className="v3-cc-btn wide" onClick={() => plan && run("Checking feasibility and red-teaming…", () => engagementCheck(plan.id))}>Run the checks</button>}
                  </div>
                )}

                {allDone && (
                  <div className="v3-ak-done">
                    <b>Plan drafted and checked.</b>
                    {published ? (
                      <span className="v3-ep-saved"><Icon name="check" size={12} /> Saved to <a href="#/v3/brands">Campaigns & Journeys</a> with {Object.keys((published.campaigns ?? {}) as Any).length} campaign(s). The Campaign, Segmentation and Flow agents can work on them now.</span>
                    ) : (
                      <span className="v3-muted">Every step is kept as a version of this plan. Save it to put the plan and its campaigns in Campaigns & Journeys, where the other agents pick them up.</span>
                    )}
                    <button type="button" className="v3-cc-btn primary" disabled={!!busy} onClick={save}>{published ? "Save again" : "Save plan & campaigns"}</button>
                    <button type="button" className="v3-cc-btn" onClick={() => setShowReasoning(true)}>See the reasoning</button>
                    <button type="button" className="v3-cc-btn" disabled={!!busy} onClick={() => plan && run("Re-running options…", () => engagementOptions(plan.id, (agent.answers as Record<string, string>) ?? {}))}>Revisit the strategy</button>
                  </div>
                )}
              </div>
            )}
            {error && <p className="v3-cc-banner error">{error}</p>}
          </div>
        </aside>

        <section className="v3-ws-output v3-ep-out">
          {busy && plan && <p className="v3-ak-canvas-note"><span className="v3-cc-spinner small" /> {busy}</p>}
          {!bucket ? (
            <div className="v3-ws-empty">
              <Icon name="map" size={28} />
              <b>The diagnosis and plan build here</b>
              <span>Once you confirm what the agent has, it classifies the brand's situation and maps where patients are lost, then drafts the plan step by step.</span>
            </div>
          ) : (
            <PlanView plan={plan!} tab={tab} setTab={setTab} drafted={drafted} ladder={arr(fw?.adoption_ladder).map(String)} />
          )}
        </section>
        {showReasoning && <ReasoningPanel entries={entries} live={Boolean(busy)} onClose={() => setShowReasoning(false)} />}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ views */

function Src({ s }: { s: unknown }) {
  return s ? <small className="v3-iq-src">Source: {Array.isArray(s) ? s.join(", ") : txt(s)}</small> : null;
}

/** The leaky bucket: the classic funnel shape, fed only with real values. Leak stages are
 *  marked; stages with no figure say so. */
function Bucket({ bucket }: { bucket: Any }) {
  const stages = arr(bucket.stages);
  const leakStages = new Set(arr(bucket.leaks).map((l) => txt(l.stage)));
  const widths = stages.map((_, i) => 100 - i * (60 / Math.max(stages.length - 1, 1)));
  return (
    <div className="v3-ep-bucket">
      <div className="hier-funnel-shape">
        {stages.map((st, i) => {
          const next = widths[i + 1] ?? widths[i] * 0.85;
          const bottom = (next / widths[i]) * 100;
          const has = st.value !== null && st.value !== undefined && st.value !== "";
          return (
            <div key={txt(st.stage)} className={`hier-funnel-seg hier-funnel-seg-${Math.min(i, 3)} ${leakStages.has(txt(st.stage)) ? "leak" : ""}`}
              style={{ width: `${widths[i]}%`, clipPath: `polygon(0 0, 100% 0, ${50 + bottom / 2}% 100%, ${50 - bottom / 2}% 100%)` }}
              title={[txt(st.what), txt(st.caveat), txt(st.source)].filter(Boolean).join(" · ")}>
              <span className="hier-funnel-seg-label">{txt(st.stage)}{leakStages.has(txt(st.stage)) ? " · leak" : ""}</span>
              <span className="hier-funnel-seg-value">{has ? `${txt(st.value)}${txt(st.unit) === "%" ? "%" : ` ${txt(st.unit)}`}${st.verdict === "proxy" ? " (proxy)" : ""}` : "No figure"}</span>
            </div>
          );
        })}
      </div>
      <table className="v3-iq-table v3-ep-bucket-table"><thead><tr><th>Stage</th><th>Figure</th><th>What it measures</th><th>Source</th></tr></thead>
        <tbody>{stages.map((st) => (
          <tr key={txt(st.stage)}><td>{txt(st.stage)}</td><td>{st.value != null && st.value !== "" ? `${txt(st.value)} ${txt(st.unit)}` : <span className="v3-iq-needs">Gap</span>}{st.verdict === "proxy" && <small className="v3-iq-src">Proxy: {txt(st.caveat)}</small>}</td><td>{txt(st.what)}</td><td className="v3-iq-src">{txt(st.source)}</td></tr>
        ))}</tbody></table>
    </div>
  );
}

function Ladder({ rungs, today, target }: { rungs: string[]; today: string; target: string }) {
  const t0 = rungs.indexOf(today), t1 = rungs.indexOf(target);
  return (
    <div className="v3-ep-ladder">
      {rungs.map((r, i) => (
        <span key={r} className={`${i === t0 ? "today" : ""} ${i === t1 ? "target" : ""} ${t0 >= 0 && t1 >= 0 && i > t0 && i < t1 ? "between" : ""}`}>{r}</span>
      ))}
    </div>
  );
}

function PlanView({ plan, tab, setTab, drafted, ladder }: { plan: EngagementPlan; tab: Tab; setTab: (t: Tab) => void; drafted: boolean; ladder: string[] }) {
  const b = (plan.body ?? {}) as Any;
  const bucket = (b.bucket ?? {}) as Any;
  const objectives = arr(b.objectives), audiences = arr(b.audiences), shifts = arr(b.shifts), campaigns = arr(b.campaigns);
  const owned = useMemo(() => new Set(campaigns.flatMap((c) => arr(c.shift_refs).map(String))), [campaigns]);
  const audName = (id: unknown) => txt(audiences.find((a) => a.id === id)?.name) || txt(id);
  const objName = (id: unknown) => txt(objectives.find((o) => o.id === id)?.objective) || txt(id);
  const checks = (b.checks ?? null) as Any | null;
  const tabs: [Tab, string][] = [["diagnosis", "Diagnosis"], ...(drafted ? ([["overview", "Overview"], ["shifts", "Shift map"], ["portfolio", "Portfolio"], ["timeline", "Timeline"], ["budget", "Budget & KPIs"], ["checks", `Checks${checks ? ` (${arr(checks.feasibility).length + arr(checks.red_team).length})` : ""}`]] as [Tab, string][]) : [])];

  return (
    <div className="v3-ep-plan">
      <div className="v3-ep-tabs">
        {tabs.map(([t, l]) => <button key={t} type="button" className={tab === t ? "active" : ""} onClick={() => setTab(t)}>{l}</button>)}
      </div>

      {tab === "diagnosis" && (<>
        <h3 className="v3-iq-h3">Where {plan.brand} loses patients — {txt(bucket.indication)}</h3>
        {Boolean(bucket.why_this_indication) && <p className="v3-ep-why">{txt(bucket.why_this_indication)}</p>}
        <Bucket bucket={bucket} />
        {Boolean(bucket.geography) && (() => {
          const geo = bucket.geography as Any;
          return (<>
            <h3 className="v3-iq-h3">Where in the US</h3>
            <div className="v3-ep-geo">
              <div><em>Priority states</em>{arr(geo.priority_states).map((x) => <p key={txt(x.state)}><b>{txt(x.state)}</b> {txt(x.why)}</p>)}</div>
              <div><em>White space</em>{arr(geo.white_space).length ? arr(geo.white_space).map((x) => <p key={txt(x.state)}><b>{txt(x.state)}</b> {txt(x.why)}</p>) : <p className="v3-muted">None identified</p>}</div>
              {arr(geo.accounts).length > 0 && <div><em>Key accounts</em>{arr(geo.accounts).map((x, i) => <p key={i}>{String(x)}</p>)}</div>}
            </div>
          </>);
        })()}
        <h3 className="v3-iq-h3">Leaks</h3>
        <div className="v3-ep-leaks">
          {arr(bucket.leaks).map((l) => (
            <article key={txt(l.id)} className={txt(l.size)}>
              <div className="v3-iq-comp2-top"><b>{txt(l.id)} · {txt(l.stage)}</b><span className={`v3-iq-threat ${txt(l.size) === "large" ? "high" : txt(l.size) === "medium" ? "med" : "low"}`}>{txt(l.size)}</span></div>
              <p>{txt(l.finding)}</p>
              <Src s={l.evidence} />
            </article>
          ))}
        </div>
        {arr(bucket.natural_attrition).length > 0 && (<><h3 className="v3-iq-h3">Natural attrition (not a marketing leak)</h3><ul className="v3-ep-plain">{arr(bucket.natural_attrition).map((x, i) => <li key={i}>{String(x)}</li>)}</ul></>)}
        {arr(bucket.gaps).length > 0 && (<><h3 className="v3-iq-h3">Data gaps</h3><ul className="v3-ep-plain">{arr(bucket.gaps).map((x, i) => <li key={i} className="v3-iq-needs">{String(x)}</li>)}</ul></>)}
        {arr(b.root_causes).length > 0 && (<>
          <h3 className="v3-iq-h3">Root causes</h3>
          <div className="v3-iq-tablewrap"><table className="v3-iq-table"><thead><tr><th>Leak</th><th>Audience</th><th>Ladder rung</th><th>Belief</th><th>Behaviour</th></tr></thead>
            <tbody>{arr(b.root_causes).map((r, i) => (<tr key={i}><td>{txt(r.leak)}</td><td>{txt(r.audience)}</td><td>{txt(r.ladder_rung)}</td><td>{txt(r.belief)}</td><td>{txt(r.behaviour)}</td></tr>))}</tbody></table></div>
        </>)}
      </>)}

      {tab === "overview" && (<>
        {Boolean(((b.situation ?? {}) as Any).narrative) && <p className="v3-iq-lede-lg">{txt(((b.situation ?? {}) as Any).narrative)}</p>}
        <h3 className="v3-iq-h3">Objectives</h3>
        <div className="v3-iq-objs">
          {objectives.map((o, i) => (
            <article key={txt(o.id)} className={txt(o.priority).toLowerCase()}>
              <div className="v3-iq-obj-top"><span className="v3-iq-obj-n">{i + 1}</span><span className="v3-iq-tier">{txt(o.priority)}{o.leak ? ` · ${txt(o.leak)}` : ""}</span></div>
              <b>{txt(o.objective)}</b>
              <span>{txt(o.kpi)}{o.baseline || o.target ? ` · ${txt(o.baseline) || "?"} → ${txt(o.target) || "?"}` : ""}{o.by ? ` · by ${txt(o.by)}` : ""}</span>
              <Src s={o.source} />
            </article>
          ))}
        </div>
        <h3 className="v3-iq-h3">Audiences on the adoption ladder — today → target</h3>
        <div className="v3-ep-auds">
          {audiences.map((a) => (
            <article key={txt(a.id)}>
              <b>{txt(a.name)}</b>
              <Ladder rungs={ladder} today={txt(a.ladder_today)} target={txt(a.ladder_target)} />
              <small className="v3-muted">{txt(a.why_now)}</small>
            </article>
          ))}
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
                      {Boolean(s.ladder_move) && <span className="v3-iq-tier primary">{txt(s.ladder_move)}</span>}
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
              <span className="v3-iq-comp2-meta">{txt(c.type)} · {txt(c.start)} → {txt(c.end)} · {arr(c.audience_ids).map(audName).join(", ")}{c.content ? ` · content: ${txt(c.content)}` : ""}</span>
              {Boolean(c.geography || c.target_hcps) && <span className="v3-iq-comp2-meta"><Icon name="map" size={11} /> {Array.isArray(c.geography) ? (c.geography as unknown[]).join(", ") : txt(c.geography) || "National"}{c.target_hcps ? ` · ~${Number(c.target_hcps).toLocaleString()} HCPs` : ""}</span>}
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
        {(["by_objective", "by_audience", "by_channel", "by_region"] as const).map((k) => {
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

      {tab === "checks" && (checks ? (<>
        <h3 className="v3-iq-h3">Feasibility</h3>
        {arr(checks.feasibility).length ? arr(checks.feasibility).map((f, i) => (
          <div key={i} className="v3-iq-rule dont"><span>!</span><div><em>{txt(f.check)} · {txt(f.severity)}</em><p>{txt(f.issue)}</p><small className="v3-muted">Fix: {txt(f.fix)}</small></div></div>
        )) : <p className="v3-ep-ok">No feasibility issues: every shift has a campaign, dates and budgets add up, approval lead times and audience load are within limits.</p>}
        <h3 className="v3-iq-h3">Red team</h3>
        {arr(checks.red_team).map((r, i) => (
          <div key={i} className="v3-ep-red"><span className={`v3-iq-threat ${txt(r.severity) === "high" ? "high" : txt(r.severity) === "medium" ? "med" : "low"}`}>{txt(r.severity)}</span>
            <div><b>{txt(r.issue)}</b><p>{txt(r.why_it_matters)}</p><p><em>Fix</em>{txt(r.fix)}</p></div></div>
        ))}
      </>) : <p className="v3-muted">Not checked yet.</p>)}
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
