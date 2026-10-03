import { useEffect, useRef, useState } from "react";
import {
  ackBrandIq, getBrandIqSteps, resetBrandIq, restoreKitVersion, runBrandIqSkill, uploadBrandPlan,
  type AgentAck, type AgentStepDef, type BrandIqSkill,
} from "../../api";
import { Icon } from "../../components/Icon";
import type { BrandSummary } from "../../types";
import { AckCard, ReasoningButton, ReasoningPanel, StepProgress, type ReasonEntry, type SkillStatus } from "../agentkit/AgentKit";
import { BrandKitPage } from "../BrandKitPage";
import "../campaignplanner/campaignPlanner.css";
import "../iq.css";
import "./brandiq.css";

/** The Brand IQ Agent. Four agent steps (strategy/kit_proposer.STEPS) over ten skills:
 *  1. you drop the brand plan and/or type (or nothing); the agent reads it and acknowledges what's
 *     available and what isn't (LLM, no fixed rules) and waits for your OK;
 *  2. it saves the current kit as a restorable version and rebuilds the kit from scratch, step by step;
 *  3. the Brand Kit is the main canvas, re-read after every skill; Live reasoning is a slide-in panel. */

type Phase = "intake" | "reading" | "ack" | "running" | "done";
const ACCEPT = ".pdf,.docx,.pptx,.txt,.md";

