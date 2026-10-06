import { useEffect, useRef, useState } from "react";
import {
  ackAgentForm, checkArtifact, editArtifact, findArtifact, generateArtifact, getAgentForm, getBrandTree, uploadAgentIntake,
  type AgentAck, type GuidelineCheck, type V3Artifact,
} from "../../api";
import { Icon } from "../../components/Icon";
import { FlowEditorChat } from "../../components/flowplanner/FlowEditorChat";
import type { BrandSummary, BrandTree } from "../../types";
import { AckCard, GlassDrop, ReasoningButton, ReasoningPanel, type ReasonEntry, type SkillStatus } from "../agentkit/AgentKit";
import { ArtifactViewer } from "../ArtifactViewer";
import "../campaignplanner/campaignPlanner.css";
import "../agentkit/agentkit.css";
import "./flowagent.css";

/** The Flow Agent: a campaign's channel-by-channel journey, as four agent steps.
 *  1 Understand the campaign -- pick the campaign, drop documents, type notes; the agent acknowledges
 *    what it has and proposes the inputs only you can give (each with its source), and waits for your OK.
 *  2 Settle the inputs -- the framework's inputs (derived, from the campaign plan, from your OK).
 *  3 Build the flow -- the versioned flow artifact (strategy/v3_artifacts.py) with its journey diagram.
 *  4 Check guidelines -- compliance check against the brand's guardrails.
 *  The flow is the main canvas; Live reasoning is a slide-in panel; "Edit the flow" edits it by chat. */

const AGENT = "flow-planner";
const STEPS = ["Understand the campaign", "Settle the inputs", "Build the flow", "Check guidelines"];
type Phase = "intake" | "reading" | "ack" | "running" | "done";
type Handoff = { brand: string; planId: number | null; campaignId: number | null };
type Inputs = V3Artifact["inputs"];

