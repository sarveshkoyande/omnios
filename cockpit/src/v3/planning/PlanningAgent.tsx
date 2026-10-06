import { useCallback, useEffect, useState } from "react";
import {
  paAck, paApprove, paChat, paCreate, paGet, paLatest, paList, paPublish, paRun, uploadAgentIntake,
  type PAAction, type PARecord,
} from "../../api";
import { Icon } from "../../components/Icon";
import type { BrandSummary } from "../../types";
import { AckCard, AgentChat, ReadyIntake, ReasoningButton, ReasoningPanel, type ReasonEntry } from "../agentkit/AgentKit";
import "../campaignplanner/campaignPlanner.css";
import "../agentkit/agentkit.css";
import "../iq.css";
import "../ep2/ep2.css";
import "./planning.css";

/** Engagement Planning, Segmentation and Channel agents: one screen, three agents (strategy/planning_agents.py).
 *  The Engagement Planning Agent runs objectives -> focus -> approach -> portfolio; "focus" is the Segmentation
 *  Agent and "approach" the Channel Mix Agent, called inside the plan and also runnable on their own. Each step is a
 *  draft until approved (or auto-run); the chat box steers the agent at any point. */

type Any = Record<string, unknown>;
const txt = (v: unknown) => (v === null || v === undefined ? "" : typeof v === "object" ? JSON.stringify(v) : String(v));
const arr = (v: unknown) => (Array.isArray(v) ? (v as Any[]) : []);
const obj = (v: unknown) => (v && typeof v === "object" && !Array.isArray(v) ? (v as Any) : {});

const STEP_META: Record<string, { name: string; full: string; by?: string; icon: Parameters<typeof Icon>[0]["name"] }> = {
  objectives: { name: "Objectives", full: "Objectives for the period", icon: "target" },
  focus: { name: "Where to focus", full: "Where to focus", by: "Segmentation Planner Agent", icon: "users" },
  approach: { name: "Message & channels", full: "Message & channel approach", by: "Channel Mix Agent", icon: "megaphone" },
  portfolio: { name: "Campaign portfolio", full: "Campaign portfolio", icon: "calendar" },
};

type AgentCfg = { id: string; name: string; icon: Parameters<typeof Icon>[0]["name"]; steps: string[]; blurb: (b: string) => string;
  start: string; placeholder: string; suggestions: string[] };
export const PLANNING_AGENTS: Record<string, AgentCfg> = {
  "engagement-planner-2": {
    id: "engagement-planner-2", name: "Engagement Planning Agent", icon: "layers", steps: ["objectives", "focus", "approach", "portfolio"],
    blurb: (b) => `Turns ${b}'s brand plan into the engagement strategy for the period: objectives, who to focus on, message and channels, and the campaigns. It reuses the Brand Kit and calls the Segmentation Planner and Channel Mix agents.`,
    start: "Start planning", placeholder: "Anything the plan should focus on? Leave empty to plan from the brand plan and Brand Kit.",
    suggestions: ["Focus on HCPs only for now", "Why this priority?", "Run everything, I'll review at the end"],
  },
  "brand-persona-builder": {
    id: "brand-persona-builder", name: "Segmentation Planner Agent", icon: "users", steps: ["focus"],
    blurb: (b) => `Decides which of ${b}'s audiences get focus and the ladder move each must make (aware → interested → trial → adopt → advocate), from the Brand Kit's personas. The Engagement Planning Agent calls it too.`,
    start: "Plan the segments", placeholder: "Any focus or constraint? e.g. “prioritise ER physicians”. Leave empty to start from the latest engagement plan.",
    suggestions: ["Prioritise the treaters", "Why is this segment low priority?", "Add caregivers"],
  },
  "channel-planner": {
    id: "channel-planner", name: "Channel Mix Agent", icon: "megaphone", steps: ["approach"],
    blurb: (b) => `Picks the lead message and the channel mix for each of ${b}'s focus segments, using the channel playbook, the brand's channel mix and the compliance claim check. The Engagement Planning Agent calls it too.`,
    start: "Plan the channels", placeholder: "Any constraint? e.g. “no field force for patients”, “digital-first”. Leave empty to start from the latest segments.",
    suggestions: ["Digital-first, field on signal only", "Why this channel for Treaters?", "Drop paid social"],
  },
};