export function BrandIqAgent({ brands, activeBrand }: { brands: BrandSummary[]; activeBrand: string | null }) {
  const brand = activeBrand ?? brands[0]?.brand ?? null;
  const [steps, setSteps] = useState<AgentStepDef[]>([]);
  const [skills, setSkills] = useState<BrandIqSkill[]>([]);
  const [phase, setPhase] = useState<Phase>("intake");
  const [file, setFile] = useState<File | null>(null);
  const [notes, setNotes] = useState("");
  const [drag, setDrag] = useState(false);
  const [ack, setAck] = useState<AgentAck | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<Record<string, SkillStatus>>({});
  const [reasons, setReasons] = useState<Record<string, string[]>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [currentStep, setCurrentStep] = useState(0);
  const [rev, setRev] = useState(0);
  const [showReasoning, setShowReasoning] = useState(false);
  const [savedVersion, setSavedVersion] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const stop = useRef(false);

  useEffect(() => { getBrandIqSteps().then((r) => { setSteps(r.steps); setSkills(r.skills); }).catch(() => undefined); }, []);
  useEffect(() => {
    setPhase("intake"); setFile(null); setNotes(""); setAck(null); setError(null); setStatus({}); setReasons({});
    setErrors({}); setCurrentStep(0); setSavedVersion(null); setShowReasoning(false);
  }, [brand]);

  const skillNames = Object.fromEntries(skills.map((s) => [s.id, s.name]));

  const read = async () => {
    if (!brand) return;
    setPhase("reading"); setError(null);
    try {
      await uploadBrandPlan(brand, file, notes);
      setAck(await ackBrandIq(brand));
      setPhase("ack");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setPhase("intake");
    }
  };

  const runSkill = async (id: string) => {
    if (!brand) return;
    setStatus((s) => ({ ...s, [id]: "running" }));
    try {
      const res = await runBrandIqSkill(brand, id);
      setReasons((r) => ({ ...r, [id]: res.reasoning ?? [] }));
      setStatus((s) => ({ ...s, [id]: "done" }));
    } catch (e) {
      setErrors((x) => ({ ...x, [id]: e instanceof Error ? e.message : String(e) }));
      setStatus((s) => ({ ...s, [id]: "error" }));
    }
    setRev((r) => r + 1);
  };

  const build = async () => {
    if (!brand) return;
    setPhase("running"); setStatus({}); setReasons({}); setErrors({}); setCurrentStep(0); stop.current = false;
    try {
      setSavedVersion((await resetBrandIq(brand)).saved_version);
      setRev((r) => r + 1);
    } catch (e) {
      setError(`Couldn't start the rebuild: ${e instanceof Error ? e.message : String(e)}`);
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
  };

  const restore = async () => {
    if (!brand || !savedVersion) return;
    try { await restoreKitVersion(brand, savedVersion); setRev((r) => r + 1); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  };

  const running = phase === "running";
  const entries: ReasonEntry[] = [
    ...(ack ? [{ id: "ack", title: "Understanding your input", status: "done" as SkillStatus,
      lines: [ack.understood ?? "", ...(ack.approach ?? [])].filter(Boolean) }] : []),
    ...skills.filter((s) => (status[s.id] ?? "idle") !== "idle").map((s) => ({
      id: s.id, title: s.name, status: status[s.id], lines: reasons[s.id] ?? [], error: errors[s.id],
    })),
  ];
  const stepIdx = phase === "intake" || phase === "reading" || phase === "ack" ? 0 : currentStep;

  if (!brand) return <p className="v3-empty">Add a brand first: the Brand IQ Agent builds one brand's kit.</p>;

  return (
    <div className="v3-ws v3-cc v3-biq">
      <div className="v3-ws-top">
        <span className="v3-ep-title">Brand IQ — {brand}</span>
        {savedVersion && <span className="v3-ws-save">Previous kit saved ({savedVersion})</span>}
        <span className="v3-ws-top-actions"><ReasoningButton live={running} onClick={() => setShowReasoning((v) => !v)} /></span>
      </div>
      <div className="v3-ws-body">
        <aside className="v3-ws-inputs">
          <div className="v3-ws-scroll">
            <div className="v3-ws-head">
              <span className="v3-app-icon lg"><Icon name="sparkles" size={20} /></span>
              <div className="v3-ws-head-text">
                <h1>Brand IQ Agent</h1>
                <p>Builds {brand}'s brand kit from the brand plan and public sources. Every other agent reads what it builds.</p>
              </div>
            </div>

            <ol className="v3-cc-stepper" aria-label="Brand IQ progress">
              {steps.map((s, i) => (
                <li key={s.id} className={i < stepIdx || phase === "done" ? "done" : i === stepIdx ? "active" : ""}>
                  <span>{i < stepIdx || phase === "done" ? <Icon name="check" size={9} /> : i + 1}</span>{s.name}
                </li>
              ))}
            </ol>

            {(phase === "intake" || phase === "reading") && (
              <section className="v3-cc-intake">
                <div className="v3-cc-intake-head">
                  <b>Brand intake</b>
                  <span>Drop {brand}'s brand plan and/or tell the agent about the brand. Nothing to add? Just build: it works from secondary sources.</span>
                </div>
                <div className={`v3-cc-drop ${drag ? "drag" : ""}`}
                  onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
                  onDragLeave={(e) => { e.preventDefault(); setDrag(false); }}
                  onDrop={(e) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files?.[0]; if (f) setFile(f); }}>
                  <Icon name="document" size={20} />
                  <b>Drag and drop the brand plan</b>
                  <span>PDF, DOCX, PPTX, TXT or MD · up to 10MB</span>
                  <button type="button" className="v3-cc-btn" disabled={phase === "reading"} onClick={() => input.current?.click()}>Browse files</button>
                  <input ref={input} type="file" accept={ACCEPT} hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) setFile(f); e.target.value = ""; }} />
                  {file && (
                    <span className="v3-cc-file-chip"><Icon name="document" size={12} /> {file.name}
                      <button type="button" aria-label="Remove file" onClick={() => setFile(null)}><Icon name="close" size={10} /></button>
                    </span>
                  )}
                </div>
                <label className="v3-cc-intake-label" htmlFor="biq-notes">Tell the agent about the brand</label>
                <textarea id="biq-notes" rows={6} value={notes} disabled={phase === "reading"} onChange={(e) => setNotes(e.target.value)}
                  placeholder="Positioning, priority audiences, objectives, what's changed this year, anything the plan doesn't say…" />
                <span className="v3-cc-hint">The brand plan is the source of truth: AI drafts never overwrite what it says. It stays on this server.</span>
                <button type="button" className="v3-cc-btn primary wide" disabled={phase === "reading"} onClick={read}>
                  {phase === "reading" ? <><span className="v3-cc-spinner small" /> Reading your input…</> : "Build brand kit"}
                </button>
              </section>
            )}

            {phase === "ack" && ack && (
              <AckCard ack={ack} onConfirm={build} onEdit={() => setPhase("intake")} />
            )}
            {phase === "ack" && <p className="v3-cc-hint">Building saves {brand}'s current kit as a version you can restore, then rebuilds it from scratch.</p>}

            {(phase === "running" || phase === "done") && (
              <StepProgress steps={steps} skillNames={skillNames} status={status} currentStep={currentStep} done={phase === "done"} />
            )}
            {running && <button type="button" className="v3-cc-btn wide v3-biq-actions" onClick={() => { stop.current = true; }}>Stop after this part</button>}
            {phase === "done" && (
              <div className="v3-ak-done">
                <b>{brand}'s kit is rebuilt.</b>
                <span className="v3-muted">AI-drafted sections are marked "Proposed — to confirm" on the kit. Review them before agents rely on them.</span>
                <button type="button" className="v3-cc-btn" onClick={() => setShowReasoning(true)}>See the reasoning</button>
                {savedVersion && <button type="button" className="v3-cc-btn" onClick={restore}>Restore the previous kit</button>}
                <button type="button" className="v3-cc-btn" onClick={() => { setPhase("intake"); setAck(null); }}>Build again</button>
              </div>
            )}
            {error && <p className="v3-cc-banner error">{error}</p>}
          </div>
        </aside>

        <section className="v3-ws-output v3-biq-canvas">
          {running && <p className="v3-ak-canvas-note"><span className="v3-cc-spinner small" /> Building — {steps[currentStep]?.name ?? ""}</p>}
          <BrandKitPage key={`${brand}:${rev}`} activeBrand={brand} brands={brands} />
        </section>
        {showReasoning && <ReasoningPanel entries={entries} live={running} onClose={() => setShowReasoning(false)} />}
      </div>
    </div>
  );
}

