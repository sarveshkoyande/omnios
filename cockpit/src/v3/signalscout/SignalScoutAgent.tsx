import { useEffect, useRef, useState } from "react";
import {
  ackScout, getScout, getScoutSteps, runScoutSkill, startScout, toggleScoutWorklist,
  type AgentAck, type AgentStepDef, type ScoutReadout, type ScoutSkill,
} from "../../api";
import { Icon } from "../../components/Icon";
import type { BrandSummary } from "../../types";
import { AckCard, ReasoningButton, ReasoningPanel, StepProgress, type ReasonEntry, type SkillStatus } from "../agentkit/AgentKit";
import "../campaignplanner/campaignPlanner.css";
import "../brandiq/brandiq.css";
import "./signalscout.css";

/** Signal Scout agent (rebuilt from the Signal Scout pilot UI): what changed in the market, and what
 *  should the brand team do about it. Four agent steps (strategy/signal_scout.STEPS) over nine skills:
 *  you give a focus (or none), the agent acknowledges what Brand IQ gives it and waits for your OK, then
 *  a fresh readout is built step by step. The pilot's three views are the main canvas; Live reasoning
 *  is a slide-in panel. */

type Any = Record<string, unknown>;
type Phase = "intake" | "reading" | "ack" | "running" | "done";
type View = "synthesis" | "market" | "competitive";
const txt = (v: unknown) => (v === null || v === undefined ? "" : String(v));
const arr = (v: unknown) => (Array.isArray(v) ? (v as Any[]) : []);
const lvl = (v: unknown) => txt(v).toLowerCase().replace(/[^a-z]+/g, "-");

