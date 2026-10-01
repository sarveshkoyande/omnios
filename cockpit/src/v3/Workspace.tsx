import { useEffect, useMemo, useRef, useState } from "react";
import {
  artifactCsvUrl, artifactVersions, checkArtifact, editArtifact, findArtifact, generateArtifact, getAgentForm, getArtifact,
  getBrandTree, restoreArtifact,
  type AgentForm, type FormDataPoint, type FormStage, type GuidelineCheck, type V3Artifact,
} from "../api";
import { ArtifactViewer } from "./ArtifactViewer";
import { RefineDrawer } from "./RefineDrawer";
import { FlowEditorChat } from "../components/flowplanner/FlowEditorChat";

/** What each agent's artifact is called, and where it can be handed off to (C14, D4). */
const ARTIFACT_NOUN: Record<string, string> = { "brief-compiler": "Brief", "campaign-planner": "Campaign plan", "flow-planner": "Flow" };
const HANDOFF: Record<string, { id: string; label: string }[]> = {
  "campaign-planner": [{ id: "flow-planner", label: "Build the flow" }, { id: "brief-compiler", label: "Compile the brief" }],
  "flow-planner": [{ id: "campaign-planner", label: "Open the campaign plan" }, { id: "brief-compiler", label: "Compile the brief" }],
  "brief-compiler": [{ id: "campaign-planner", label: "Open the campaign plan" }, { id: "flow-planner", label: "Build the flow" }],
};
export type Handoff = { brand: string; planId: number | null; campaignId: number | null };
import { REGISTRY } from "../agents";
import { Icon } from "../components/Icon";
import type { BrandSummary, BrandTree } from "../types";
import type { Favorite } from "./store";

/** Phase 3 agent workspace (C1-C8): inputs on the left, output on the right. The input cards
 *  are generated from the agent's framework config (config/frameworks/*.json via
 *  /api/v3/agents/{id}/form): derive = pre-filled from data, confirm = recommendation +
 *  options, ask = yours to answer. Generate projects those inputs into a typed, versioned
 *  artifact (Phase 4, strategy/v3_artifacts.py) shown in the viewer on the right. */

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

/** A stage is done only when every ask is answered and every confirm is decided -- the same
 *  test the brief uses, so a green stage never feeds a "Needs input" brief field. Open picks
 *  show as empty; only unanswered asks block Generate (see missingAsks). */
function stageState(st: FormStage, answers: Answers): "done" | "recommended" | "empty" {
  const states = st.data_points.map((p) => pointState(p, answers[p.key]));
  if (states.includes("empty")) return "empty";
  if (states.includes("recommended")) return "recommended";
  return "done";
}

