import { useCallback, useEffect, useState } from "react";
import {
  ep2Ack, ep2Approve, ep2Create, ep2Get, ep2List, ep2Publish, ep2Run, uploadAgentIntake, type EP2Plan,
} from "../../api";
import { Icon } from "../../components/Icon";
import type { BrandSummary } from "../../types";
import { AckCard, ReadyIntake, ReasoningButton, ReasoningPanel, type ReasonEntry } from "../agentkit/AgentKit";
import { MermaidView } from "../campaignplanner/MermaidView";
import "../campaignplanner/campaignPlanner.css";
import "../agentkit/agentkit.css";
import "../iq.css";
import "./ep2.css";

/** Engagement Planner 2: the CampaignFlow 30-minute planning framework as an agent
 *  (config/frameworks/campaignflow.json, strategy/campaignflow.py). Intake -> acknowledgement -> six
 *  steps, each a draft until you approve it (or redo it with your changes); the next step reads only
 *  approved output. The step artifacts are the canvas; Live reasoning is a slide-in panel. */

type Any = Record<string, unknown>;
const txt = (v: unknown) => (v === null || v === undefined ? "" : typeof v === "object" ? JSON.stringify(v) : String(v));
const arr = (v: unknown) => (Array.isArray(v) ? (v as Any[]) : []);
const obj = (v: unknown) => (v && typeof v === "object" && !Array.isArray(v) ? (v as Any) : {});

const STEPS = [
  { id: "objective", name: "Objective card", full: "Campaign objective card" },
  { id: "audience", name: "Target audience", full: "Target audience segmentation" },
  { id: "channels", name: "Channel plan", full: "Channel planning" },
  { id: "journeys", name: "Journey design", full: "Journey design" },
  { id: "omnichannel", name: "Omnichannel rules", full: "Omnichannel planning" },
  { id: "brief", name: "Campaign brief", full: "Campaign brief" },
];

function errText(e: unknown): string {
  const s = String(e);
  const i = s.indexOf("{");
  if (i >= 0) { try { const d = JSON.parse(s.slice(i)).detail; if (typeof d === "string") return d; } catch { /* not JSON */ } }
  return s;
}

function summary(id: string, o: Any): string {
  switch (id) {
    case "objective": return txt(o.campaign_name);
    case "audience": return `${arr(o.segments).length} segments · ${txt(o.mode)}`;
    case "channels": return arr(o.candidates).filter((c) => c.result === "live").map((c) => txt(c.channel)).join(", ");
    case "journeys": return arr(o.journeys).map((j) => txt(j.name)).join(", ");
    case "omnichannel": return `${arr(o.rules).length} rules`;
    case "brief": return `${arr(o.sections).length} sections · ${arr(o.qa).length} QA cases`;
    default: return "";
  }
}

