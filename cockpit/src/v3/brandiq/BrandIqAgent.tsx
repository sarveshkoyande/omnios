import { useEffect, useRef, useState } from "react";
import { listBrandIqSkills, runBrandIqSkill, type BrandIqSkill } from "../../api";
import { Icon } from "../../components/Icon";
import type { BrandSummary } from "../../types";
import { BrandKitPage } from "../BrandKitPage";
import "../campaignplanner/campaignPlanner.css";
import "../iq.css";
import "./brandiq.css";

/** The Brand IQ Agent: builds a brand's kit one skill at a time (strategy/kit_proposer.SKILLS).
 *  Left: the steps, each a separate skill you can run alone or all in order. Right: the Brand Kit,
 *  re-read after every step so you watch it being generated. */

type Status = "idle" | "running" | "done" | "error";

export function BrandIqAgent({ brands, activeBrand }: { brands: BrandSummary[]; activeBrand: string | null }) {
  const brand = activeBrand ?? brands[0]?.brand ?? null;
  const [skills, setSkills] = useState<BrandIqSkill[]>([]);
  const [status, setStatus] = useState<Record<string, Status>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [rev, setRev] = useState(0);
  const [runningAll, setRunningAll] = useState(false);
  const stop = useRef(false);

  useEffect(() => { listBrandIqSkills().then((r) => setSkills(r.skills)).catch(() => setSkills([])); }, []);
  useEffect(() => { setStatus({}); setErrors({}); }, [brand]);

  const runOne = async (id: string): Promise<boolean> => {
    if (!brand) return false;
    setStatus((s) => ({ ...s, [id]: "running" }));
    setErrors((e) => ({ ...e, [id]: "" }));
    try {
      await runBrandIqSkill(brand, id);
      setStatus((s) => ({ ...s, [id]: "done" }));
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

  const busy = runningAll || Object.values(status).includes("running");
  const doneCount = skills.filter((s) => status[s.id] === "done").length;

  if (!brand) return <p className="v3-empty">Add a brand first: the Brand IQ Agent builds one brand's kit.</p>;

  return (
    <div className="v3-ws v3-cc v3-biq">
      <div className="v3-ws-top">
        <span className="v3-ep-title">Brand IQ — {brand}</span>
        <span className="v3-ws-save">{doneCount}/{skills.length} skills run this session</span>
      </div>
      <div className="v3-ws-body">
        <aside className="v3-ws-inputs">
          <div className="v3-ws-scroll">
            <div className="v3-ws-head">
              <span className="v3-app-icon lg"><Icon name="sparkles" size={20} /></span>
              <div className="v3-ws-head-text">
                <h1>Brand IQ Agent</h1>
                <p>Builds {brand}'s brand kit from public sources and the brand plan, one skill at a time. Every other agent reads what it builds.</p>
              </div>
            </div>

            <div className="v3-biq-actions">
              {runningAll
                ? <button type="button" className="v3-cc-btn wide" onClick={() => { stop.current = true; }}>Stop after this step</button>
                : <button type="button" className="v3-cc-btn primary wide" disabled={busy || !skills.length} onClick={runAll}>Run all steps</button>}
            </div>

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
                      <p>{s.does}</p>
                      {st === "error" && <p className="v3-cc-banner error">{errors[s.id]}</p>}
                      <button type="button" className="v3-cc-btn" disabled={busy} onClick={() => runOne(s.id)}>
                        {st === "done" ? "Run again" : st === "error" ? "Retry" : "Run this step"}
                      </button>
                    </div>
                  </li>
                );
              })}
            </ol>
          </div>
        </aside>

        <section className="v3-ws-output v3-biq-canvas">
          {busy && <p className="v3-biq-live"><span className="v3-cc-spinner small" /> Generating — the kit updates after each step</p>}
          <BrandKitPage key={`${brand}:${rev}`} activeBrand={brand} brands={brands} />
        </section>
      </div>
    </div>
  );
}