export function SignalScoutAgent({ brands, activeBrand }: { brands: BrandSummary[]; activeBrand: string | null }) {
  const brand = activeBrand ?? brands[0]?.brand ?? null;
  const [steps, setSteps] = useState<AgentStepDef[]>([]);
  const [skills, setSkills] = useState<ScoutSkill[]>([]);
  const [phase, setPhase] = useState<Phase>("intake");
  const [focus, setFocus] = useState("");
  const [ack, setAck] = useState<AgentAck | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [readout, setReadout] = useState<ScoutReadout | null>(null);
  const [previous, setPrevious] = useState<ScoutReadout | null>(null);
  const [status, setStatus] = useState<Record<string, SkillStatus>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [currentStep, setCurrentStep] = useState(0);
  const [view, setView] = useState<View>("synthesis");
  const [showReasoning, setShowReasoning] = useState(false);
  const stop = useRef(false);

  useEffect(() => { getScoutSteps().then((r) => { setSteps(r.steps); setSkills(r.skills); }).catch(() => undefined); }, []);
  useEffect(() => {
    setPhase("intake"); setFocus(""); setAck(null); setError(null); setReadout(null); setPrevious(null);
    setStatus({}); setErrors({}); setCurrentStep(0); setShowReasoning(false);
    if (!brand) return;
    getScout(brand).then((r) => {
      setPrevious(r.previous);
      if (r.current && Object.keys(r.current.sections ?? {}).length) setReadout(r.current);
    }).catch(() => undefined);
  }, [brand]);

  const skillNames = Object.fromEntries(skills.map((s) => [s.id, s.name]));
  const viewOf = Object.fromEntries(skills.map((s) => [s.id, s.view])) as Record<string, View>;

  const read = async () => {
    if (!brand) return;
    setPhase("reading"); setError(null);
    try {
      setAck(await ackScout(brand, focus));
      setPhase("ack");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setPhase("intake");
    }
  };

  const runSkill = async (id: string) => {
    if (!brand) return;
    setStatus((s) => ({ ...s, [id]: "running" }));
    setView(viewOf[id] ?? "synthesis");
    try {
      const res = await runScoutSkill(brand, id);
      setReadout(res.readout);
      setStatus((s) => ({ ...s, [id]: "done" }));
    } catch (e) {
      setErrors((x) => ({ ...x, [id]: e instanceof Error ? e.message : String(e) }));
      setStatus((s) => ({ ...s, [id]: "error" }));
    }
  };

  const build = async () => {
    if (!brand) return;
    setPhase("running"); setStatus({}); setErrors({}); setCurrentStep(0); stop.current = false;
    try {
      const r = await startScout(brand, focus);
      setReadout(r.current); setPrevious(r.previous);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setPhase("ack");
      return;
    }
    for (let i = 0; i < steps.length; i++) {
      if (stop.current) break;
      setCurrentStep(i);
      for (const k of steps[i].skills) {
        if (stop.current) break;
        await runSkill(k);
      }
    }
    setCurrentStep(steps.length);
    setPhase("done");
    setView("synthesis");
  };

  const toggleWork = async (i: number) => {
    if (!brand) return;
    try { setReadout(await toggleScoutWorklist(brand, i)); } catch { /* keep the board as it was */ }
  };

  const running = phase === "running";
  const sec = readout?.sections ?? {};
  const entries: ReasonEntry[] = [
    ...(ack ? [{ id: "ack", title: "Understanding the brief", status: "done" as SkillStatus,
      lines: [ack.understood ?? "", ...(ack.approach ?? [])].filter(Boolean) }] : []),
    ...skills.filter((s) => (status[s.id] ?? "idle") !== "idle" || (phase === "intake" && readout?.reasoning?.[s.id])).map((s) => ({
      id: s.id, title: s.name, status: (status[s.id] ?? "done") as SkillStatus, lines: readout?.reasoning?.[s.id] ?? [], error: errors[s.id],
    })),
  ];
  const stepIdx = phase === "intake" || phase === "reading" || phase === "ack" ? 0 : currentStep;

  if (!brand) return <p className="v3-empty">Add a brand first: Signal Scout watches one brand's market.</p>;

  return (
    <div className="v3-ws v3-cc v3-biq v3-ss">
      <div className="v3-ws-top">
        <span className="v3-ep-title">Signal Scout — {brand} · US</span>
        {readout && <span className="v3-ws-save">Readout {readout.started}{previous ? ` · previous ${previous.started}` : " · first readout"}</span>}
        <span className="v3-ws-top-actions"><ReasoningButton live={running} onClick={() => setShowReasoning((v) => !v)} /></span>
      </div>
      <div className="v3-ws-body">
        <aside className="v3-ws-inputs">
          <div className="v3-ws-scroll">
            <div className="v3-ws-head">
              <span className="v3-app-icon lg"><Icon name="radar" size={20} /></span>
              <div className="v3-ws-head-text">
                <h1>Signal Scout</h1>
                <p>What changed in {brand}'s market, and what should the team do? Keeps only the signals that matter and turns them into actions.</p>
              </div>
            </div>

            <ol className="v3-cc-stepper" aria-label="Signal Scout progress">
              {steps.map((s, i) => (
                <li key={s.id} className={i < stepIdx || phase === "done" ? "done" : i === stepIdx ? "active" : ""}>
                  <span>{i < stepIdx || phase === "done" ? <Icon name="check" size={9} /> : i + 1}</span>{s.name}
                </li>
              ))}
            </ol>

            {(phase === "intake" || phase === "reading") && (
              <section className="v3-cc-intake">
                <div className="v3-cc-intake-head">
                  <b>Scan brief</b>
                  <span>Signal Scout reads {brand}'s Brand IQ. Tell it what to look for, or leave it empty for an open scan.</span>
                </div>
                <label className="v3-cc-intake-label" htmlFor="ss-focus">What should the scan answer?</label>
                <textarea id="ss-focus" rows={6} value={focus} disabled={phase === "reading"} onChange={(e) => setFocus(e.target.value)}
                  placeholder="e.g. Is there whitespace against the market leader? What are competitors saying to cardiologists? What changed since the last congress?" />
                <span className="v3-cc-hint">US market only. Channel activity is estimated from public knowledge, not observed media spend.</span>
                {readout && <span className="v3-cc-hint">The last readout ({readout.started}) is on the right and is kept so the new one can say what changed.</span>}
                <button type="button" className="v3-cc-btn primary wide" disabled={phase === "reading"} onClick={read}>
                  {phase === "reading" ? <><span className="v3-cc-spinner small" /> Reading your brief…</> : "Start scan"}
                </button>
              </section>
            )}

            {phase === "ack" && ack && <AckCard ack={ack} onConfirm={build} onEdit={() => setPhase("intake")} />}

            {(phase === "running" || phase === "done") && (
              <StepProgress steps={steps} skillNames={skillNames} status={status} currentStep={currentStep} done={phase === "done"} />
            )}
            {running && <button type="button" className="v3-cc-btn wide v3-biq-actions" onClick={() => { stop.current = true; }}>Stop after this part</button>}
            {phase === "done" && (
              <div className="v3-ak-done">
                <b>Readout ready.</b>
                <span className="v3-muted">Review the signals and add the actions you'll pursue to the worklist.</span>
                <button type="button" className="v3-cc-btn" onClick={() => setShowReasoning(true)}>See the reasoning</button>
                <button type="button" className="v3-cc-btn" onClick={() => { setPhase("intake"); setAck(null); }}>New scan</button>
              </div>
            )}
            {error && <p className="v3-cc-banner error">{error}</p>}
          </div>
        </aside>

        <section className="v3-ws-output v3-biq-canvas">
          <div className="v3-av-tabs" role="tablist">
            {([["synthesis", "Synthesis & action"], ["market", "Market & treatment"], ["competitive", "Competitive landscape"]] as [View, string][]).map(([id, label]) => (
              <button key={id} type="button" role="tab" aria-selected={view === id} className={view === id ? "active" : ""} onClick={() => setView(id)}>{label}</button>
            ))}
          </div>
          {running && <p className="v3-ak-canvas-note"><span className="v3-cc-spinner small" /> Building — {steps[currentStep]?.name ?? ""}</p>}
          {view === "synthesis" ? <Synthesis sec={sec} worklist={readout?.worklist ?? []} toggle={toggleWork} />
            : view === "market" ? <Market sec={sec} /> : <Competitive sec={sec} />}
        </section>
        {showReasoning && <ReasoningPanel entries={entries} live={running} onClose={() => setShowReasoning(false)} />}
      </div>
    </div>
  );
}