export function FlowAgent({ brands, activeBrand, handoff }: { brands: BrandSummary[]; activeBrand: string | null; handoff?: Handoff }) {
  const [brand, setBrand] = useState<string | null>(handoff?.brand ?? activeBrand ?? brands[0]?.brand ?? null);
  const [tree, setTree] = useState<BrandTree | null>(null);
  const [planId, setPlanId] = useState<number | null>(handoff?.planId ?? null);
  const [campaignId, setCampaignId] = useState<number | null>(handoff?.campaignId ?? null);
  const [phase, setPhase] = useState<Phase>("intake");
  const [files, setFiles] = useState<File[]>([]);
  const [notes, setNotes] = useState("");
  const [ack, setAck] = useState<(AgentAck & { answers: { key: string; label?: string; value: string; source: string }[] }) | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<SkillStatus[]>(["idle", "idle", "idle", "idle"]);
  const [current, setCurrent] = useState(0);
  const [settled, setSettled] = useState<{ filled: string[]; missing: string[] } | null>(null);
  const [artifact, setArtifact] = useState<V3Artifact | null>(null);
  const [check, setCheck] = useState<GuidelineCheck | null>(null);
  const [showReasoning, setShowReasoning] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [diagramMarkup, setDiagramMarkup] = useState<string | null>(null);
  const pendingScope = useRef(handoff ?? null);

  useEffect(() => { if (!brand && brands.length) setBrand(activeBrand ?? brands[0].brand); }, [brand, brands, activeBrand]);
  useEffect(() => {
    if (!brand) return;
    let live = true;
    getBrandTree(brand).then((t) => {
      if (!live) return;
      setTree(t);
      const pending = pendingScope.current;
      pendingScope.current = null;
      if (pending && pending.brand === brand) { setPlanId(pending.planId); setCampaignId(pending.campaignId); return; }
      const plan = t.engagement_plans.find((p) => p.campaigns.length) ?? t.engagement_plans[0];
      setPlanId(plan?.id ?? null);
      setCampaignId(plan?.campaigns[0]?.id ?? null);
    }).catch(() => { if (live) setTree({ brand, engagement_plans: [] }); });
    return () => { live = false; };
  }, [brand]);

  // A flow already built for this campaign opens on the canvas.
  useEffect(() => {
    setArtifact(null); setCheck(null); setPhase("intake"); setAck(null); setStatus(["idle", "idle", "idle", "idle"]); setSettled(null);
    if (!brand || !campaignId) return;
    findArtifact(AGENT, brand, campaignId).then(({ artifacts }) => { if (artifacts[0]) setArtifact(artifacts[0]); }).catch(() => undefined);
  }, [brand, campaignId]);

  const plan = tree?.engagement_plans.find((p) => p.id === planId) ?? null;
  const campaign = plan?.campaigns.find((c) => c.id === campaignId) ?? null;

  const read = async () => {
    if (!brand || !campaignId) return;
    setPhase("reading"); setError(null);
    try {
      await uploadAgentIntake(AGENT, `${brand}:${campaignId}`, files, notes);
      setAck(await ackAgentForm(AGENT, brand, planId, campaignId));
      setPhase("ack");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setPhase("intake");
    }
  };

  const mark = (i: number, s: SkillStatus) => setStatus((prev) => prev.map((x, j) => (j === i ? s : x)));

  const build = async () => {
    if (!brand || !campaignId || !ack) return;
    setPhase("running"); setError(null); setCheck(null);
    mark(0, "done");
    // 2 Settle the inputs: derived values, the campaign plan's decisions, and the answers you just OK'd.
    setCurrent(1); mark(1, "running");
    let inputs: Inputs = {};
    try {
      const form = await getAgentForm(AGENT, brand, planId, campaignId);
      const fromPlan: Record<string, string> = {};
      try {
        const { artifacts } = await findArtifact("campaign-planner", brand, campaignId);
        for (const [k, v] of Object.entries(artifacts[0]?.inputs ?? {})) if (v.value && v.confirmed) fromPlan[k] = v.value;
      } catch { /* no campaign plan yet */ }
      const fromAck = Object.fromEntries(ack.answers.map((a) => [a.key, a.value]));
      const filled: string[] = [], missing: string[] = [];
      inputs = Object.fromEntries(form.stages.flatMap((s) => s.data_points).map((p) => {
        const value = p.derivation === "derive" ? p.value : (fromAck[p.key] ?? fromPlan[p.key] ?? null);
        (value ? filled : missing).push(p.label);
        return [p.key, { label: p.label, derivation: p.derivation, value, confirmed: Boolean(value) || p.derivation !== "confirm" }];
      }));
      setSettled({ filled, missing });
      mark(1, "done");
    } catch (e) {
      mark(1, "error"); setError(e instanceof Error ? e.message : String(e)); setPhase("ack"); return;
    }
    // 3 Build the flow.
    setCurrent(2); mark(2, "running");
    let art: V3Artifact;
    try {
      art = await generateArtifact({ agent: AGENT, brand, plan_id: planId, campaign_id: campaignId,
        title: `${campaign?.name ?? "Untitled"} — Flow`, inputs, extras: notes.trim() ? [{ label: "Notes", value: notes.trim() }] : [] });
      setArtifact(art); setDiagramMarkup(null);
      mark(2, "done");
    } catch (e) {
      mark(2, "error"); setError(e instanceof Error ? e.message : String(e)); setPhase("done"); return;
    }
    // 4 Check guidelines.
    setCurrent(3); mark(3, "running");
    try { setCheck(await checkArtifact(art.id)); mark(3, "done"); }
    catch (e) { mark(3, "error"); setError(e instanceof Error ? e.message : String(e)); }
    setCurrent(4);
    setPhase("done");
  };

  const onEdit = async (fieldId: string, value: string) => {
    if (!artifact) return;
    setArtifact(await editArtifact(artifact.id, { [fieldId]: value }));
  };

  const running = phase === "running";
  const stepIdx = phase === "running" || phase === "done" ? current : 0;
  const needsInput = artifact ? artifact.artifact.sections.flatMap((s) => s.fields ?? []).filter((f) => f.needs_input).length : 0;
  const summaries = [
    ack?.understood ?? "",
    settled ? `${settled.filled.length} inputs set, ${settled.missing.length} need input` : "",
    artifact ? `v${artifact.version}${needsInput ? ` · ${needsInput} field(s) need input` : ""}` : "",
    check ? `${check.issues.length} issue(s)` : "",
  ];
  const entries: ReasonEntry[] = [];
  if (ack) entries.push({ id: "ack", title: "Understanding the campaign", status: "done",
    lines: [ack.understood ?? "", ...(ack.approach ?? []), ...ack.answers.map((a) => `Proposed ${a.label ?? a.key}: ${a.value} (${a.source})`)].filter(Boolean) });
  if (settled) entries.push({ id: "inputs", title: "Settling the inputs", status: status[1],
    lines: [`Set: ${settled.filled.join(", ") || "none"}`, settled.missing.length ? `Still needs input: ${settled.missing.join(", ")}` : "Every input is set."] });
  if (status[2] !== "idle") entries.push({ id: "build", title: "Building the flow", status: status[2],
    lines: artifact ? artifact.artifact.sections.map((s) => `${s.title}: ${(s.fields ?? []).length} field(s)`) : [] });
  if (status[3] !== "idle") entries.push({ id: "check", title: "Checking guidelines", status: status[3],
    lines: check ? [check.summary, ...check.issues.map((i) => `[${i.severity}] ${i.label}: ${i.issue} → ${i.suggestion}`)].filter(Boolean) : [] });

  if (!brand) return <p className="v3-empty">Add a brand first: the Flow Planner Agent builds a campaign's journey.</p>;

  return (
    <div className="v3-ws v3-cc v3-flowagent">
      <div className="v3-ws-top">
        <span className="v3-ep-title">Flow Planner Agent — {campaign?.name ?? brand}</span>
        {artifact && <span className="v3-ws-save">Flow v{artifact.version}</span>}
        <span className="v3-ws-top-actions">
          {artifact?.campaign_id && <button type="button" className="v3-cc-btn" onClick={() => { setEditOpen((v) => !v); setShowReasoning(false); }}>Edit the flow</button>}
          <ReasoningButton live={running || phase === "reading"} onClick={() => { setShowReasoning((v) => !v); setEditOpen(false); }} />
        </span>
      </div>
      <div className="v3-ws-body">
        <aside className="v3-ws-inputs">
          <div className="v3-ws-scroll">
            <div className="v3-ws-head">
              <span className="v3-app-icon lg"><Icon name="route" size={20} /></span>
              <div className="v3-ws-head-text">
                <h1>Flow Planner Agent</h1>
                <p>Builds the campaign's channel-by-channel journey from the brief, the campaign plan and your notes, then checks it against {brand}'s guidelines.</p>
              </div>
            </div>

            <ol className="v3-cc-stepper" aria-label="Flow Planner Agent progress">
              {STEPS.map((s, i) => (
                <li key={s} className={i < stepIdx ? "done" : i === stepIdx && phase !== "done" ? "active" : ""}>
                  <span>{i < stepIdx ? <Icon name="check" size={9} /> : i + 1}</span>{s}
                </li>
              ))}
            </ol>

            {(phase === "intake" || phase === "reading") && (
              <section className="v3-ak-intake">
                <div className="v3-cc-intake-head">
                  <b>Campaign intake</b>
                  <span>Pick the campaign, then add the brief and anything else the agent should know.</span>
                </div>
                <div className="v3-flowagent-scope">
                  <label>Brand
                    <select value={brand ?? ""} disabled={phase === "reading"} onChange={(e) => setBrand(e.target.value)}>
                      {brands.map((b) => <option key={b.brand}>{b.brand}</option>)}
                    </select>
                  </label>
                  <label>Engagement plan
                    <select value={planId ?? ""} disabled={phase === "reading"} onChange={(e) => {
                      const p = tree?.engagement_plans.find((x) => x.id === Number(e.target.value));
                      setPlanId(p?.id ?? null); setCampaignId(p?.campaigns[0]?.id ?? null);
                    }}>
                      {(tree?.engagement_plans ?? []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                    </select>
                  </label>
                  <label>Campaign
                    <select value={campaignId ?? ""} disabled={phase === "reading"} onChange={(e) => setCampaignId(Number(e.target.value))}>
                      {(plan?.campaigns ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                    </select>
                  </label>
                </div>
                {tree && !campaign && <p className="v3-cc-banner info">{brand} has no campaign yet. Create one from an engagement plan first.</p>}
                <GlassDrop files={files} setFiles={setFiles} notes={notes} setNotes={setNotes} disabled={phase === "reading"}
                  notesLabel="Tell the agent about the journey"
                  placeholder="Channels to use or avoid, cadence, timing, the moments that matter, what the HCP should do at the end…"
                  hint={artifact ? `This campaign already has a flow (v${artifact.version}); building again saves a new version.` : undefined} />
                <button type="button" className="v3-cc-btn primary wide" disabled={phase === "reading" || !campaign} onClick={read}>
                  {phase === "reading" ? <><span className="v3-cc-spinner small" /> Reading your input…</> : "Build flow"}
                </button>
              </section>
            )}

            {phase === "ack" && ack && (
              <>
                <AckCard ack={ack} onConfirm={build} onEdit={() => setPhase("intake")} />
                {ack.answers.length > 0 && (
                  <div className="v3-flowagent-answers">
                    <em>Inputs the agent will fill</em>
                    {ack.answers.map((a) => <div key={a.key}><b>{a.label ?? a.key}</b><span>{a.value}</span><small>{a.source}</small></div>)}
                  </div>
                )}
              </>
            )}

            {(phase === "running" || phase === "done") && (
              <div className="v3-ak-progress">
                {STEPS.map((name, i) => {
                  if (i > current && phase !== "done") return null;
                  const st = status[i];
                  if (st === "done" || (phase === "done" && st !== "running")) {
                    return (
                      <div key={name} className={`v3-ak-row ${st === "error" ? "" : "done"}`}>
                        <span className="v3-ak-dot">{st === "error" ? "!" : <Icon name="check" size={9} />}</span><b>{name}</b>
                        {summaries[i] && <small className="v3-flowagent-sum">{st === "error" ? "Didn't finish" : summaries[i]}</small>}
                      </div>
                    );
                  }
                  return (
                    <div key={name} className="v3-ak-row current">
                      <div className="v3-ak-row-head"><span className="v3-ak-dot"><span className="v3-cc-spinner small" /></span><b>{name}…</b></div>
                    </div>
                  );
                })}
              </div>
            )}
            {phase === "done" && (
              <div className="v3-ak-done">
                <b>{artifact ? "Flow built." : "The flow didn't build."}</b>
                {check && <span className="v3-muted">{check.summary}</span>}
                {needsInput > 0 && <span className="v3-muted">{needsInput} field(s) still need input — fill them on the canvas.</span>}
                {artifact?.campaign_id && <button type="button" className="v3-cc-btn" onClick={() => { setEditOpen(true); setShowReasoning(false); }}>Edit the flow by chat</button>}
                <button type="button" className="v3-cc-btn" onClick={() => setShowReasoning(true)}>See the reasoning</button>
                <button type="button" className="v3-cc-btn" onClick={() => { setPhase("intake"); setAck(null); }}>Build again</button>
              </div>
            )}
            {error && <p className="v3-cc-banner error">{error}</p>}
          </div>
        </aside>

        <section className="v3-ws-output v3-flowagent-out">
          {running && <p className="v3-ak-canvas-note"><span className="v3-cc-spinner small" /> {STEPS[current]}…</p>}
          {artifact ? (
            <ArtifactViewer art={artifact} readOnly={running} compareTo={null} onEdit={onEdit} issues={check?.issues} diagramMarkup={diagramMarkup} />
          ) : (
            <div className="v3-ws-empty">
              <Icon name="route" size={28} />
              <b>The flow builds here</b>
              <span>Once you confirm what the agent has, it settles the inputs, builds the journey and checks it against the guidelines.</span>
            </div>
          )}
        </section>
        {showReasoning && <ReasoningPanel entries={entries} live={running || phase === "reading"} onClose={() => setShowReasoning(false)} />}
        {editOpen && artifact?.campaign_id && (
          <aside className="v3-refine" aria-label="Edit the flow">
            <div className="v3-refine-head">
              <b><Icon name="sparkles" size={14} /> Edit the flow</b>
              <button type="button" aria-label="Close" onClick={() => setEditOpen(false)}><Icon name="close" size={13} /></button>
            </div>
            <div className="v3-refine-body v3-flow-edit">
              <FlowEditorChat campaignId={artifact.campaign_id} audience="HCP" onMarkup={setDiagramMarkup} embedded />
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}