export function EngagementPlanner2({ brands, activeBrand, planId }: { brands: BrandSummary[]; activeBrand: string | null; planId?: string }) {
  const brand = activeBrand ?? brands[0]?.brand ?? null;
  const [plan, setPlan] = useState<EP2Plan | null>(null);
  const [plans, setPlans] = useState<{ id: string; title: string; version: number; approved: number }[]>([]);
  const [files, setFiles] = useState<File[]>([]);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState("");
  const [tab, setTab] = useState("objective");
  const [showReasoning, setShowReasoning] = useState(false);

  const refreshList = useCallback(() => {
    if (brand) ep2List(brand).then((r) => setPlans(r.plans)).catch(() => setPlans([]));
  }, [brand]);
  useEffect(refreshList, [refreshList]);
  useEffect(() => {
    if (!planId) { setPlan(null); return; }
    if (plan?.id !== planId) ep2Get(planId).then(setPlan).catch((e) => setError(errText(e)));
  }, [planId]);  // eslint-disable-line react-hooks/exhaustive-deps

  const run = async (label: string, fn: () => Promise<EP2Plan>): Promise<EP2Plan | null> => {
    setBusy(label); setError(null);
    try { const p = await fn(); setPlan(p); refreshList(); return p; }
    catch (e) { setError(errText(e)); return null; }
    finally { setBusy(null); }
  };

  const start = async () => {
    if (!brand) return;
    const p = await run("Creating the plan…", () => ep2Create(brand));
    if (!p) return;
    window.location.hash = `#/v3/agent/engagement-planner-2/${p.id}`;
    setBusy("Reading the brand plan and Brand IQ…");
    try { await uploadAgentIntake("engagement-planner-2", p.id, files, notes); } catch (e) { setError(errText(e)); setBusy(null); return; }
    await run("Reading the brand plan and Brand IQ…", () => ep2Ack(p.id));
  };

  const steps = plan?.steps ?? {};
  const current = STEPS.findIndex((s) => steps[s.id]?.status !== "approved");
  const allApproved = plan ? current === -1 : false;
  const cur = current >= 0 ? STEPS[current] : null;
  const curStep = cur ? steps[cur.id] : undefined;

  const runStep = async (i: number, fb?: string) => {
    if (!plan) return;
    const s = STEPS[i];
    const p = await run(`Step ${i + 1} · ${s.full}${fb ? " (revising)" : ""}…`, () => ep2Run(plan.id, s.id, fb));
    if (p) { setTab(s.id); setFeedback(""); }
  };
  const approveAndContinue = async () => {
    if (!plan || current < 0) return;
    const p = await run(`Approving step ${current + 1}…`, () => ep2Approve(plan.id, STEPS[current].id));
    if (p && current + 1 < STEPS.length) await runStep(current + 1);
  };
  const save = () => plan && run("Saving to Campaigns & Journeys…", () => ep2Publish(plan.id));

  const entries: ReasonEntry[] = [];
  if (plan?.ack) entries.push({ id: "ack", title: "Reading the brand plan", status: "done", lines: [plan.ack.understood ?? "", ...(plan.ack.approach ?? [])].filter(Boolean) });
  STEPS.forEach((s, i) => { const st = steps[s.id]; if (st) entries.push({ id: s.id, title: `Step ${i + 1} · ${s.full}`, status: "done", lines: st.reasoning ?? [] }); });
  if (busy) entries.push({ id: "busy", title: busy, status: "running", lines: [] });

  if (!brand) return <p className="v3-empty">Add a brand first.</p>;
  const shown = STEPS.filter((s) => steps[s.id]);
  const out = obj(steps[tab]?.output);

  return (
    <div className="v3-ws v3-cc v3-ep2">
      <div className="v3-ws-top">
        <span className="v3-ep-title">{plan ? plan.title : `New campaign plan — ${brand}`}</span>
        {plan && <span className="v3-ws-save">v{plan.version} · CampaignFlow framework</span>}
        <span className="v3-ws-top-actions">
          {plans.length > 0 && (
            <select className="v3-ep-select" value={plan?.id ?? ""} onChange={(e) => { window.location.hash = e.target.value ? `#/v3/agent/engagement-planner-2/${e.target.value}` : "#/v3/agent/engagement-planner-2"; }}>
              <option value="">+ New plan</option>
              {plans.map((p) => <option key={p.id} value={p.id}>{p.title} ({p.approved}/6)</option>)}
            </select>
          )}
          {steps.journeys?.status === "approved" && (
            <button type="button" className="v3-cc-btn primary" disabled={!!busy} onClick={save}>{plan?.published ? "Save again" : "Save plan"}</button>
          )}
          <ReasoningButton live={Boolean(busy)} onClick={() => setShowReasoning((v) => !v)} />
        </span>
      </div>

      <div className="v3-ws-body">
        <aside className="v3-ws-inputs">
          <div className="v3-ws-scroll">
            <div className="v3-ws-head">
              <span className="v3-app-icon lg"><Icon name="layers" size={20} /></span>
              <div className="v3-ws-head-text">
                <h1>Engagement Planning Agent</h1>
                <p>Runs the CampaignFlow framework for one {brand} campaign: from the brand plan to a build-ready campaign brief, one approved step at a time.</p>
              </div>
            </div>

            <ol className="v3-cc-stepper" aria-label="CampaignFlow progress">
              {STEPS.map((s, i) => {
                const st = steps[s.id]?.status;
                return (
                  <li key={s.id} className={st === "approved" ? "done" : plan?.ack && i === current ? "active" : ""}>
                    <span>{st === "approved" ? <Icon name="check" size={9} /> : i + 1}</span>{s.name}
                  </li>
                );
              })}
            </ol>

            {!plan && (
              <ReadyIntake brand={brand} startLabel="Start planning" busy={!!busy} busyLabel={busy} onStart={start}
                files={files} setFiles={setFiles} notes={notes} setNotes={setNotes}
                addLabel="Add campaign details or briefs" notesLabel="Which campaign is this?"
                placeholder="Which campaign is this? Leave empty to plan from Brand IQ." />
            )}

            {plan && (
              <div className="v3-ak-progress">
                {STEPS.map((s, i) => steps[s.id]?.status === "approved" && (
                  <button key={s.id} type="button" className="v3-ak-row done v3-ep2-row" onClick={() => setTab(s.id)}>
                    <span className="v3-ak-dot"><Icon name="check" size={9} /></span><b>{i + 1} · {s.full}</b>
                    <small>{summary(s.id, obj(steps[s.id].output))}</small>
                  </button>
                ))}

                {!Object.keys(steps).length && (
                  plan.ack ? <AckCard ack={plan.ack} onConfirm={() => runStep(0)} onEdit={() => { window.location.hash = "#/v3/agent/engagement-planner-2"; }} />
                    : !busy && <button type="button" className="v3-cc-btn primary wide" onClick={() => run("Reading the brand plan and Brand IQ…", () => ep2Ack(plan.id))}>Read the brand plan</button>
                )}

                {cur && (curStep || busy) && (
                  <div className="v3-ak-row current">
                    <div className="v3-ak-row-head">
                      <span className="v3-ak-dot">{busy ? <span className="v3-cc-spinner small" /> : current + 1}</span>
                      <b>{current + 1} · {cur.full}</b>
                      {curStep?.status === "stale" && <small className="v3-ep2-stale">An earlier step changed — redo this one</small>}
                    </div>
                    {busy ? <small className="v3-ep-busy-line">{busy}</small> : curStep && (
                      <div className="v3-ep-sub">
                        <em>Review the draft on the right</em>
                        {cur.id === "objective" && arr(curStep.output.questions).length > 0 && (
                          <div className="v3-ep2-qs">
                            <b>Questions raised (not invented)</b>
                            {arr(curStep.output.questions).map((q, k) => <p key={k}>{txt(q.question)} <small>{txt(q.owner)}</small></p>)}
                          </div>
                        )}
                        <textarea className="v3-glass-text" rows={3} value={feedback} onChange={(e) => setFeedback(e.target.value)}
                          placeholder="Anything to change? e.g. answer a question, narrow the audience, drop a channel…" />
                        <div className="v3-ep2-actions">
                          <button type="button" className="v3-cc-btn primary" disabled={curStep.status === "stale"} onClick={approveAndContinue}>
                            {current + 1 < STEPS.length ? "Approve & continue" : "Approve the brief"}
                          </button>
                          <button type="button" className="v3-cc-btn" onClick={() => runStep(current, feedback.trim() || "Redo this step.")}>
                            {feedback.trim() ? "Redo with my changes" : "Redo"}
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )}
                {cur && !curStep && !busy && Object.keys(steps).length > 0 && (
                  <button type="button" className="v3-cc-btn primary wide" onClick={() => runStep(current)}>Run step {current + 1} · {cur.full}</button>
                )}

                {allApproved && (
                  <div className="v3-ak-done">
                    <b>All six steps approved.</b>
                    {plan.published
                      ? <span className="v3-ep-saved"><Icon name="check" size={12} /> Saved to <a href="#/v3/brands">Campaigns & Journeys</a> with {Object.keys(plan.published.flows ?? {}).length} journey(s). It shows in Live simulation.</span>
                      : <span className="v3-muted">Save it to put the campaign and its journeys in Campaigns & Journeys and Live simulation.</span>}
                    <button type="button" className="v3-cc-btn primary" disabled={!!busy} onClick={save}>{plan.published ? "Save again" : "Save plan & journeys"}</button>
                    <button type="button" className="v3-cc-btn" onClick={() => setShowReasoning(true)}>See the reasoning</button>
                  </div>
                )}
              </div>
            )}
            {error && <p className="v3-cc-banner error">{error}</p>}
          </div>
        </aside>

        <section className="v3-ws-output v3-ep2-out">
          {busy && plan && <p className="v3-ak-canvas-note"><span className="v3-cc-spinner small" /> {busy}</p>}
          {!shown.length ? (
            <div className="v3-ws-empty">
              <Icon name="layers" size={28} />
              <b>The plan builds here, step by step</b>
              <span>Objective card → target audience → channel plan → journeys → omnichannel rules → campaign brief. Each step waits for your approval.</span>
            </div>
          ) : (
            <>
              <div className="v3-av-tabs" role="tablist">
                {shown.map((s) => (
                  <button key={s.id} type="button" role="tab" aria-selected={tab === s.id} className={tab === s.id ? "active" : ""} onClick={() => setTab(s.id)}>
                    {STEPS.indexOf(s) + 1} · {s.name}{steps[s.id].status !== "approved" && <em className={`v3-ep2-tag ${steps[s.id].status}`}>{steps[s.id].status}</em>}
                  </button>
                ))}
              </div>
              {!steps[tab] ? <p className="v3-muted">Pick a step above.</p>
                : tab === "objective" ? <ObjectiveView o={out} />
                : tab === "audience" ? <AudienceView o={out} />
                : tab === "channels" ? <ChannelsView o={out} />
                : tab === "journeys" ? <JourneysView o={out} />
                : tab === "omnichannel" ? <OmniView o={out} />
                : <BriefView o={out} />}
            </>
          )}
        </section>
        {showReasoning && <ReasoningPanel entries={entries} live={Boolean(busy)} onClose={() => setShowReasoning(false)} />}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ step views */

function Table({ rows, cols }: { rows: Any[]; cols: [string, string][] }) {
  if (!rows.length) return <p className="v3-muted">None.</p>;
  return (
    <div className="v3-iq-tablewrap"><table className="v3-iq-table">
      <thead><tr>{cols.map(([, l]) => <th key={l}>{l}</th>)}</tr></thead>
      <tbody>{rows.map((r, i) => <tr key={i}>{cols.map(([k]) => <td key={k}>{Array.isArray(r[k]) ? (r[k] as unknown[]).map(txt).join(", ") : txt(r[k])}</td>)}</tr>)}</tbody>
    </table></div>
  );
}

function Gaps({ rows, title = "Gap register" }: { rows: Any[]; title?: string }) {
  if (!rows.length) return null;
  return (<><h3 className="v3-iq-h3">{title}</h3>
    <div className="v3-ep2-gaps">{rows.map((g, i) => <div key={i}><Icon name="alertTriangle" size={12} /><span>{txt(g.gap ?? g.item)}{g.blocks ? ` — blocks ${txt(g.blocks)}` : ""}</span><small>{txt(g.owner ?? (g.returns_to_step ? `back to step ${txt(g.returns_to_step)}` : ""))}</small></div>)}</div></>);
}

const CARD_FIELDS: [string, string][] = [
  ["campaign_objective", "Campaign objective"], ["target_audience", "Target audience"], ["current_behaviour", "Current behaviour"],
  ["desired_behaviour", "Desired behaviour"], ["strategic_imperative", "Strategic imperative"],
  ["messaging_guardrails", "Messaging & guardrails"], ["channel_priorities", "Channel priorities"],
];

function ObjectiveView({ o }: { o: Any }) {
  const card = obj(o.card), roles = obj(o.audience_roles), timing = obj(o.timing);
  return (
    <div className="v3-ep2-view">
      <p className="v3-ep2-eyebrow">Step 01 · Campaign objective card</p>
      <h2 className="v3-ep2-h">{txt(o.campaign_name)}</h2>
      <div className="v3-ep2-pills"><span>{txt(o.brand_mode) === "launch" ? "Launch brand" : "Existing brand"}</span>{Boolean(o.mode_reason) && <small>{txt(o.mode_reason)}</small>}</div>
      <div className="v3-ep2-card">
        {CARD_FIELDS.map(([k, label]) => {
          const f = obj(card[k]);
          const q = /question/i.test(txt(f.source));
          return (
            <div key={k} className={q ? "q" : ""}>
              <em>{label}</em>
              <p>{txt(f.value) || "—"}</p>
              <small>{txt(f.source)}</small>
            </div>
          );
        })}
      </div>
      <div className="v3-ep2-two">
        <div><h3 className="v3-iq-h3">Primary prescribers</h3><ul className="v3-ep-plain">{arr(roles.primary_prescribers).map((r, i) => <li key={i}>{txt(r)}</li>)}</ul></div>
        <div><h3 className="v3-iq-h3">Adjacent pathway</h3><ul className="v3-ep-plain">{arr(roles.adjacent_pathway).map((r, i) => <li key={i}>{txt(r)}</li>)}</ul></div>
      </div>
      <h3 className="v3-iq-h3">KPIs (inherited from the brand plan)</h3>
      <Table rows={arr(o.kpis)} cols={[["kpi", "KPI"], ["target", "Target"], ["source", "Source"]]} />
      {Boolean(timing.earliest_start) && <p className="v3-ep2-note"><b>Earliest start:</b> {txt(timing.earliest_start)} — {txt(timing.why)}</p>}
      <Gaps title="Questions raised" rows={arr(o.questions).map((q) => ({ gap: q.question, blocks: q.why ? undefined : undefined, owner: q.owner }))} />
    </div>
  );
}

function AudienceView({ o }: { o: Any }) {
  const uni = obj(o.universe), prim = obj(uni.primary), adj = obj(uni.adjacent);
  const segs = arr(o.segments);
  const cell = (opp: string, reach: string) => segs.filter((s) => (txt(s.brand_opportunity) === "High") === (opp === "High") && (txt(s.hcp_reachability) === "High") === (reach === "High"));
  return (
    <div className="v3-ep2-view">
      <p className="v3-ep2-eyebrow">Step 02 · Target audience segmentation</p>
      <h2 className="v3-ep2-h">{txt(o.mode) === "launch" ? "Launch audience (IQVIA eligibility)" : "Existing brand: Rx lifecycle → strategic priority"}</h2>
      <div className="v3-ep2-two">
        <div className="v3-ep2-box"><em>Primary prescriber universe</em><p>{arr(prim.specialties).map(txt).join(", ")}</p><small>{txt(prim.inclusion)}</small></div>
        <div className="v3-ep2-box"><em>Adjacent pathway universe</em><p>{arr(adj.roles).map(txt).join(", ")}</p><small>{txt(adj.inclusion)}</small></div>
      </div>
      {arr(o.gates).length > 0 && <><h3 className="v3-iq-h3">Eligibility gates (not scored)</h3><Table rows={arr(o.gates)} cols={[["gate", "Gate"], ["rule", "Rule"]]} /></>}
      <h3 className="v3-iq-h3">Segments</h3>
      <Table rows={segs.map((s) => ({ ...s, est_hcps: Number.isFinite(Number(s.est_hcps)) && s.est_hcps !== null && s.est_hcps !== "" ? Number(s.est_hcps).toLocaleString() : "Gap" }))} cols={[["segment", "Segment"], ["definition", "Definition"], ["strategic_priority", "Strategic priority"], ["est_hcps", "HCPs"], ["brand_opportunity", "Opportunity"], ["hcp_reachability", "Reachability"], ["investment_priority", "Investment"], ["desired_progression", "Desired progression"]]} />
      {segs.some((x) => x.count_source) && <small className="v3-muted">Counts: {Array.from(new Set(segs.map((x) => txt(x.count_source)).filter(Boolean))).slice(0, 2).join(" · ")}</small>}
      {txt(o.mode) !== "launch" && segs.length > 0 && (
        <>
          <h3 className="v3-iq-h3">Prioritization matrix · brand opportunity × HCP reachability</h3>
          <div className="v3-ep2-matrix">
            {[["High", "Low"], ["High", "High"], ["Low", "Low"], ["Low", "High"]].map(([opp, reach]) => (
              <div key={opp + reach}>
                <em>{opp} opportunity · {reach === "High" ? "high" : "lower"} reachability</em>
                {cell(opp, reach).map((s) => <span key={txt(s.segment)} className="v3-ep2-chip">{txt(s.segment)} · {txt(s.strategic_priority)}</span>)}
              </div>
            ))}
          </div>
        </>
      )}
      {arr(o.adjacent_segments).length > 0 && <><h3 className="v3-iq-h3">Adjacent pathway (Enable)</h3><Table rows={arr(o.adjacent_segments)} cols={[["role", "Role"], ["strategic_priority", "Priority"], ["est_hcps", "HCPs"], ["pathway_kpi", "Pathway KPI"]]} /></>}
      {Boolean(o.focus) && <p className="v3-ep2-note"><b>Focus:</b> {txt(o.focus)}</p>}
      <Gaps rows={arr(o.gaps)} />
    </div>
  );
}

function ChannelsView({ o }: { o: Any }) {
  return (
    <div className="v3-ep2-view">
      <p className="v3-ep2-eyebrow">Step 03 · Channel planning</p>
      <h2 className="v3-ep2-h">Which channels deliver the movement</h2>
      <Table rows={arr(o.engagement_needs)} cols={[["progression", "Desired progression"], ["need", "Engagement need"]]} />
      <h3 className="v3-iq-h3">Four checks</h3>
      <div className="v3-iq-tablewrap"><table className="v3-iq-table">
        <thead><tr><th>Channel</th><th>01 Message fit</th><th>02 HCP engagement</th><th>03 Consent & access</th><th>04 Feasibility</th><th>Result</th></tr></thead>
        <tbody>{arr(o.candidates).map((c, i) => (
          <tr key={i} className={c.result === "removed" ? "v3-ep2-removed" : ""}>
            <td><b>{txt(c.channel)}</b></td><td>{txt(c.message_fit)}</td><td>{txt(c.hcp_engagement)}</td><td>{txt(c.consent_access)}</td><td>{txt(c.feasibility)}</td>
            <td><span className={`v3-ep2-tag ${txt(c.result)}`}>{txt(c.result)}</span>{c.reason ? <small> {txt(c.reason)}</small> : null}</td>
          </tr>))}</tbody>
      </table></div>
      <h3 className="v3-iq-h3">Live mix (2 default, 3 max)</h3>
      <div className="v3-ep2-grid">
        {arr(o.mix).map((m, i) => (
          <div key={i} className="v3-ep2-box">
            <em>{txt(m.segment)} · {txt(m.progression)}</em>
            <small>Investment {txt(m.investment_priority)} · digital affinity {txt(m.digital_affinity)}</small>
            {arr(m.channels).map((c, j) => <p key={j}><b>{txt(c.channel)}</b> — {txt(c.job)}{arr(c.modules).length ? <small> · {arr(c.modules).map(txt).join(", ")}</small> : null}</p>)}
          </div>
        ))}
      </div>
      <h3 className="v3-iq-h3">Execution constraints</h3>
      <Table rows={arr(o.constraints)} cols={[["type", "Type"], ["rule", "Rule"]]} />
      <Gaps rows={arr(o.gap_register)} />
    </div>
  );
}

const mmText = (s: string) => s.replace(/["<>{}[\]()|#;]/g, " ").replace(/\s+/g, " ").trim().slice(0, 60);

function journeyMermaid(j: Any): string {
  const steps = arr(j.steps);
  const ids = new Set(steps.map((s) => txt(s.id)));
  const lines = ["flowchart TD", `  E(["Entry: ${mmText(txt(j.entry))}"])`];
  steps.forEach((s, i) => {
    const id = txt(s.id) || `S${i}`;
    lines.push(`  ${id}["${mmText(`${id} ${txt(s.play)}`)}<br/>${mmText(`${txt(s.channel)}: ${txt(s.module) || txt(s.tactic)}`)}<br/><i>${mmText(`wait ${txt(s.wait)}`)}</i>"]`);
    if (i === 0) lines.push(`  E --> ${id}`);
    const next = txt(s.on_signal);
    if (ids.has(next)) lines.push(`  ${id} -->|signal| ${next}`);
    else if (i + 1 < steps.length) lines.push(`  ${id} -->|signal| ${txt(steps[i + 1].id) || `S${i + 1}`}`);
    else lines.push(`  ${id} -->|signal| X`);
    lines.push(`  ${id}N["${mmText(txt(s.on_no_signal) || "wait / retry / alternate")}"]`);
    lines.push(`  ${id} -.->|no signal| ${id}N`);
    lines.push(`  ${id}N -.-> ${id}`);
  });
  lines.push(`  X(["Exit: ${mmText(arr(j.exit).map(txt).join(" / ") || "sequence complete")} → ${mmText(txt(j.next_journey))}"])`);
  return lines.join("\n");
}

function JourneysView({ o }: { o: Any }) {
  const [i, setI] = useState(0);
  const js = arr(o.journeys);
  const j = js[i];
  return (
    <div className="v3-ep2-view">
      <p className="v3-ep2-eyebrow">Step 04 · Journey design → customer engagement plan</p>
      <h2 className="v3-ep2-h">Signal → next-best tactic → wait → progression</h2>
      <div className="v3-ep-tabs">{js.map((x, k) => <button key={k} type="button" className={k === i ? "active" : ""} onClick={() => setI(k)}>{txt(x.id)} · {txt(x.name)} <small>({txt(x.type)})</small></button>)}</div>
      {j && (
        <>
          <div className="v3-ep2-grid four">
            <div className="v3-ep2-box"><em>Entry</em><p>{txt(j.entry)}</p></div>
            <div className="v3-ep2-box"><em>Objective</em><p>{txt(j.objective)}</p></div>
            <div className="v3-ep2-box"><em>Cadence</em><p>{txt(j.cadence)}</p></div>
            <div className="v3-ep2-box"><em>Exit → next journey</em><p>{arr(j.exit).map(txt).join(" · ")} → {txt(j.next_journey)}</p><small>Opt-out: {txt(j.opt_out)}</small></div>
          </div>
          <MermaidView code={journeyMermaid(j)} fileName={`journey-${txt(j.id)}`} />
          <h3 className="v3-iq-h3">Tactic catalog</h3>
          <Table rows={arr(j.steps)} cols={[["id", "ID"], ["play", "Play"], ["tactic", "Tactic"], ["channel", "Channel"], ["module", "Module"], ["cta", "CTA"], ["wait", "Wait"], ["signal", "Signal"], ["on_signal", "On signal"], ["on_no_signal", "No signal"]]} />
        </>
      )}
      <h3 className="v3-iq-h3">Branch catalog</h3>
      <Table rows={arr(o.branch_catalog)} cols={[["branch", "Branch"], ["trigger", "Trigger"], ["action", "Journey action"]]} />
      <h3 className="v3-iq-h3">Movability (intensity only)</h3>
      <Table rows={arr(o.movability)} cols={[["segment", "Segment"], ["score", "Movability"], ["effect", "Effect on the journey"]]} />
      <h3 className="v3-iq-h3">Measures</h3>
      <Table rows={arr(o.measures)} cols={[["measure", "Measure"], ["why", "Why"]]} />
      <Gaps rows={arr(o.gap_register)} />
    </div>
  );
}

function OmniView({ o }: { o: Any }) {
  return (
    <div className="v3-ep2-view">
      <p className="v3-ep2-eyebrow">Step 05 · Omnichannel plan / orchestration specification</p>
      <h2 className="v3-ep2-h">One rule source, written before platform build</h2>
      <h3 className="v3-iq-h3">Event & evidence dictionary</h3>
      <Table rows={arr(o.signals)} cols={[["signal", "Signal"], ["meaning", "Meaning"], ["evidence_window", "Evidence window"]]} />
      <h3 className="v3-iq-h3">Rule catalog</h3>
      <div className="v3-iq-tablewrap"><table className="v3-iq-table">
        <thead><tr><th>Rule ID</th><th>Journey</th><th>Type</th><th>IF</th><th>THEN</th><th>ELSE</th></tr></thead>
        <tbody>{arr(o.rules).map((r, i) => (
          <tr key={i}><td><code>{txt(r.id)}</code>{r.hard_gate ? <span className="v3-ep2-tag gate">hard gate</span> : null}</td><td>{txt(r.journey)}</td><td>{txt(r.type)}</td><td>{txt(r.if)}</td><td>{txt(r.then)}</td><td>{txt(r.else)}</td></tr>
        ))}</tbody>
      </table></div>
      <h3 className="v3-iq-h3">Channel sequence</h3>
      <Table rows={arr(o.channel_sequence)} cols={[["journey", "Journey"], ["starts", "Starts"], ["follows_signal", "Follows a signal"], ["covers_no_response", "Covers no response"]]} />
      <h3 className="v3-iq-h3">Safe outcomes</h3>
      <Table rows={arr(o.safe_outcomes)} cols={[["when", "When"], ["outcome", "Outcome"]]} />
      <h3 className="v3-iq-h3">Approvals</h3>
      <Table rows={arr(o.approvals)} cols={[["who", "Who"], ["approves", "Approves"]]} />
      <Gaps title="Blocking gaps (return upstream)" rows={arr(o.upstream_gaps)} />
    </div>
  );
}

function BriefView({ o }: { o: Any }) {
  return (
    <div className="v3-ep2-view">
      <p className="v3-ep2-eyebrow">Step 06 · Campaign brief</p>
      <h2 className="v3-ep2-h">Build-ready handoff to Campaign Operations</h2>
      <div className="v3-ep2-sections">
        {arr(o.sections).map((s, i) => (
          <div key={i} className="v3-ep2-box"><em>{txt(s.n)}. {txt(s.title)}</em><p>{txt(s.content)}</p><small>Owner: {txt(s.owner)}</small></div>
        ))}
      </div>
      <h3 className="v3-iq-h3">Build mapping (references step 05 rule IDs)</h3>
      <Table rows={arr(o.build_mapping)} cols={[["journey", "Journey"], ["entry", "Entry"], ["initial_tactic", "Initial tactic"], ["rule_ids", "Rule IDs"], ["content", "Content"], ["channel", "Channel"], ["exit", "Exit"], ["next_journey", "Next journey"], ["safe_outcome", "Safe outcome"]]} />
      <h3 className="v3-iq-h3">QA / UAT scenarios</h3>
      <Table rows={arr(o.qa)} cols={[["scenario", "Scenario"], ["expected", "Expected result"], ["rule_ids", "Rule IDs"]]} />
      <h3 className="v3-iq-h3">Definition of done</h3>
      <div className="v3-ep2-dod">{arr(o.definition_of_done).map((d, i) => (
        <div key={i} className={txt(d.status)}><span>{txt(d.status) === "met" ? <Icon name="check" size={11} /> : "○"}</span><b>{txt(d.item)}</b><small>{txt(d.why)}</small></div>
      ))}</div>
      <Gaps title="Open items" rows={arr(o.open_items)} />
    </div>
  );
}