function Pending({ what }: { what: string }) {
  return <p className="v3-ss-pending">{what} appears here once its step has run.</p>;
}

function Basis({ v }: { v: unknown }) {
  return v ? <small className="v3-ss-basis">{txt(v)}</small> : null;
}

function Synthesis({ sec, worklist, toggle }: { sec: Record<string, Any>; worklist: number[]; toggle: (i: number) => void }) {
  const syn = sec.synthesis, act = sec.actions, his = sec.history;
  return (
    <div className="v3-ss-view">
      <p className="v3-ss-eyebrow">Synthesis & action</p>
      <h2 className="v3-ss-h">What changed — what should the team do?</h2>
      {!syn ? <Pending what="The synthesis" /> : (
        <>
          <div className="v3-ss-exec">
            <span className="v3-ss-eyebrow">✦ Executive intelligence</span>
            <h3>{txt(syn.headline)}</h3>
            <p>{txt(syn.summary)}</p>
            <div className="v3-ss-pills"><span>Confidence · {txt(syn.confidence)}</span><span>{txt(syn.converging)} signals converge</span></div>
          </div>
          <h3 className="v3-ss-sec"><em>01</em> Signals that matter</h3>
          <div className="v3-ss-grid">
            {arr(syn.signals).map((s) => (
              <div key={txt(s.id)} className="v3-ss-card">
                <div className="v3-ss-card-top"><span>Signal {txt(s.id)} · {txt(s.category)}</span><span className={`v3-ss-badge ${lvl(s.materiality)}`}>{txt(s.materiality)} materiality</span></div>
                <b>{txt(s.title)}</b>
                <p>{txt(s.detail)}</p>
                <small>Source: {txt(s.source)} · Confidence: {txt(s.confidence)}</small>
              </div>
            ))}
          </div>
        </>
      )}
      <h3 className="v3-ss-sec"><em>02</em> Recommended team actions</h3>
      {!act ? <Pending what="The action board" /> : (
        <div className="v3-ss-grid">
          {arr(act.actions).map((a, i) => {
            const on = worklist.includes(i);
            return (
              <div key={i} className="v3-ss-card">
                <div className="v3-ss-card-top"><span className="v3-ss-fn"><i>{txt(a.function).charAt(0)}</i>{txt(a.function)} · {txt(a.area)}</span></div>
                <b>{txt(a.title)}</b>
                <p>{txt(a.detail)}</p>
                <small>Linked signals: {arr(a.linked_signals).map(String).join(" + ")} · Priority: {txt(a.priority)} · {txt(a.timing)}</small>
                <button type="button" className={`v3-cc-btn ${on ? "primary" : ""}`} onClick={() => toggle(i)}>{on ? "On worklist ✓" : "Add to worklist"}</button>
              </div>
            );
          })}
        </div>
      )}
      <h3 className="v3-ss-sec"><em>03</em> What changed since the last readout</h3>
      {!his ? <Pending what="Signal history" /> : (
        <div className="v3-ss-hist">
          <div className="v3-ss-hist-row"><div><em>Previous</em><p>{txt(his.previous_summary) || "No previous readout — this is the baseline."}</p></div><span>→</span><div><em>Current</em><p>{txt(his.current_summary)}</p></div></div>
          {arr(his.changes).map((c, i) => (
            <div key={i} className="v3-ss-change"><span className={`v3-ss-badge ${lvl(c.status)}`}>{txt(c.status)}</span><b>{txt(c.signal)}</b><span>{txt(c.note)}</span></div>
          ))}
        </div>
      )}
      {act && (
        <div className="v3-ss-decide">
          <b>Human decision point</b>
          <span>Signal Scout surfaces and connects evidence; the brand team decides which actions to pursue. {worklist.length} on the worklist.</span>
        </div>
      )}
    </div>
  );
}

