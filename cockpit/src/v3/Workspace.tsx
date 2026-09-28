import { useEffect, useMemo, useRef, useState } from "react";
import { getAgentForm, getBrandTree, type AgentForm, type FormDataPoint, type FormStage } from "../api";
import { REGISTRY } from "../agents";
import { Icon } from "../components/Icon";
import type { BrandSummary, BrandTree } from "../types";
import type { Favorite } from "./store";

/** Phase 3 agent workspace (C1-C8): inputs on the left, output on the right. The input cards
 *  are generated from the agent's framework config (config/frameworks/*.json via
 *  /api/v3/agents/{id}/form): derive = pre-filled from data, confirm = recommendation +
 *  options, ask = yours to answer. The output viewer arrives in Phase 4. */

type Answer = { value: string; confirmed: boolean };
type Answers = Record<string, Answer>;
type ExtraContext = { id: string; label: string; value: string };

const EXTRA_CONTEXT = ["Target audience", "Competitors", "Key data points", "Custom information"];

const draftKey = (agent: string, campaign: number | null) => `omni-v3-draft:${agent}:${campaign ?? "none"}`;

function readDraft(key: string): { answers: Answers; extras: ExtraContext[]; title?: string } {
  try { return JSON.parse(localStorage.getItem(key) ?? "") ?? { answers: {}, extras: [] }; } catch { return { answers: {}, extras: [] }; }
}

/** How complete a data point is: derive needs nothing from you; confirm needs a confirmed or
 *  picked value; ask needs an answer. */
function pointState(p: FormDataPoint, a?: Answer): "done" | "recommended" | "empty" | "auto" {
  if (p.derivation === "ask") return a?.value.trim() ? "done" : "empty";
  if (p.derivation === "confirm") {
    if (a?.confirmed && a.value) return "done";
    return p.recommendation ? "recommended" : "empty";
  }
  return "auto";
}

/** A stage is empty while a required answer is missing, recommended while a recommendation
 *  still awaits confirmation, and done otherwise (an unpicked confirm with no recommendation
 *  is optional -- the planner decides it at Generate). */
function stageState(st: FormStage, answers: Answers): "done" | "recommended" | "empty" {
  const states = st.data_points.map((p) => ({ p, s: pointState(p, answers[p.key]) }));
  if (states.some(({ p, s }) => p.derivation === "ask" && s === "empty")) return "empty";
  if (states.some(({ s }) => s === "recommended")) return "recommended";
  return "done";
}

