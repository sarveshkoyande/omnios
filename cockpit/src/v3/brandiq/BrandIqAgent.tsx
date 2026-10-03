import { useEffect, useRef, useState } from "react";
import { listBrandIqSkills, runBrandIqSkill, uploadBrandPlan, type BrandIqSkill } from "../../api";
import { Icon } from "../../components/Icon";
import type { BrandSummary } from "../../types";
import { BrandKitPage } from "../BrandKitPage";
import "../campaignplanner/campaignPlanner.css";
import "../iq.css";
import "./brandiq.css";

/** The Brand IQ Agent: builds a brand's kit one skill at a time (strategy/kit_proposer.SKILLS).
 *  Starts like the Campaign Agent: drop the brand plan and/or type details, then the skills run one
 *  by one. Left: intake, then each skill's progress. Right: live reasoning per skill, and the Brand
 *  Kit itself, re-read after every step so you watch it being generated. */

type Status = "idle" | "running" | "done" | "error";
const ACCEPT = ".pdf,.docx,.pptx,.txt,.md";

function Intake({ brand, file, setFile, notes, setNotes, onStart }: {
  brand: string; file: File | null; setFile: (f: File | null) => void;
  notes: string; setNotes: (v: string) => void; onStart: () => void;
}) {
  const [drag, setDrag] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  return (
    <section className="v3-cc-intake">
      <div className="v3-cc-intake-head">
        <b>Brand intake</b>
        <span>Upload {brand}'s brand plan and add anything the agent should know. No plan? Start anyway: it builds from public sources.</span>
      </div>
      <div className={`v3-cc-drop ${drag ? "drag" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={(e) => { e.preventDefault(); setDrag(false); }}
        onDrop={(e) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files?.[0]; if (f) setFile(f); }}>
        <Icon name="document" size={20} />
        <b>Drag and drop the brand plan</b>
        <span>PDF, DOCX, PPTX, TXT or MD · up to 10MB</span>
        <button type="button" className="v3-cc-btn" onClick={() => input.current?.click()}>Browse files</button>
        <input ref={input} type="file" accept={ACCEPT} hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) setFile(f); e.target.value = ""; }} />
        {file && (
          <span className="v3-cc-file-chip"><Icon name="document" size={12} /> {file.name}
            <button type="button" aria-label="Remove file" onClick={() => setFile(null)}><Icon name="close" size={10} /></button>
          </span>
        )}
      </div>
      <label className="v3-cc-intake-label" htmlFor="biq-notes">Brand details {file ? "(optional notes on the plan)" : "(optional)"}</label>
      <textarea id="biq-notes" rows={6} value={notes} placeholder="Positioning, priority audiences, objectives, what's changed this year, anything the plan doesn't say…"
        onChange={(e) => setNotes(e.target.value)} />
      <span className="v3-cc-hint">The brand plan is the source of truth: AI drafts never overwrite what it says. It stays on this server.</span>
      <button type="button" className="v3-cc-btn primary wide" onClick={onStart}>Build brand kit</button>
    </section>
  );
}

export function BrandIqAgent({ brands, activeBrand }: { brands: BrandSummary[]; activeBrand: string | null }) {
  const brand = activeBrand ?? brands[0]?.brand ?? null;
  const [skills, setSkills] = useState<BrandIqSkill[]>([]);
  const [status, setStatus] = useState<Record<string, Status>>({});
  const [reasoning, setReasoning] = useState<Record<string, string[]>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [started, setStarted] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [notes, setNotes] = useState("");
  const [tab, setTab] = useState<"reasoning" | "kit">("reasoning");
  const [rev, setRev] = useState(0);
  const [runningAll, setRunningAll] = useState(false);
  const stop = useRef(false);
  const feedEnd = useRef<HTMLDivElement>(null);

  useEffect(() => { listBrandIqSkills().then((r) => setSkills(r.skills)).catch(() => setSkills([])); }, []);
  useEffect(() => { setStatus({}); setReasoning({}); setErrors({}); setStarted(false); setFile(null); setNotes(""); }, [brand]);
  useEffect(() => { feedEnd.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [status, reasoning]);

  const runOne = async (id: string): Promise<boolean> => {
    if (!brand) return false;
    setStatus((s) => ({ ...s, [id]: "running" }));
    setErrors((e) => ({ ...e, [id]: "" }));
    setReasoning((r) => ({ ...r, [id]: [] }));
    try {
      const res = await runBrandIqSkill(brand, id);
      setStatus((s) => ({ ...s, [id]: "done" }));
      setReasoning((r) => ({ ...r, [id]: res.reasoning ?? [] }));
      setRev((r) => r + 1);
      return true;
    } catch (e) {
      setStatus((s) => ({ ...s, [id]: "error" }));
      setErrors((x) => ({ ...x, [id]: e instanceof Error ? e.message : String(e) }));
      return false;
    }
  };

  const runAll = async () => {
    setRunningAll(true);
    stop.current = false;
    for (const s of skills) {
      if (stop.current) break;
      await runOne(s.id);
    }
    setRunningAll(false);
  };

  const start = async () => {
    if (!brand) return;
    setStarted(true);
    setTab("reasoning");
    if (file || notes.trim()) {
      try {
        await uploadBrandPlan(brand, file, notes);
      } catch (e) {
        setErrors((x) => ({ ...x, brand_plan: `Couldn't read the brand plan: ${e instanceof Error ? e.message : String(e)}` }));
      }
    }
    await runAll();
  };

  const busy = runningAll || Object.values(status).includes("running");
  const doneCount = skills.filter((s) => status[s.id] === "done").length;
  const current = skills.findIndex((s) => status[s.id] === "running");
  const stepIdx = current >= 0 ? current : doneCount;
  const shown = skills.filter((s) => (status[s.id] ?? "idle") !== "idle");

  if (!brand) return <p className="v3-empty">Add a brand first: the Brand IQ Agent builds one brand's kit.</p>;

  return (
    <div className="v3-ws v3-cc v3-biq">
      <div className="v3-ws-top">
        <span className="v3-ep-title">Brand IQ — {brand}</span>
        {started && <span className="v3-ws-save">{doneCount}/{skills.length} skills done</span>}
      </div>
      <div className="v3-ws-body">
        <aside className="v3-ws-inputs">
          <div className="v3-ws-scroll">
            <div className="v3-ws-head">
              <span className="v3-app-icon lg"><Icon name="sparkles" size={20} /></span>
              <div className="v3-ws-head-text">
                <h1>Brand IQ Agent</h1>
                <p>Builds {brand}'s brand kit from the brand plan and public sources, one skill at a time. Every other agent reads what it builds.</p>
              </div>
            </div>

            <ol className="v3-cc-stepper" aria-label="Brand IQ progress">
              {skills.map((s, i) => {
                const st = status[s.id];
                return (
                  <li key={s.id} className={st === "done" ? "done" : started && i === stepIdx ? "active" : ""}>
                    <span>{st === "done" ? <Icon name="check" size={9} /> : i + 1}</span>{s.name}
                  </li>
                );
              })}
            </ol>

            {!started ? (
              <Intake brand={brand} file={file} setFile={setFile} notes={notes} setNotes={setNotes} onStart={start} />
            ) : (
              <>
                <ol className="v3-biq-steps">
                  {skills.map((s, i) => {
                    const st = status[s.id] ?? "idle";
                    return (
                      <li key={s.id} className={`v3-biq-step ${st}`}>
                        <span className="v3-biq-num">{st === "done" ? <Icon name="check" size={10} /> : st === "running" ? <span className="v3-cc-spinner small" /> : i + 1}</span>
                        <div className="v3-biq-body">
                          <div className="v3-biq-top">
                            <b>{s.name}</b>
                            <span className={`v3-biq-kind ${s.llm ? "ai" : ""}`}>{s.llm ? "AI skill" : "Data skill"}</span>
                          </div>
                          <p>{st === "running" ? "Running…" : st === "error" ? "Didn't finish — see the reasoning panel" : s.does}</p>
                          {!busy && (st === "done" || st === "error") && (
                            <button type="button" className="v3-link" onClick={() => runOne(s.id)}>{st === "error" ? "Retry" : "Run again"}</button>
                          )}
                        </div>
                      </li>
                    );
                  })}
                </ol>
                <div className="v3-biq-actions">
                  {runningAll
                    ? <button type="button" className="v3-cc-btn wide" onClick={() => { stop.current = true; }}>Stop after this step</button>
                    : <button type="button" className="v3-cc-btn wide" onClick={() => { setStarted(false); setStatus({}); setReasoning({}); setErrors({}); }}>Start over with a new brand plan</button>}
                </div>
              </>
            )}
          </div>
        </aside>

        <section className="v3-ws-output v3-biq-canvas">
          <div className="v3-av-tabs" role="tablist">
            <button type="button" role="tab" aria-selected={tab === "reasoning"} className={tab === "reasoning" ? "active" : ""} onClick={() => setTab("reasoning")}>
              <Icon name="eye" size={13} /> Live reasoning
            </button>
            <button type="button" role="tab" aria-selected={tab === "kit"} className={tab === "kit" ? "active" : ""} onClick={() => setTab("kit")}>
              Brand Kit{busy ? " · updating" : ""}
            </button>
          </div>

          {tab === "kit" ? (
            <BrandKitPage key={`${brand}:${rev}`} activeBrand={brand} brands={brands} />
          ) : !shown.length ? (
            <div className="v3-ws-empty">
              <Icon name="sparkles" size={28} />
              <b>The agent's reasoning appears here</b>
              <span>Each skill runs in turn and says what it read, what it concluded and why. Open the Brand Kit tab to watch the kit fill in.</span>
            </div>
          ) : (
            <div className="v3-biq-feed">
              {shown.map((s) => {
                const st = status[s.id];
                const idx = skills.indexOf(s) + 1;
                return (
                  <article key={s.id} className={`v3-biq-card ${st}`}>
                    <header>
                      <span className="v3-biq-num">{st === "done" ? <Icon name="check" size={10} /> : st === "running" ? <span className="v3-cc-spinner small" /> : idx}</span>
                      <b>{s.name}</b>
                      <span className={`v3-biq-kind ${s.llm ? "ai" : ""}`}>{s.llm ? "AI skill" : "Data skill"}</span>
                    </header>
                    {st === "running" && (
                      <div className="v3-biq-thinking">
                        <span>{s.llm ? "Reasoning over the evidence" : "Fetching"}: {s.does}</span>
                        <div className="v3-ask-thinking"><span /><span /><span /></div>
                      </div>
                    )}
                    {st === "done" && (reasoning[s.id]?.length
                      ? <ul>{reasoning[s.id].map((r, i) => <li key={i}>{r}</li>)}</ul>
                      : <p className="v3-muted">Done. Nothing further to explain.</p>)}
                    {st === "error" && <p className="v3-cc-banner error">{errors[s.id]}</p>}
                  </article>
                );
              })}
              {errors.brand_plan && status.brand_plan !== "error" && <p className="v3-cc-banner error">{errors.brand_plan}</p>}
              {!busy && doneCount > 0 && (
                <button type="button" className="v3-cc-btn primary" onClick={() => setTab("kit")}>Open the Brand Kit</button>
              )}
              <div ref={feedEnd} />
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