function Market({ sec }: { sec: Record<string, Any> }) {
  const m = sec.market, c = sec.clinical;
  return (
    <div className="v3-ss-view">
      <p className="v3-ss-eyebrow">Market and treatment landscape</p>
      <h2 className="v3-ss-h">External context for the brand</h2>
      {!m ? <Pending what="The market landscape" /> : (
        <>
          <div className="v3-ss-kpis">
            {arr(m.indicators).map((k, i) => <div key={i}><b>{txt(k.value)}</b><span>{txt(k.label)}</span><Basis v={k.source || k.basis} /></div>)}
          </div>
          {Boolean(m.insight) && <div className="v3-ss-insight"><em>Market insight</em><p>{txt(m.insight)}</p></div>}
          <h3 className="v3-ss-sec">Evidence records</h3>
          <div className="v3-ss-records">
            {arr(m.evidence_records).map((r, i) => (
              <div key={i}><span className="v3-ss-tag">{txt(r.type)}</span><div><b>{txt(r.title)}</b><p>{txt(r.detail)}</p><Basis v={r.source} /></div><em>{txt(r.status)}</em></div>
            ))}
          </div>
        </>
      )}
      <h3 className="v3-ss-sec">Key clinical evidence</h3>
      {!c ? <Pending what="Clinical evidence" /> : arr(c.studies).map((s, i) => (
        <div key={i} className="v3-ss-study">
          <div className="v3-ss-card-top"><b>{txt(s.name)}</b><span className={`v3-ss-badge ${lvl(s.relevance)}`}>{txt(s.relevance)} relevance</span></div>
          <small>{[s.phase, s.publication].filter(Boolean).map(txt).join(" · ")}</small>
          <div className="v3-ss-kpis">{arr(s.metrics).map((x, j) => <div key={j}><b>{txt(x.value)}</b><span>{txt(x.label)}</span></div>)}</div>
          <Basis v={s.source} />
        </div>
      ))}
    </div>
  );
}