export function Workspace({ agentId, brands, activeBrand, isFavorite, toggleFavorite }: {
  agentId: string;
  brands: BrandSummary[];
  activeBrand: string | null;
  isFavorite: (type: Favorite["type"], id: string) => boolean;
  toggleFavorite: (fav: Favorite) => void;
}) {
  const agent = REGISTRY.find((a) => a.id === agentId);

  // App settings (C4): starts from the global brand; changing it here overrides only this
  // workspace (BR5).
  const [brand, setBrand] = useState<string | null>(activeBrand);
  const [tree, setTree] = useState<BrandTree | null>(null);
  const [planId, setPlanId] = useState<number | null>(null);
  const [campaignId, setCampaignId] = useState<number | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [switcherOpen, setSwitcherOpen] = useState(false);

  const [form, setForm] = useState<AgentForm | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [openStage, setOpenStage] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Answers>({});
  const [extras, setExtras] = useState<ExtraContext[]>([]);
  const [title, setTitle] = useState("");
  const [generated, setGenerated] = useState<unknown>(null);
  const loadedKey = useRef<string>("");

  useEffect(() => { if (!brand && brands.length) setBrand(activeBrand ?? brands[0].brand); }, [brand, brands, activeBrand]);

  useEffect(() => {
    if (!brand) return;
    let live = true;
    setTree(null);
    getBrandTree(brand).then((t) => {
      if (!live) return;
      setTree(t);
      const plan = t.engagement_plans.find((p) => p.campaigns.length) ?? t.engagement_plans[0];
      setPlanId(plan?.id ?? null);
      setCampaignId(plan?.campaigns[0]?.id ?? null);
    }).catch(() => live && setTree({ brand, engagement_plans: [] }));
    return () => { live = false; };
  }, [brand]);

  const plan = tree?.engagement_plans.find((p) => p.id === planId) ?? null;
  const campaign = plan?.campaigns.find((c) => c.id === campaignId) ?? null;
  const territory = brands.find((b) => b.brand === brand)?.territories[0] ?? null;

  useEffect(() => {
    if (!brand || !tree) return;
    let live = true;
    setForm(null);
    setFormError(null);
    getAgentForm(agentId, brand, planId, campaignId)
      .then((f) => {
        if (!live) return;
        setForm(f);
        setOpenStage((cur) => cur ?? f.stages[0]?.id ?? null);
      })
      .catch((e) => live && setFormError(e instanceof Error ? e.message : String(e)));
    return () => { live = false; };
  }, [agentId, brand, tree, planId, campaignId]);

  // Draft inputs are a per-browser convenience until saving lands in Phase 4 (C15).
  const key = draftKey(agentId, campaignId);
  useEffect(() => {
    const d = readDraft(key);
    setAnswers(d.answers ?? {});
    setExtras(d.extras ?? []);
    setTitle(d.title ?? "");
    setGenerated(null);
    loadedKey.current = key;
  }, [key]);
  useEffect(() => {
    if (loadedKey.current !== key) return;
    try { localStorage.setItem(key, JSON.stringify({ answers, extras, title })); } catch { /* storage unavailable */ }
  }, [key, answers, extras, title]);

  const setAnswer = (k: string, a: Answer) => setAnswers((prev) => ({ ...prev, [k]: a }));

  const stages = form?.stages ?? [];
  const missingAsks = useMemo(
    () => stages.flatMap((s) => s.data_points).filter((p) => p.derivation === "ask" && !answers[p.key]?.value.trim()),
    [stages, answers],
  );
  const doneCount = stages.filter((s) => stageState(s, answers) === "done").length;
  const docTitle = title || `${campaign?.name ?? "Untitled"} — ${agent?.name === "Briefing Agent" ? "Brief" : agent?.name ?? ""}`;

  const generate = () => {
    setGenerated({
      agent: agentId,
      framework: form?.framework?.id,
      brand, territory, plan: plan?.name ?? null, campaign: campaign?.name ?? null,
      inputs: Object.fromEntries(stages.flatMap((s) => s.data_points).map((p) => {
        const a = answers[p.key];
        const value = p.derivation === "derive" ? p.value : a?.value || (p.derivation === "confirm" ? p.recommendation : null);
        return [p.key, { label: p.label, derivation: p.derivation, value, confirmed: p.derivation !== "confirm" || Boolean(a?.confirmed) }];
      })),
      extra_context: extras.filter((x) => x.value.trim()),
    });
  };

  if (!agent) return <p className="v3-muted">No agent called "{agentId}".</p>;
  const fav = isFavorite("app", agent.id);

  return (
    <div className="v3-ws">
      <div className="v3-ws-top">
        <input className="v3-ws-title" value={docTitle} aria-label="Title" onChange={(e) => setTitle(e.target.value)} />
        <span className="v3-ws-save"><Icon name="document" size={13} /> Draft on this browser</span>
        <span className="v3-ws-top-actions">
          <button type="button" disabled title="Arrives with saving (Phase 4)">Version history</button>
          <button type="button" disabled title="Arrives in Phase 5">Share</button>
        </span>
      </div>

      <div className="v3-ws-body">
        <aside className="v3-ws-inputs">
          <div className="v3-ws-scroll">
            <div className="v3-ws-head">
              <span className="v3-app-icon lg"><Icon name={agent.icon} size={20} /></span>
              <div className="v3-ws-head-text">
                <div className="v3-ws-head-row">
                  <h1>{agent.name}</h1>
                  <button type="button" className={`v3-ws-star ${fav ? "on" : ""}`} aria-label={fav ? "Remove from favorites" : "Add to favorites"}
                    onClick={() => toggleFavorite({ type: "app", id: agent.id, label: agent.name, href: `#/v3/agent/${agent.id}` })}>
                    <Icon name="star" size={15} />
                  </button>
                </div>
                <p>{agent.summary}</p>
              </div>
            </div>

            <div className="v3-ws-change">
              <button type="button" className="v3-ws-change-btn" onClick={() => setSwitcherOpen((o) => !o)}>
                <Icon name="layers" size={13} /> Change agent <Icon name="chevronDown" size={12} />
              </button>
              {switcherOpen && (
                <div className="v3-new-menu v3-ws-switch">
                  {REGISTRY.filter((a) => !a.tags.includes("coming-soon")).map((a) => (
                    <a key={a.id} className="v3-new-item" href={a.route ?? `#/v3/app/${a.id}`} onClick={() => setSwitcherOpen(false)}>{a.name}</a>
                  ))}
                </div>
              )}
            </div>

            <section className={`v3-ws-settings ${settingsOpen ? "open" : ""}`}>
              <button type="button" className="v3-ws-settings-row" onClick={() => setSettingsOpen((o) => !o)} aria-expanded={settingsOpen}>
                <b>Settings</b>
                <span>{[brand, territory, plan?.name, campaign?.name].filter(Boolean).join(" · ") || "Choose a brand"}</span>
                <Icon name="chevronDown" size={13} />
              </button>
              {settingsOpen && (
                <div className="v3-ws-settings-grid">
                  <label>Brand
                    <select value={brand ?? ""} onChange={(e) => setBrand(e.target.value)}>
                      {brands.map((b) => <option key={b.brand}>{b.brand}</option>)}
                    </select>
                  </label>
                  <label>Territory
                    <select value={territory ?? ""} disabled><option>{territory ?? "—"}</option></select>
                  </label>
                  <label>Engagement plan
                    <select value={planId ?? ""} onChange={(e) => {
                      const p = tree?.engagement_plans.find((x) => x.id === Number(e.target.value));
                      setPlanId(p?.id ?? null); setCampaignId(p?.campaigns[0]?.id ?? null);
                    }}>
                      {(tree?.engagement_plans ?? []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                    </select>
                  </label>
                  <label>Campaign
                    <select value={campaignId ?? ""} onChange={(e) => setCampaignId(Number(e.target.value))}>
                      {(plan?.campaigns ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                    </select>
                  </label>
                  {brand !== activeBrand && activeBrand && (
                    <p className="v3-ws-note">Using {brand} here only; your global brand is still {activeBrand}.</p>
                  )}
                </div>
              )}
            </section>

            {form?.framework && (
              <div className="v3-ws-progress">
                <span>{form.framework.name}</span>
                <span>{doneCount} of {stages.length} ready</span>
              </div>
            )}
            {formError && <p className="v3-ask-error">{formError}</p>}
            {!form && !formError && <p className="v3-muted">Loading inputs…</p>}

            {stages.map((st) => {
              const state = stageState(st, answers);
              const open = openStage === st.id;
              return (
                <section key={st.id} className={`v3-card-in ${open ? "open" : ""}`}>
                  <button type="button" className="v3-card-in-head" onClick={() => setOpenStage(open ? null : st.id)} aria-expanded={open}>
                    <span className={`v3-status ${state}`}>{state === "done" ? <Icon name="check" size={11} /> : null}</span>
                    <span className="v3-card-in-title"><b>{st.name}</b><span>{st.decision}</span></span>
                    <Icon name="chevronDown" size={13} />
                  </button>
                  {open && (
                    <div className="v3-card-in-body">
                      <p className="v3-card-in-why" title={st.how}>{st.framework}</p>
                      {st.data_points.map((p) => <DataPointRow key={p.key} p={p} answer={answers[p.key]} onChange={(a) => setAnswer(p.key, a)} />)}
                    </div>
                  )}
                </section>
              );
            })}

            {form && (
              <section className="v3-ws-extra">
                <b>Add more context</b>
                <div className="v3-chip-row">
                  {EXTRA_CONTEXT.map((label) => (
                    <button key={label} type="button" className="v3-chip" onClick={() => setExtras((x) => [...x, { id: `${label}-${Date.now()}`, label, value: "" }])}>
                      <Icon name="plus" size={11} /> {label}
                    </button>
                  ))}
                </div>
                {extras.map((x) => (
                  <div key={x.id} className="v3-ws-extra-item">
                    <div className="v3-ws-extra-head"><b>{x.label}</b>
                      <button type="button" aria-label={`Remove ${x.label}`} onClick={() => setExtras((all) => all.filter((y) => y.id !== x.id))}><Icon name="close" size={11} /></button>
                    </div>
                    <textarea rows={2} value={x.value} placeholder={`Add ${x.label.toLowerCase()}…`}
                      onChange={(e) => setExtras((all) => all.map((y) => (y.id === x.id ? { ...y, value: e.target.value } : y)))} />
                  </div>
                ))}
              </section>
            )}
          </div>

          <div className="v3-ws-generate">
            <button type="button" disabled={!form || missingAsks.length > 0} onClick={generate}>
              {generated ? "Regenerate" : "Generate"}
            </button>
            {form && missingAsks.length > 0 && <span>Answer {missingAsks.length} required question{missingAsks.length === 1 ? "" : "s"} to generate</span>}
          </div>
        </aside>

        <section className="v3-ws-output">
          {generated ? (
            <div className="v3-ws-output-inner">
              <div className="v3-ws-output-tabs"><span className="active">Data</span><span title="Phase 4">Overview</span><span title="Phase 4">Detail</span></div>
              <p className="v3-muted">These are the structured inputs the brief will be generated from. The brief itself, with its Overview and Detail views, arrives in Phase 4.</p>
              <pre className="v3-ws-json">{JSON.stringify(generated, null, 2)}</pre>
            </div>
          ) : (
            <div className="v3-ws-empty">
              <span className="v3-app-icon lg"><Icon name={agent.icon} size={22} /></span>
              <b>Your {agent.name === "Briefing Agent" ? "brief" : "output"} appears here</b>
              <p>Check the inputs on the left, answer anything marked required, then Generate.</p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function DataPointRow({ p, answer, onChange }: { p: FormDataPoint; answer?: Answer; onChange: (a: Answer) => void }) {
  const state = pointState(p, answer);
  const sourceLabel = p.source === "external" ? "External data" : p.source === "user" ? "You" : "Brand data";

  if (p.derivation === "derive") {
    return (
      <div className="v3-dp">
        <div className="v3-dp-label">{p.label}<em>{sourceLabel}</em></div>
        {p.value ? <div className="v3-dp-value">{p.value}</div> : <div className="v3-dp-auto">Worked out when you generate</div>}
      </div>
    );
  }

  if (p.derivation === "ask") {
    return (
      <div className={`v3-dp ${state}`}>
        <div className="v3-dp-label">{p.label}<em className="req">Required</em></div>
        <textarea rows={2} value={answer?.value ?? ""} placeholder="Your answer…"
          onChange={(e) => onChange({ value: e.target.value, confirmed: true })} />
      </div>
    );
  }

  const chosen = answer?.confirmed ? answer.value : null;
  return (
    <div className={`v3-dp ${state}`}>
      <div className="v3-dp-label">{p.label}<em>{state === "recommended" ? "Recommended — confirm or change" : state === "done" ? "Confirmed" : "Pick one"}</em></div>
      {p.recommendation && !chosen && (
        <div className="v3-dp-rec">
          <span>{p.recommendation}</span>
          <button type="button" onClick={() => onChange({ value: p.recommendation as string, confirmed: true })}>Confirm</button>
        </div>
      )}
      {(p.options.length > 0 || chosen) && (
        <div className="v3-chip-row">
          {[...new Set([...(p.recommendation ? [p.recommendation] : []), ...p.options])].map((o) => (
            <button key={o} type="button" className={`v3-chip ${chosen === o ? "on" : ""}`} aria-pressed={chosen === o}
              onClick={() => onChange({ value: o, confirmed: true })}>{o}</button>
          ))}
        </div>
      )}
      <input className="v3-dp-other" placeholder="Or type your own…" value={chosen && ![p.recommendation, ...p.options].includes(chosen) ? chosen : ""}
        onChange={(e) => onChange({ value: e.target.value, confirmed: Boolean(e.target.value.trim()) })} />
    </div>
  );
}