export function Workspace({ agentId, artifactId, handoff, brands, activeBrand, isFavorite, toggleFavorite }: {
  agentId: string;
  /** Reopen a specific saved artifact (from My work / Recent work). */
  artifactId?: string;
  /** Opened from another agent's "Send to": work on that exact brand, plan and campaign. */
  handoff?: Handoff;
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
  const [artifact, setArtifact] = useState<V3Artifact | null>(null);
  const [viewing, setViewing] = useState<V3Artifact | null>(null);
  const [versionsOpen, setVersionsOpen] = useState(false);
  const [versionList, setVersionList] = useState<{ version: number; created_at: string; reason: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);
  const [refineOpen, setRefineOpen] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [check, setCheck] = useState<GuidelineCheck | null>(null);
  const [checking, setChecking] = useState(false);
  const [checkError, setCheckError] = useState<string | null>(null);
  const [focusField, setFocusField] = useState<{ id: string; nonce: number } | null>(null);
  const [sendOpen, setSendOpen] = useState(false);
  const [seededFrom, setSeededFrom] = useState<number | null>(null);
  const [diagramMarkup, setDiagramMarkup] = useState<string | null>(null);
  const loadedKey = useRef<string>("");
  /** Set when reopening a saved artifact, so the tree load selects its plan + campaign. */
  const pendingSelection = useRef<{ planId: number | null; campaignId: number | null } | null>(null);

  useEffect(() => {
    if (!handoff) return;
    pendingSelection.current = { planId: handoff.planId, campaignId: handoff.campaignId };
    setBrand(handoff.brand);
  }, [handoff]);

  useEffect(() => {
    if (!artifactId) return;
    getArtifact(artifactId).then((a) => {
      pendingSelection.current = { planId: a.plan_id, campaignId: a.campaign_id };
      setBrand(a.brand);
    }).catch(() => undefined);
  }, [artifactId]);

  useEffect(() => { if (!brand && !artifactId && !handoff && brands.length) setBrand(activeBrand ?? brands[0].brand); }, [brand, brands, activeBrand, artifactId]);

  useEffect(() => {
    if (!brand) return;
    let live = true;
    setTree(null);
    getBrandTree(brand).then((t) => {
      if (!live) return;
      setTree(t);
      const pending = pendingSelection.current;
      pendingSelection.current = null;
      if (pending) { setPlanId(pending.planId); setCampaignId(pending.campaignId); return; }
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
    setArtifact(null);
    setViewing(null);
    loadedKey.current = key;
  }, [key]);

  // A saved artifact for this agent + campaign wins over the browser draft: its inputs are
  // what the saved brief was generated from.
  useEffect(() => {
    if (!brand || !campaignId) return;
    let live = true;
    setSeededFrom(null);
    findArtifact(agentId, brand, campaignId).then(({ artifacts }) => {
      const a = artifacts[0];
      if (!live) return;
      if (!a) {
        // No artifact of our own yet: start from this campaign's plan, if one exists (D4). The
        // plan and every downstream agent share the same framework keys.
        if (agentId === "campaign-planner") return;
        findArtifact("campaign-planner", brand, campaignId).then(({ artifacts: plans }) => {
          const plan = plans[0];
          if (!live || !plan) return;
          setAnswers(Object.fromEntries(Object.entries(plan.inputs)
            .filter(([, v]) => v.derivation !== "derive" && v.value)
            .map(([k, v]) => [k, { value: v.value as string, confirmed: v.confirmed }])));
          setSeededFrom(plan.version);
        }).catch(() => undefined);
        return;
      }
      setArtifact(a);
      setTitle(a.title);
      setExtras(a.extras.map((x, i) => ({ id: x.id ?? `${x.label}-${i}`, label: x.label, value: x.value })));
      setAnswers(Object.fromEntries(Object.entries(a.inputs)
        .filter(([, v]) => v.derivation !== "derive" && v.value)
        .map(([k, v]) => [k, { value: v.value as string, confirmed: v.confirmed }])));
    }).catch(() => undefined);
    return () => { live = false; };
  }, [agentId, brand, campaignId]);
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
  const noun = ARTIFACT_NOUN[agentId] ?? agent?.name ?? "Output";
  const docTitle = title || `${campaign?.name ?? "Untitled"} — ${noun}`;
  const handoffHref = (to: string) => `#/v3/agent/${to}/for/${encodeURIComponent(brand ?? "")}/${planId ?? 0}/${campaignId ?? 0}`;

  /** Only confirmed or answered values go in; an unconfirmed recommendation stays undecided
   *  (the brief shows "Needs input") rather than being silently accepted. */
  const generate = () => {
    if (!brand) return;
    setBusy(true);
    setGenError(null);
    generateArtifact({
      agent: agentId, brand, plan_id: planId, campaign_id: campaignId, title: docTitle,
      inputs: Object.fromEntries(stages.flatMap((s) => s.data_points).map((p) => {
        const a = answers[p.key];
        const value = p.derivation === "derive" ? p.value : (a?.confirmed ? a.value : null) || null;
        return [p.key, { label: p.label, derivation: p.derivation, value, confirmed: p.derivation !== "confirm" || Boolean(a?.confirmed) }];
      })),
      extras: extras.filter((x) => x.value.trim()),
    })
      .then((a) => { setArtifact(a); setViewing(null); })
      .catch((e) => setGenError(e instanceof Error ? e.message : String(e)))
      .finally(() => setBusy(false));
  };

  const onEdit = async (fieldId: string, value: string) => {
    if (!artifact) return;
    setArtifact(await editArtifact(artifact.id, { [fieldId]: value }));
    setCheck(null);
  };

  /** C12: LLM pre-review against the brand's guardrails; results stay until the brief changes. */
  const runCheck = () => {
    if (!artifact) return;
    setChecking(true);
    setCheckError(null);
    checkArtifact(artifact.id)
      .then(setCheck)
      .catch((e) => setCheckError(e instanceof Error ? e.message : String(e)))
      .finally(() => setChecking(false));
  };

  /** C14 exports: JSON (machine), CSV (table), PDF (the browser's print-to-PDF of the full brief). */
  const exportJson = () => {
    if (!artifact) return;
    const blob = new Blob([JSON.stringify({ ...artifact.artifact, meta: { id: artifact.id, title: artifact.title, brand: artifact.brand, version: artifact.version } }, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${artifact.title || "brief"} v${artifact.version}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
    setExportOpen(false);
  };

  const toggleVersions = () => {
    if (!artifact) return;
    if (!versionsOpen) artifactVersions(artifact.id).then((r) => setVersionList(r.versions)).catch(() => setVersionList([]));
    setVersionsOpen((o) => !o);
  };
  const viewVersion = (v: number) => {
    if (!artifact) return;
    setVersionsOpen(false);
    if (v === artifact.version) { setViewing(null); return; }
    getArtifact(artifact.id, v).then(setViewing).catch(() => undefined);
  };
  const restoreViewing = () => {
    if (!artifact || !viewing) return;
    restoreArtifact(artifact.id, viewing.version).then((a) => { setArtifact(a); setViewing(null); }).catch(() => undefined);
  };

  if (!agent) return <p className="v3-muted">No agent called "{agentId}".</p>;
  const fav = isFavorite("app", agent.id);

  return (
    <div className="v3-ws">
      <div className="v3-ws-top">
        <input className="v3-ws-title" value={docTitle} aria-label="Title" onChange={(e) => setTitle(e.target.value)} />
        <span className="v3-ws-save">
          {artifact ? <><Icon name="check" size={13} /> Saved · v{artifact.version}</> : <><Icon name="document" size={13} /> Draft on this browser</>}
        </span>
        <span className="v3-ws-top-actions">
          <span className="v3-ws-versions">
            <button type="button" disabled={!artifact} onClick={toggleVersions} aria-expanded={versionsOpen}
              title={artifact ? undefined : "Generate first"}>Version history</button>
            {versionsOpen && (
              <div className="v3-new-menu v3-ws-version-menu">
                {versionList.map((v) => (
                  <button key={v.version} type="button" className={`v3-ws-version ${(viewing?.version ?? artifact?.version) === v.version ? "active" : ""}`}
                    onClick={() => viewVersion(v.version)}>
                    <b>v{v.version}{v.version === artifact?.version ? " · current" : ""}</b>
                    <span>{v.reason}</span>
                    <em>{new Date(v.created_at).toLocaleString()}</em>
                  </button>
                ))}
              </div>
            )}
          </span>
          <button type="button" disabled={!artifact || checking} onClick={runCheck}>{checking ? "Checking…" : "Check guidelines"}</button>
          <span className="v3-ws-versions">
            <button type="button" disabled={!artifact} onClick={() => setExportOpen((o) => !o)} aria-expanded={exportOpen}>Export</button>
            {exportOpen && artifact && (
              <div className="v3-new-menu v3-ws-version-menu">
                <button type="button" className="v3-ws-version" onClick={() => { setExportOpen(false); window.print(); }}><b>PDF</b><span>Print or save the full brief</span></button>
                <a className="v3-ws-version" href={artifactCsvUrl(artifact.id)} onClick={() => setExportOpen(false)}><b>CSV</b><span>One row per field, for spreadsheets</span></a>
                <button type="button" className="v3-ws-version" onClick={exportJson}><b>JSON</b><span>Machine-readable, for other systems</span></button>
              </div>
            )}
          </span>
          {HANDOFF[agentId] && (
            <span className="v3-ws-versions">
              <button type="button" disabled={!campaignId} onClick={() => setSendOpen((o) => !o)} aria-expanded={sendOpen}>Send to</button>
              {sendOpen && (
                <div className="v3-new-menu v3-ws-version-menu">
                  {HANDOFF[agentId].map((h) => (
                    <a key={h.id} className="v3-ws-version" href={handoffHref(h.id)} onClick={() => setSendOpen(false)}>
                      <b>{h.label}</b><span>{REGISTRY.find((a) => a.id === h.id)?.name} · same campaign</span>
                    </a>
                  ))}
                </div>
              )}
            </span>
          )}
          <button type="button" className="v3-ws-refine-btn" disabled={!artifact} onClick={() => setRefineOpen((o) => !o)} aria-pressed={refineOpen}>
            <Icon name="sparkles" size={13} /> Refine
          </button>
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

            {seededFrom !== null && !artifact && (
              <p className="v3-ws-seeded"><Icon name="check" size={12} /> Pre-filled from this campaign's plan (v{seededFrom}). Review, then Generate.</p>
            )}
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
            <button type="button" disabled={!form || missingAsks.length > 0 || busy} onClick={generate}>
              {busy ? "Generating…" : artifact ? "Regenerate" : "Generate"}
            </button>
            {genError && <span className="v3-ask-error">{genError}</span>}
            {form && missingAsks.length > 0 && <span>Answer {missingAsks.length} required question{missingAsks.length === 1 ? "" : "s"} to generate</span>}
          </div>
        </aside>

        <section className="v3-ws-output">
          {viewing && artifact ? (
            <>
              <div className="v3-ws-viewing">
                <span>Viewing <b>v{viewing.version}</b> ({viewing.version_reason}). Highlighted fields differ from the current v{artifact.version}.</span>
                <button type="button" onClick={restoreViewing}>Restore this version</button>
                <button type="button" className="ghost" onClick={() => setViewing(null)}>Back to current</button>
              </div>
              <ArtifactViewer art={viewing} readOnly compareTo={artifact} onEdit={onEdit} />
            </>
          ) : artifact ? (
            <>
              {(check || checkError) && (
                <div className={`v3-check ${checkError ? "error" : check && check.issues.length ? "issues" : "clean"}`}>
                  <div className="v3-check-head">
                    <b>{checkError ? "Couldn't check guidelines" : check!.issues.length ? `${check!.issues.length} guideline issue${check!.issues.length === 1 ? "" : "s"}` : "No guideline issues found"}</b>
                    <button type="button" aria-label="Dismiss" onClick={() => { setCheck(null); setCheckError(null); }}><Icon name="close" size={12} /></button>
                  </div>
                  <p>{checkError ?? check!.summary}</p>
                  {check?.issues.map((i, n) => (
                    <button key={n} type="button" className={`v3-check-item ${i.severity}`} onClick={() => setFocusField({ id: i.field_id, nonce: Date.now() })}>
                      <b>{i.label}</b><span>{i.issue}</span>
                    </button>
                  ))}
                  {check && check.needs_input.length > 0 && <p className="v3-check-note">{check.needs_input.length} field{check.needs_input.length === 1 ? "" : "s"} still need input and weren't checked.</p>}
                </div>
              )}
              <ArtifactViewer art={artifact} readOnly={false} compareTo={null} onEdit={onEdit} issues={check?.issues} focusField={focusField} diagramMarkup={diagramMarkup} />
            </>
          ) : (
            <div className="v3-ws-empty">
              <span className="v3-app-icon lg"><Icon name={agent.icon} size={22} /></span>
              <b>Your {noun.toLowerCase()} appears here</b>
              <p>Check the inputs on the left, answer anything marked required, then Generate.</p>
            </div>
          )}
        </section>
        {refineOpen && artifact && !viewing && artifact.type === "flow" && artifact.campaign_id && (
          <aside className="v3-refine" aria-label="Edit the flow">
            <div className="v3-refine-head">
              <b><Icon name="sparkles" size={14} /> Edit the flow</b>
              <button type="button" aria-label="Close" onClick={() => setRefineOpen(false)}><Icon name="close" size={13} /></button>
            </div>
            <div className="v3-refine-body v3-flow-edit">
              <FlowEditorChat campaignId={artifact.campaign_id} audience="HCP" onMarkup={setDiagramMarkup} embedded />
            </div>
          </aside>
        )}
        {refineOpen && artifact && !viewing && artifact.type !== "flow" && (
          <RefineDrawer artifact={artifact} onClose={() => setRefineOpen(false)}
            onApplied={(a) => { setArtifact(a); setCheck(null); }} />
        )}
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