function Competitive({ sec }: { sec: Record<string, Any> }) {
  const cs = sec.competitive_set, pos = sec.positioning, msg = sec.messages, ch = sec.channels;
  return (
    <div className="v3-ss-view">
      <p className="v3-ss-eyebrow">Competitive landscape</p>
      <h2 className="v3-ss-h">Who matters → how they compete → what they say → where they're active</h2>
      <h3 className="v3-ss-sec"><em>01</em> Competitive set</h3>
      {!cs ? <Pending what="The competitive set" /> : (
        <div className="v3-ss-grid">
          {arr(cs.entities).map((e, i) => (
            <div key={i} className="v3-ss-card">
              <div className="v3-ss-card-top"><b>{txt(e.name)}</b><span className="v3-ss-tag">{txt(e.type)}</span></div>
              <small>{[e.generic, e.company].filter(Boolean).map(txt).join(" · ")}</small>
              <p>{[e.mechanism, e.route_dosing].filter(Boolean).map(txt).join(" · ")}</p>
              <p><b>{txt(e.positioning)}</b></p>
              <dl className="v3-ss-dl">
                {Boolean((e.key_metric as Any)?.value) && <><dt>{txt((e.key_metric as Any).label)}</dt><dd>{txt((e.key_metric as Any).value)}</dd></>}
                {Boolean(e.outcomes) && <><dt>Outcomes</dt><dd>{txt(e.outcomes)}</dd></>}
                {Boolean(e.activity) && <><dt>Activity</dt><dd>{txt(e.activity)}</dd></>}
              </dl>
              <div className="v3-ss-pills">{arr(e.tags).map((t, j) => <span key={j}>{String(t)}</span>)}</div>
              <Basis v={e.basis} />
            </div>
          ))}
        </div>
      )}
      <h3 className="v3-ss-sec"><em>02</em> Positioning & evidence</h3>
      {!pos ? <Pending what="The positioning comparison" /> : (
        <div className="v3-iq-tablewrap"><table className="v3-iq-table">
          <thead><tr><th>Dimension</th>{arr(pos.columns).map((c, i) => <th key={i}>{String(c)}</th>)}</tr></thead>
          <tbody>{arr(pos.rows).map((r, i) => <tr key={i}><td><b>{txt(r.dimension)}</b></td>{arr(r.values).map((v, j) => <td key={j}>{String(v)}</td>)}</tr>)}</tbody>
        </table></div>
      )}
      <h3 className="v3-ss-sec"><em>03</em> Message territory</h3>
      {!msg ? <Pending what="The message territory" /> : (
        <div className="v3-ss-grid">
          {arr(msg.themes).map((t, i) => (
            <div key={i} className="v3-ss-card">
              <div className="v3-ss-card-top"><b>{txt(t.theme)}</b><span className={`v3-ss-badge ${lvl(t.status)}`}>{txt(t.status)}</span></div>
              <p>{txt(t.detail)}</p>
              {arr(t.owners).length > 0 && <small>Observed owners: {arr(t.owners).map(String).join(" · ")}</small>}
              {Boolean(t.potential) && <small>Potential territory: {txt(t.potential)}</small>}
            </div>
          ))}
        </div>
      )}
      <h3 className="v3-ss-sec"><em>04</em> Channel activity</h3>
      {!ch ? <Pending what="Channel activity" /> : (
        <>
          <div className="v3-ss-grid">
            {arr(ch.entities).map((e, i) => (
              <div key={i} className="v3-ss-card">
                <b>{txt(e.name)}</b>
                {arr(e.channels).map((c, j) => <div key={j} className="v3-ss-chan"><span>{txt(c.channel)}</span><span className={`v3-ss-badge ${lvl(c.level)}`}>{txt(c.level)}</span></div>)}
              </div>
            ))}
          </div>
          {Boolean(ch.pattern) && <div className="v3-ss-insight"><em>Pattern</em><p>{txt(ch.pattern)}</p></div>}
          <p className="v3-ss-pending">Activity levels are the agent's estimate from public knowledge, not observed media spend.</p>
        </>
      )}
    </div>
  );
}