const STAGE_NAME: Record<string, string> = { aware: "Aware", interested: "Interested", trial: "Trial", adopt: "Adopt", advocate: "Advocate" };
const STAGES = Object.keys(STAGE_NAME);
const stage = (s: unknown) => STAGE_NAME[txt(s).toLowerCase()] ?? txt(s);

function errText(e: unknown): string {
  const s = String(e);
  const i = s.indexOf("{");
  if (i >= 0) { try { const d = JSON.parse(s.slice(i)).detail; if (typeof d === "string") return d; } catch { /* not JSON */ } }
  return s;
}

function summary(id: string, o: Any): string {
  switch (id) {
    case "objectives": return `${arr(o.objectives).length} objectives`;
    case "focus": return arr(o.segments).map((s) => `${txt(s.persona)} (${stage(s.from_stage)} → ${stage(s.to_stage)})`).slice(0, 3).join(", ");
    case "approach": return arr(o.mix).filter((m) => m.weight === "lead").map((m) => txt(m.channel)).join(", ");
    case "portfolio": return `${arr(o.campaigns).length} campaigns`;
    default: return "";
  }
}

export function PlanningAgent({ agentId, brands, activeBrand, recordId }: { agentId: string; brands: BrandSummary[]; activeBrand: string | null; recordId?: string }) {
  const cfg = PLANNING_AGENTS[agentId];
  const brand = activeBrand ?? brands[0]?.brand ?? null;
  const base = `#/v3/agent/${agentId}`;
  const [rec, setRec] = useState<PARecord | null>(null);
  const [records, setRecords] = useState<{ id: string; title: string; approved: number; of: number }[]>([]);
  const [latest, setLatest] = useState<Record<string, { from: { title: string; agent: string } }>>({});
  const [files, setFiles] = useState<File[]>([]);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState("");
  const [tab, setTab] = useState(cfg.steps[0]);
  const [showReasoning, setShowReasoning] = useState(false);

  const refreshList = useCallback(() => {
    if (brand) paList(agentId, brand).then((r) => setRecords(r.records)).catch(() => setRecords([]));
    if (brand) paLatest(brand).then(setLatest).catch(() => setLatest({}));
  }, [brand, agentId]);
  useEffect(refreshList, [refreshList]);
  useEffect(() => {
    if (!recordId) { setRec(null); return; }
    if (rec?.id !== recordId) paGet(agentId, recordId).then(setRec).catch((e) => setError(errText(e)));
  }, [recordId]);  // eslint-disable-line react-hooks/exhaustive-deps

  const call = async (label: string, fn: () => Promise<PARecord>): Promise<PARecord | null> => {
    setBusy(label); setError(null);
    try { const r = await fn(); setRec(r); return r; }
    catch (e) { setError(errText(e)); return null; }
    finally { setBusy(null); }
  };

  const start = async () => {
    if (!brand) return;
    const r = await call("Creating…", () => paCreate(agentId, brand));
    if (!r) return;
    window.location.hash = `${base}/${r.id}`;
    setBusy("Reading the brand plan and Brand Kit…");
    try { await uploadAgentIntake(agentId, r.id, files, notes); } catch (e) { setError(errText(e)); setBusy(null); return; }
    await call("Reading the brand plan and Brand Kit…", () => paAck(agentId, r.id));
    refreshList();
  };

  const steps = rec?.steps ?? {};
  const current = cfg.steps.findIndex((s) => steps[s]?.status !== "approved");
  const allApproved = rec ? current === -1 : false;
  const cur = current >= 0 ? cfg.steps[current] : null;
  const curStep = cur ? steps[cur] : undefined;

  const runStep = async (step: string, fb?: string, force = false): Promise<PARecord | null> => {
    if (!rec) return null;
    const m = STEP_META[step];
    const r = await call(`${m.by ? `${m.by} · ` : ""}${m.full}${fb ? " (revising)" : ""}…`, () => paRun(agentId, rec.id, step, fb, force));
    if (r) { setTab(step); setFeedback(""); refreshList(); }
    return r;
  };
  const runAll = async (from: PARecord) => {
    let r: PARecord | null = from;
    for (const s of cfg.steps) {
      if (!r) return;
      if (r.steps[s]?.status === "approved") continue;
      r = await runStep(s, undefined, true);
    }
  };
  const approveAndContinue = async () => {
    if (!rec || !cur) return;
    const r = await call("Approving…", () => paApprove(agentId, rec.id, cur));
    if (r && current + 1 < cfg.steps.length) await runStep(cfg.steps[current + 1]);
  };
  const doAction = async (a: PAAction, r: PARecord) => {
    if (!a) return;
    if (a.type === "run") await runStep(a.step, a.feedback, Boolean(a.force));
    else if (a.type === "run_all") await runAll(r);
  };
  const send = async (message: string) => {
    if (!rec) return;
    setBusy("Reading your message…"); setError(null);
    try {
      const res = await paChat(agentId, rec.id, message);
      setRec(res.record); setBusy(null);
      await doAction(res.action, res.record);
    } catch (e) { setError(errText(e)); setBusy(null); }
  };
  const save = () => rec && call("Saving to Campaigns & Journeys…", () => paPublish(agentId, rec.id));

  const entries: ReasonEntry[] = [];
  if (rec?.ack) entries.push({ id: "ack", title: "Reading the brand plan and Brand Kit", status: "done", lines: [rec.ack.understood ?? "", ...(rec.ack.approach ?? [])].filter(Boolean) });
  cfg.steps.forEach((s) => { const st = steps[s]; if (st) entries.push({ id: s, title: `${STEP_META[s].full}${STEP_META[s].by ? ` (${STEP_META[s].by})` : ""}`, status: "done", lines: st.reasoning ?? [] }); });
  if (busy) entries.push({ id: "busy", title: busy, status: "running", lines: [] });

  if (!brand) return <p className="v3-empty">Add a brand first.</p>;
  if (!cfg) return <p className="v3-empty">Unknown agent.</p>;
  const shown = cfg.steps.filter((s) => steps[s]);
  const out = obj(steps[tab]?.output);
  const isPlan = agentId === "engagement-planner-2";
  const startsFrom = [
    ...(cfg.steps.includes("objectives") ? [] : latest.objectives ? [`Objectives from “${latest.objectives.from.title}”`] : ["Objectives from the brand plan's KPIs"]),
    ...(agentId === "channel-planner" ? [latest.focus ? `Segments from “${latest.focus.from.title}”` : "No segments yet — run the Segmentation Planner Agent first"] : []),
  ];

  return (
    <div className="v3-ws v3-cc v3-ep2 v3-pa">
      <div className="v3-ws-top">
        <span className="v3-ep-title">{rec ? rec.title : `${cfg.name} — ${brand}`}</span>
        {rec && <span className="v3-ws-save">v{rec.version}{rec.auto ? " · running without stopping" : ""}</span>}
        <span className="v3-ws-top-actions">
          {records.length > 0 && (
            <select className="v3-ep-select" value={rec?.id ?? ""} onChange={(e) => { window.location.hash = e.target.value ? `${base}/${e.target.value}` : base; }}>
              <option value="">+ New</option>
              {records.map((p) => <option key={p.id} value={p.id}>{p.title} ({p.approved}/{p.of})</option>)}
            </select>
          )}
          {isPlan && steps.portfolio?.status === "approved" && (
            <button type="button" className="v3-cc-btn primary" disabled={!!busy} onClick={save}>{rec?.published ? "Save again" : "Save plan"}</button>
          )}
          <ReasoningButton live={Boolean(busy)} onClick={() => setShowReasoning((v) => !v)} />
        </span>
      </div>

      <div className="v3-ws-body">
        <aside className="v3-ws-inputs v3-pa-aside">
          <div className="v3-ws-scroll">
            <div className="v3-ws-head">
              <span className="v3-app-icon lg"><Icon name={cfg.icon} size={20} /></span>
              <div className="v3-ws-head-text">
                <h1>{cfg.name}</h1>
                <p>{cfg.blurb(brand)}</p>
              </div>
            </div>

            {cfg.steps.length > 1 && (
              <ol className="v3-cc-stepper" aria-label="Progress">
                {cfg.steps.map((s, i) => {
                  const st = steps[s]?.status;
                  return (
                    <li key={s} className={st === "approved" ? "done" : rec?.ack && i === current ? "active" : ""}>
                      <span>{st === "approved" ? <Icon name="check" size={9} /> : i + 1}</span>{STEP_META[s].name}
                    </li>
                  );
                })}
              </ol>
            )}

            {!rec && (
              <>
                {startsFrom.length > 0 && <div className="v3-pa-from">{startsFrom.map((x) => <span key={x}><Icon name="link" size={11} />{x}</span>)}</div>}
                <ReadyIntake brand={brand} startLabel={cfg.start} busy={!!busy} busyLabel={busy} onStart={start}
                  files={files} setFiles={setFiles} notes={notes} setNotes={setNotes} placeholder={cfg.placeholder} />
              </>
            )}

            {rec && (
              <div className="v3-ak-progress">
                {cfg.steps.map((s, i) => steps[s]?.status === "approved" && (
                  <button key={s} type="button" className="v3-ak-row done v3-ep2-row" onClick={() => setTab(s)}>
                    <span className="v3-ak-dot"><Icon name="check" size={9} /></span><b>{cfg.steps.length > 1 ? `${i + 1} · ` : ""}{STEP_META[s].full}</b>
                    <small>{STEP_META[s].by && isPlan ? `${STEP_META[s].by} · ` : ""}{summary(s, obj(steps[s].output))}</small>
                  </button>
                ))}

                {!Object.keys(steps).length && (
                  rec.ack ? <AckCard ack={rec.ack} onConfirm={() => runStep(cfg.steps[0])} onEdit={() => { window.location.hash = base; }} />
                    : !busy && <button type="button" className="v3-cc-btn primary wide" onClick={() => call("Reading the brand plan and Brand Kit…", () => paAck(agentId, rec.id))}>Read the brand plan</button>
                )}

                {cur && (curStep || busy) && (
                  <div className="v3-ak-row current">
                    <div className="v3-ak-row-head">
                      <span className="v3-ak-dot">{busy ? <span className="v3-cc-spinner small" /> : current + 1}</span>
                      <b>{STEP_META[cur].full}</b>
                      {STEP_META[cur].by && isPlan && <small className="v3-pa-by">{STEP_META[cur].by}</small>}
                      {curStep?.status === "stale" && <small className="v3-ep2-stale">An earlier step changed — redo this one</small>}
                    </div>
                    {busy ? <small className="v3-ep-busy-line">{busy}</small> : curStep && (
                      <div className="v3-ep-sub">
                        <em>Review the draft on the right</em>
                        <textarea className="v3-glass-text" rows={2} value={feedback} onChange={(e) => setFeedback(e.target.value)}
                          placeholder="Anything to change in this step?" />
                        <div className="v3-ep2-actions">
                          <button type="button" className="v3-cc-btn primary" disabled={curStep.status === "stale"} onClick={approveAndContinue}>
                            {current + 1 < cfg.steps.length ? "Approve & continue" : "Approve"}
                          </button>
                          <button type="button" className="v3-cc-btn" onClick={() => runStep(cur, feedback.trim() || "Redo this step.")}>
                            {feedback.trim() ? "Redo with my changes" : "Redo"}
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )}
                {cur && !curStep && !busy && Object.keys(steps).length > 0 && (
                  <button type="button" className="v3-cc-btn primary wide" onClick={() => runStep(cur)}>Run · {STEP_META[cur].full}</button>
                )}

                {allApproved && (
                  <div className="v3-ak-done">
                    {isPlan ? (<>
                      <b>The engagement plan is ready.</b>
                      {rec.published
                        ? <span className="v3-ep-saved"><Icon name="check" size={12} /> Saved to <a href="#/v3/brands">Campaigns & Journeys</a> with {Object.keys(rec.published.campaigns ?? {}).length} campaign(s). Each opens the Campaign Planning Agent.</span>
                        : <span className="v3-muted">Save it to put the plan and its campaigns in Campaigns & Journeys and Live simulation.</span>}
                      <button type="button" className="v3-cc-btn primary" disabled={!!busy} onClick={save}>{rec.published ? "Save again" : "Save plan & campaigns"}</button>
                    </>) : agentId === "brand-persona-builder" ? (<>
                      <b>Segments approved.</b>
                      <span className="v3-muted">The Channel Mix Agent and the next engagement plan start from these.</span>
                      <a className="v3-cc-btn primary" href="#/v3/agent/channel-planner">Plan the channels →</a>
                    </>) : (<>
                      <b>Channel approach approved.</b>
                      <span className="v3-muted">The next engagement plan's portfolio starts from it.</span>
                      <a className="v3-cc-btn primary" href="#/v3/agent/engagement-planner-2">Build the engagement plan →</a>
                    </>)}
                  </div>
                )}
              </div>
            )}
            {error && <p className="v3-cc-banner error">{error}</p>}
          </div>
          {rec && (
            <div className="v3-pa-chat">
              <AgentChat messages={rec.chat ?? []} onSend={send} busy={!!busy} suggestions={cfg.suggestions} />
            </div>
          )}
        </aside>

        <section className="v3-ws-output v3-ep2-out">
          {busy && rec && <p className="v3-ak-canvas-note"><span className="v3-cc-spinner small" /> {busy}</p>}
          {!shown.length ? (
            <div className="v3-ws-empty">
              <Icon name={cfg.icon} size={28} />
              <b>{isPlan ? "The engagement plan builds here, step by step" : `The ${cfg.name.toLowerCase()}'s work shows here`}</b>
              <span>{isPlan ? "Objectives → where to focus → message & channels → campaign portfolio. It reuses the Brand Kit; nothing is rebuilt." : "It reuses the Brand Kit as given and only decides priorities."}</span>
            </div>
          ) : (
            <>
              {shown.length > 1 && (
                <div className="v3-av-tabs" role="tablist">
                  {shown.map((s) => (
                    <button key={s} type="button" role="tab" aria-selected={tab === s} className={tab === s ? "active" : ""} onClick={() => setTab(s)}>
                      {cfg.steps.indexOf(s) + 1} · {STEP_META[s].name}{steps[s].status !== "approved" && <em className={`v3-ep2-tag ${steps[s].status}`}>{steps[s].status}</em>}
                    </button>
                  ))}
                </div>
              )}
              {!steps[tab] ? <p className="v3-muted">Pick a step above.</p>
                : tab === "objectives" ? <ObjectivesView o={out} />
                : tab === "focus" ? <FocusView o={out} by={isPlan ? "Segmentation Planner Agent" : undefined} />
                : tab === "approach" ? <ApproachView o={out} by={isPlan ? "Channel Mix Agent" : undefined} />
                : <PortfolioView o={out} period={rec?.period} />}
            </>
          )}
        </section>
        {showReasoning && <ReasoningPanel entries={entries} live={Boolean(busy)} onClose={() => setShowReasoning(false)} />}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ views */

const Kit = ({ children, href = "#/v3/iq/kits" }: { children: React.ReactNode; href?: string }) => (
  <a className="v3-pa-kit" href={href} title="Reused from the Brand Kit"><Icon name="document" size={10} />{children}</a>
);

function Notes({ o }: { o: Any }) {
  const qs = arr(o.questions), kn = arr(o.kit_notes);
  if (!qs.length && !kn.length) return null;
  return (
    <div className="v3-pa-notes">
      {qs.length > 0 && <div><b><Icon name="alertTriangle" size={12} /> Questions (not invented)</b>{qs.map((q, i) => <p key={i}>{txt(q.question)}{q.why ? <small> — {txt(q.why)}</small> : null}</p>)}</div>}
      {kn.length > 0 && <div><b><Icon name="document" size={12} /> Notes for the Brand Kit</b>{kn.map((q, i) => <p key={i}>{txt(q.what)}: {txt(q.note)} <a href="#/v3/iq/kits">Fix in Brand IQ</a></p>)}</div>}
    </div>
  );
}

function ObjectivesView({ o }: { o: Any }) {
  return (
    <div className="v3-ep2-view">
      <p className="v3-ep2-eyebrow">Step 1 · Objectives for the period</p>
      <h2 className="v3-ep2-h">What this plan must achieve</h2>
      <div className="v3-pa-objs">
        {arr(o.objectives).map((x) => (
          <article key={txt(x.id)}>
            <header><span className="v3-pa-id">{txt(x.id)}</span><b>{txt(x.objective)}</b></header>
            <div className="v3-pa-measure"><Icon name="target" size={13} /><span>{txt(x.measure)}</span><b>{txt(x.baseline) || "—"} → {txt(x.target) || "—"}</b>{txt(x.by) && <small>by {txt(x.by)}</small>}</div>
            {txt(x.gap) && <p><Icon name="alertTriangle" size={12} /> {txt(x.gap)}</p>}
            <footer>{txt(x.imperative) && <Kit>{txt(x.imperative)}</Kit>}<small>{txt(x.source)}</small></footer>
          </article>
        ))}
      </div>
      <Notes o={o} />
    </div>
  );
}

function Ladder({ segs }: { segs: Any[] }) {
  return (
    <div className="v3-pa-ladder">
      {STAGES.map((s) => (
        <div key={s} className="v3-pa-rung">
          <em>{STAGE_NAME[s]}</em>
          {segs.filter((x) => txt(x.to_stage).toLowerCase() === s).map((x) => (
            <span key={txt(x.id)} className={`v3-pa-move ${txt(x.priority).toLowerCase()}`} title={txt(x.why)}>
              {txt(x.persona)}<small>from {stage(x.from_stage)}</small>
            </span>
          ))}
        </div>
      ))}
    </div>
  );
}

function FocusView({ o, by }: { o: Any; by?: string }) {
  const segs = arr(o.segments);
  return (
    <div className="v3-ep2-view">
      <p className="v3-ep2-eyebrow">{by ? `Step 2 · Where to focus · by the ${by}` : "Where to focus"}</p>
      <h2 className="v3-ep2-h">Who moves, and how far</h2>
      <p className="v3-pa-sub">Placed where each segment must get to this period. Personas come from the Brand Kit as they are. <Kit href="#/v3/iq/personas">Audiences tab</Kit></p>
      <Ladder segs={segs} />
      <div className="v3-pa-segs">
        {segs.map((x) => (
          <article key={txt(x.id)}>
            <header>
              <span className="v3-pa-id">{txt(x.id)}</span><b>{txt(x.persona)}</b>
              <span className={`v3-pa-prio ${txt(x.priority).toLowerCase()}`}>{txt(x.priority)}</span>
            </header>
            <div className="v3-pa-movebar"><span>{stage(x.from_stage)}</span><Icon name="arrowRight" size={13} /><b>{stage(x.to_stage)}</b><small>{txt(x.audience)}</small></div>
            <ul className="v3-iq-bul">
              {txt(x.why) && <li><b>Why</b> {txt(x.why)}</li>}
              {txt(x.barrier) && <li><b>Barrier</b> {txt(x.barrier)}</li>}
              {txt(x.moment) && <li><b>Moment</b> {txt(x.moment)}</li>}
            </ul>
            <footer>
              {arr(x.objective_ids).map((id) => <span key={String(id)} className="v3-pa-id sm">{String(id)}</span>)}
              {x.size !== null && x.size !== undefined && x.size !== "" && <small>{Number.isFinite(Number(x.size)) ? Number(x.size).toLocaleString() : txt(x.size)} · {txt(x.size_source)}</small>}
            </footer>
          </article>
        ))}
      </div>
      {arr(o.deprioritised).length > 0 && (
        <div className="v3-pa-depr"><b>Not in focus this period</b>{arr(o.deprioritised).map((d, i) => <p key={i}><span>{txt(d.persona)}</span> {txt(d.why)}</p>)}</div>
      )}
      <Notes o={o} />
    </div>
  );
}

function ApproachView({ o, by }: { o: Any; by?: string }) {
  return (
    <div className="v3-ep2-view">
      <p className="v3-ep2-eyebrow">{by ? `Step 3 · Message & channels · by the ${by}` : "Message & channel approach"}</p>
      <h2 className="v3-ep2-h">What each segment hears, and where</h2>
      <p className="v3-pa-sub">Messages from the Brand Kit's message matrix; channel jobs from the channel playbook. <Kit href="#/v3/iq/channels">Channels tab</Kit></p>
      <div className="v3-pa-mix">{arr(o.mix).map((m, i) => <span key={i} className={`w-${txt(m.weight)}`}>{txt(m.channel)}<small>{txt(m.weight)}</small></span>)}</div>
      <div className="v3-pa-segs">
        {arr(o.by_segment).map((x, i) => {
          const lm = obj(x.lead_message);
          return (
            <article key={i}>
              <header><span className="v3-pa-id">{txt(x.segment_id)}</span><b>{txt(x.persona)}</b><small className="v3-pa-movetag">{txt(x.move)}</small></header>
              <div className="v3-pa-msg"><Icon name="message" size={13} /><div><Kit href="#/v3/iq/message">{txt(lm.pillar)}</Kit><p>{txt(lm.message)}</p></div></div>
              <ul className="v3-pa-chans">
                {arr(x.channels).map((c, j) => (
                  <li key={j} className={txt(c.weight)}><b>{txt(c.channel)}</b><span>{txt(c.job)}</span><small>{txt(c.weight)}</small></li>
                ))}
              </ul>
              {arr(x.avoid).length > 0 && <div className="v3-pa-avoid"><Icon name="shield" size={12} />{arr(x.avoid).map((a, j) => <span key={j}>Avoid: {txt(a.what)} <small>{txt(a.why)}</small></span>)}</div>}
            </article>
          );
        })}
      </div>
      {arr(o.rules).length > 0 && (<>
        <h3 className="v3-iq-h3">Orchestration rules</h3>
        <ul className="v3-iq-bul">{arr(o.rules).map((r, i) => <li key={i}><b>{txt(r.rule)}</b> {txt(r.why)}</li>)}</ul>
      </>)}
      <Notes o={o} />
    </div>
  );
}

function monthsBetween(start: string, end: string): string[] {
  const out: string[] = [];
  const s = new Date(`${start.slice(0, 7)}-01T00:00:00`), e = new Date(`${end.slice(0, 7)}-01T00:00:00`);
  for (let d = s; d <= e && out.length < 24; d = new Date(d.getFullYear(), d.getMonth() + 1, 1)) out.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`);
  return out;
}

function PortfolioView({ o, period }: { o: Any; period?: { start: string; end: string } }) {
  const camps = arr(o.campaigns);
  const months = period ? monthsBetween(period.start, period.end) : [];
  const idx = (m: string) => Math.max(0, months.indexOf(m.slice(0, 7)));
  return (
    <div className="v3-ep2-view">
      <p className="v3-ep2-eyebrow">Step 4 · Campaign portfolio</p>
      <h2 className="v3-ep2-h">The campaigns that deliver the plan</h2>
      {months.length > 0 && (
        <div className="v3-pa-gantt" style={{ ["--n" as string]: months.length }}>
          <div className="v3-pa-gantt-head"><span />{months.map((m) => <em key={m}>{new Date(`${m}-01T00:00:00`).toLocaleString("en", { month: "short" })}</em>)}</div>
          {camps.map((c) => {
            const a = idx(txt(c.start)), b = Math.max(a, months.indexOf(txt(c.end).slice(0, 7)) >= 0 ? months.indexOf(txt(c.end).slice(0, 7)) : months.length - 1);
            return (
              <div key={txt(c.id)} className="v3-pa-gantt-row">
                <span>{txt(c.name)}</span>
                <i style={{ gridColumn: `${a + 2} / ${b + 3}` }} title={`${txt(c.start)} → ${txt(c.end)}`}>{txt(c.move)}</i>
              </div>
            );
          })}
        </div>
      )}
      <div className="v3-pa-segs">
        {camps.map((c) => (
          <article key={txt(c.id)}>
            <header><span className="v3-pa-id">{txt(c.id)}</span><b>{txt(c.name)}</b><small className="v3-pa-movetag">{txt(c.start)} → {txt(c.end)}</small></header>
            <ul className="v3-iq-bul">
              {txt(c.move) && <li><b>Move</b> {txt(c.move)}</li>}
              {txt(c.message) && <li><b>Message</b> {txt(c.message)}</li>}
              {arr(c.lead_channels).length > 0 && <li><b>Channels</b> {arr(c.lead_channels).map(txt).join(" · ")}</li>}
              {txt(c.moment) && <li><b>Moment</b> {txt(c.moment)}</li>}
              {txt(c.kpi) && <li><b>KPI</b> {txt(c.kpi)}</li>}
            </ul>
            {txt(c.why) && <p className="v3-pa-why">{txt(c.why)}</p>}
            <footer>{[...arr(c.objective_ids), ...arr(c.segment_ids)].map((id) => <span key={String(id)} className="v3-pa-id sm">{String(id)}</span>)}</footer>
          </article>
        ))}
      </div>
      {arr(o.sequencing).length > 0 && (<><h3 className="v3-iq-h3">Sequencing</h3><ul className="v3-iq-bul">{arr(o.sequencing).map((s, i) => <li key={i}>{txt(s)}</li>)}</ul></>)}
      <Notes o={o} />
    </div>
  );
}
