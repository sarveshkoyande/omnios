import { useEffect, useMemo, useRef, useState } from "react";
import { getArtifact, getBrandTree } from "../../api";
import { REGISTRY } from "../../agents";
import { Icon } from "../../components/Icon";
import { GlassDrop } from "../agentkit/AgentKit";
import type { BrandSummary, BrandTree } from "../../types";
import type { Favorite } from "../store";
import { ccApi, sfApi, type Briefing, type CCItem, type CCState } from "./api";
import { Blueprint, DeployPanel } from "./Blueprint";
import { BriefingDocument } from "./BriefingDocument";
import { Conversation } from "./Conversation";
import { MermaidView } from "./MermaidView";
import { ReasoningDrawer } from "./Pipeline";
import { useCampaignPlanner } from "./useCampaignPlanner";
import "./campaignPlanner.css";

/** The Briefing Agent (Cockpit v3 "briefing-agent"; was "campaign-planner" in MR !1): Camille's create-campaign flow in the
 *  Cockpit's workspace layout -- the conversation with the agents on the left (intake,
 *  clarifying questions, assumption review, the blueprint agents at work), the Campaign
 *  Briefing Document and the Journey Blueprint on the right. Scoped to a brand, engagement
 *  plan and campaign like every workspace; the backend is strategy/campaign_creator. */

const HANDOFF = [{ id: "flow-planner", label: "Build the flow" }, { id: "brief-compiler", label: "Compile the brief" }];
const STAGES = ["Intake", "Clarification", "Campaign brief", "Blueprint", "Deployment", "Salesforce"];
type Handoff = { brand: string; planId: number | null; campaignId: number | null };
type Tab = "brief" | "blueprint";

function stageIndex(st: CCState, runningKind: string | null): number {
  if (st.deployment?.status === "succeeded") return 5;
  if (st.deployment || runningKind === "deploy") return 4;
  if (st.stage === "blueprint" || runningKind === "blueprint") return 3;
  if (st.stage === "briefing") return 2;
  if (st.stage === "clarifying" || st.stage === "assumptions") return 1;
  return 0;
}

function saveBlob(name: string, data: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function IntakePanel({ text, setText, file, setFile, autoAssume, setAutoAssume, disabled, onAnalyze }: {
  text: string; setText: (v: string) => void; file: File | null; setFile: (f: File | null) => void;
  autoAssume: boolean; setAutoAssume: (v: boolean) => void; disabled: boolean; onAnalyze: () => void;
}) {
  return (
    <section className="v3-ak-intake">
      <div className="v3-cc-intake-head">
        <b>Campaign intake</b>
        <span>Upload the campaign brief or paste the details to begin the analysis.</span>
      </div>
      <GlassDrop files={file ? [file] : []} setFiles={(f) => setFile(f[0] ?? null)} notes={text} setNotes={setText} multiple={false} disabled={disabled}
        notesLabel={`Campaign details${file ? " (optional instructions for the document)" : ""}`}
        placeholder="Describe your campaign objectives, target audience, and journey requirements…"
        hint="Include the brand, product, therapeutic area, objective, target market and the day-by-day journey for the most accurate briefing." />
      <label className="v3-cc-toggle">
        <input type="checkbox" checked={autoAssume} disabled={disabled} onChange={(e) => setAutoAssume(e.target.checked)} />
        <span><b>Auto-assume</b> — let the agent fill gaps with sensible defaults and skip clarifying questions</span>
      </label>
      <button type="button" className="v3-cc-btn primary wide" disabled={disabled || (!text.trim() && !file)} onClick={onAnalyze}>
        Analyze campaign
      </button>
    </section>
  );
}

export function CampaignPlanner({ artifactId, handoff, brands, activeBrand, isFavorite, toggleFavorite }: {
  artifactId?: string;
  handoff?: Handoff;
  brands: BrandSummary[];
  activeBrand: string | null;
  isFavorite: (type: Favorite["type"], id: string) => boolean;
  toggleFavorite: (fav: Favorite) => void;
}) {
  const agent = REGISTRY.find((a) => a.id === "briefing-agent");
  const planner = useCampaignPlanner();
  const { session, running, sf } = planner;
  const st = session?.state ?? null;

  // ---- scope (same selection model as the other agent workspaces)
  const [brand, setBrand] = useState<string | null>(activeBrand);
  const [tree, setTree] = useState<BrandTree | null>(null);
  const [planId, setPlanId] = useState<number | null>(null);
  const [campaignId, setCampaignId] = useState<number | null>(null);
  const [scopeReady, setScopeReady] = useState(false);
  const pendingSelection = useRef<{ planId: number | null; campaignId: number | null } | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);

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
  useEffect(() => { if (!brand && !artifactId && !handoff && brands.length) setBrand(activeBrand ?? brands[0].brand); }, [brand, brands, activeBrand, artifactId, handoff]);
  useEffect(() => {
    if (!brand) return;
    let live = true;
    setScopeReady(false);
    setTree(null);
    getBrandTree(brand).then((t) => {
      if (!live) return;
      setTree(t);
      const pending = pendingSelection.current;
      pendingSelection.current = null;
      if (pending) { setPlanId(pending.planId); setCampaignId(pending.campaignId); }
      else {
        const plan = t.engagement_plans.find((p) => p.campaigns.length) ?? t.engagement_plans[0];
        setPlanId(plan?.id ?? null);
        setCampaignId(plan?.campaigns[0]?.id ?? null);
      }
      setScopeReady(true);
    }).catch(() => { if (live) { setTree({ brand, engagement_plans: [] }); setPlanId(null); setCampaignId(null); setScopeReady(true); } });
    return () => { live = false; };
  }, [brand]);
  const { openScope } = planner;
  useEffect(() => {
    if (scopeReady && brand) openScope({ brand, planId, campaignId });
  }, [scopeReady, brand, planId, campaignId, openScope]);

  const plan = tree?.engagement_plans.find((p) => p.id === planId) ?? null;
  const campaign = plan?.campaigns.find((c) => c.id === campaignId) ?? null;
  const territory = brands.find((b) => b.brand === brand)?.territories[0] ?? null;

  // ---- page state
  const [title, setTitle] = useState("");
  useEffect(() => { setTitle(session?.title ?? ""); }, [session?.id, session?.title]);
  const [intakeText, setIntakeText] = useState("");
  const [intakeFile, setIntakeFile] = useState<File | null>(null);
  const [autoAssume, setAutoAssume] = useState(false);
  const [composer, setComposer] = useState("");
  const [tab, setTab] = useState<Tab>("brief");
  const [changeOpen, setChangeOpen] = useState(false);
  const [changeText, setChangeText] = useState("");
  const [reasoningFor, setReasoningFor] = useState<string | null>(null);
  const [versionsOpen, setVersionsOpen] = useState(false);
  const [versionList, setVersionList] = useState<{ version: number; created_at: string; reason: string }[]>([]);
  const [viewing, setViewing] = useState<{ version: number; briefing: Briefing } | null>(null);
  const [exportOpen, setExportOpen] = useState(false);
  const [sendOpen, setSendOpen] = useState(false);
  const threadEnd = useRef<HTMLDivElement>(null);

  // A new scope starts clean.
  useEffect(() => {
    setIntakeText(""); setIntakeFile(null); setComposer(""); setViewing(null); setReasoningFor(null); setChangeOpen(false);
    setTab("brief");
  }, [session?.id]);
  // The intake leaves the screen once the brief exists; clear what was typed for it.
  const stage = st?.stage;
  useEffect(() => { if (stage && stage !== "intake") { setIntakeText(""); setIntakeFile(null); } }, [stage]);
  // Follow the work: the journey tab while the agents build it, the brief when a new version lands.
  useEffect(() => { if (running?.kind === "blueprint") setTab("blueprint"); }, [running?.kind, running?.jobId]);
  const briefingVersion = st?.briefing_version;
  useEffect(() => { if (briefingVersion) { setTab("brief"); setViewing(null); } }, [briefingVersion]);
  const itemCount = st?.items.length ?? 0;
  useEffect(() => { threadEnd.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [itemCount, planner.jobError]);

  const busy = Boolean(running);
  const llmOn = session?.llm.available ?? false;
  const pipelineItems = (st?.items ?? []).filter((i): i is Extract<CCItem, { kind: "pipeline" }> => i.kind === "pipeline");
  const livePipeline = running?.kind === "blueprint" ? pipelineItems[pipelineItems.length - 1] : undefined;
  const reasoningItem = pipelineItems.find((p) => p.id === reasoningFor) ?? null;
  const stepIdx = st ? stageIndex(st, running?.kind ?? null) : 0;
  const fav = agent ? isFavorite("app", agent.id) : false;
  const handoffHref = (to: string) => `#/v3/agent/${to}/for/${encodeURIComponent(brand ?? "")}/${planId ?? 0}/${campaignId ?? 0}`;
  const returnTo = `/#/v3/agent/briefing-agent/for/${encodeURIComponent(brand ?? "")}/${planId ?? 0}/${campaignId ?? 0}`;
  const liveIds = planner.liveIds;

  const saveTitle = () => {
    if (session && title.trim() && title.trim() !== session.title) planner.rename(title.trim());
  };
  const sendComposer = () => {
    const t = composer.trim();
    if (!t || busy || !st) return;
    const go = st.stage === "blueprint" ? planner.buildBlueprint(t) : planner.updateBriefing(t);
    go.then((ok) => { if (ok) setComposer(""); });
  };
  const toggleVersions = () => {
    if (!session) return;
    if (!versionsOpen) ccApi.briefingVersions(session.id).then((r) => setVersionList(r.versions)).catch(() => setVersionList([]));
    setVersionsOpen((o) => !o);
  };
  const viewVersion = (v: number) => {
    if (!session || !st) return;
    setVersionsOpen(false);
    setTab("brief");
    if (v === st.briefing_version) { setViewing(null); return; }
    ccApi.briefingVersion(session.id, v).then(setViewing).catch(() => undefined);
  };

  const composerHint = useMemo(() => {
    if (!st) return "";
    if (busy) return running?.kind === "deploy" ? "Deploying to Salesforce…" : "The agents are working…";
    if (st.stage === "clarifying") return "Answer the clarification questions above to continue.";
    if (st.stage === "assumptions") return "Review the assumptions above to continue.";
    return "";
  }, [st, busy, running?.kind]);

  if (!agent) return <p className="v3-muted">The Campaign Planner isn't registered.</p>;

  return (
    <div className="v3-ws v3-cc">
      <div className="v3-ws-top">
        <input className="v3-ws-title" value={title} aria-label="Title" disabled={!session}
          onChange={(e) => setTitle(e.target.value)} onBlur={saveTitle}
          onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }} />
        <span className="v3-ws-save">
          {busy ? <><span className="v3-cc-spinner small" /> Working…</>
            : st?.briefing ? <><Icon name="check" size={13} /> Saved · brief v{st.briefing_version}</>
              : <><Icon name="document" size={13} /> Not started</>}
        </span>
        <span className="v3-ws-top-actions">
          <span className="v3-ws-versions">
            <button type="button" disabled={!st?.briefing} onClick={toggleVersions} aria-expanded={versionsOpen}>Version history</button>
            {versionsOpen && (
              <div className="v3-new-menu v3-ws-version-menu">
                {versionList.map((v) => (
                  <button key={v.version} type="button" className={`v3-ws-version ${(viewing?.version ?? st?.briefing_version) === v.version ? "active" : ""}`}
                    onClick={() => viewVersion(v.version)}>
                    <b>v{v.version}{v.version === st?.briefing_version ? " · current" : ""}</b>
                    <span>{v.reason}</span>
                    <em>{new Date(v.created_at).toLocaleString()}</em>
                  </button>
                ))}
              </div>
            )}
          </span>
          <span className="v3-ws-versions">
            <button type="button" disabled={!st?.briefing || !session} onClick={() => setExportOpen((o) => !o)} aria-expanded={exportOpen}>Export</button>
            {exportOpen && session && st?.briefing && (
              <div className="v3-new-menu v3-ws-version-menu">
                <a className="v3-ws-version" href={ccApi.exportUrl(session.id, "pdf")} onClick={() => setExportOpen(false)}><b>Briefing · PDF</b><span>The Campaign Briefing Document</span></a>
                <a className="v3-ws-version" href={ccApi.exportUrl(session.id, "docx")} onClick={() => setExportOpen(false)}><b>Briefing · Word</b><span>Editable .docx</span></a>
                <button type="button" className="v3-ws-version" onClick={() => { setExportOpen(false); saveBlob(`${st.briefing!.campaignName || "briefing"} v${st.briefing_version}.json`, st.briefing); }}>
                  <b>Briefing · JSON</b><span>Machine-readable, for other systems</span></button>
                {st.spec && <a className="v3-ws-version" href={ccApi.packageUrl(session.id)} onClick={() => setExportOpen(false)}><b>Flow package · ZIP</b><span>package.xml + Flow metadata, deployable</span></a>}
                {st.blueprint && <button type="button" className="v3-ws-version" onClick={() => { setExportOpen(false); saveBlob("journey-blueprint.json", st.blueprint); }}>
                  <b>Blueprint · JSON</b><span>Spec, QA report, validation and docs</span></button>}
              </div>
            )}
          </span>
          <span className="v3-ws-versions">
            <button type="button" disabled={!campaignId} onClick={() => setSendOpen((o) => !o)} aria-expanded={sendOpen}>Send to</button>
            {sendOpen && (
              <div className="v3-new-menu v3-ws-version-menu">
                {HANDOFF.map((h) => (
                  <a key={h.id} className="v3-ws-version" href={handoffHref(h.id)} onClick={() => setSendOpen(false)}>
                    <b>{h.label}</b><span>{REGISTRY.find((a) => a.id === h.id)?.name} · same campaign</span>
                  </a>
                ))}
              </div>
            )}
          </span>
          <button type="button" disabled={!st || (st.stage === "intake" && !st.items.length)}
            onClick={() => { if (window.confirm("Start over? This clears the brief, the questions and the journey blueprint for this campaign.")) planner.reset(); }}>
            Start over
          </button>
          <button type="button" className="v3-ws-refine-btn" disabled={!st?.briefing || !llmOn || busy} aria-pressed={changeOpen}
            title={!llmOn ? "Changing the brief needs the AI model" : undefined} onClick={() => { setReasoningFor(null); setChangeOpen((o) => !o); }}>
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


            <section className={`v3-ws-settings ${settingsOpen ? "open" : ""}`}>
              <button type="button" className="v3-ws-settings-row" onClick={() => setSettingsOpen((o) => !o)} aria-expanded={settingsOpen}>
                <b>Settings</b>
                <span>{[brand, territory, plan?.name, campaign?.name].filter(Boolean).join(" · ") || "Choose a brand"}</span>
                <Icon name="chevronDown" size={13} />
              </button>
              {settingsOpen && (
                <div className="v3-ws-settings-grid">
                  <label>Brand
                    <select value={brand ?? ""} disabled={busy} onChange={(e) => setBrand(e.target.value)}>
                      {brands.map((b) => <option key={b.brand}>{b.brand}</option>)}
                    </select>
                  </label>
                  <label>Territory
                    <select value={territory ?? ""} disabled><option>{territory ?? "—"}</option></select>
                  </label>
                  <label>Engagement plan
                    <select value={planId ?? ""} disabled={busy} onChange={(e) => {
                      const p = tree?.engagement_plans.find((x) => x.id === Number(e.target.value));
                      setPlanId(p?.id ?? null); setCampaignId(p?.campaigns[0]?.id ?? null);
                    }}>
                      {(tree?.engagement_plans ?? []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                    </select>
                  </label>
                  <label>Campaign
                    <select value={campaignId ?? ""} disabled={busy} onChange={(e) => setCampaignId(Number(e.target.value))}>
                      {(plan?.campaigns ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                    </select>
                  </label>
                  {brand !== activeBrand && activeBrand && (
                    <p className="v3-ws-note">Using {brand} here only; your global brand is still {activeBrand}.</p>
                  )}
                </div>
              )}
            </section>

            <ol className="v3-cc-stepper" aria-label="Campaign workflow progress">
              {STAGES.map((s, i) => (
                <li key={s} className={i < stepIdx ? "done" : i === stepIdx ? "active" : ""}>
                  <span>{i < stepIdx ? <Icon name="check" size={9} /> : i + 1}</span>{s}
                </li>
              ))}
            </ol>

            {session && !llmOn && (
              <p className="v3-cc-banner info">No AI model is configured on this server, so the brief is assembled from your text by rules and the blueprint agents fall back to rules.</p>
            )}
            {planner.loadError && <p className="v3-cc-banner error">Couldn't open the Campaign Planner: {planner.loadError}</p>}
            {!session && !planner.loadError && <p className="v3-muted">{brands.length ? "Opening the Campaign Planner…" : "Add a brand first: the Campaign Planner works inside a brand."}</p>}

            {st && st.stage === "intake" && !st.items.length && !busy ? (
              <IntakePanel text={intakeText} setText={setIntakeText} file={intakeFile} setFile={setIntakeFile}
                autoAssume={autoAssume} setAutoAssume={setAutoAssume} disabled={busy}
                onAnalyze={() => planner.analyze(intakeText, intakeFile, autoAssume)} />
            ) : st && (
              <Conversation items={st.items} liveIds={liveIds} busy={busy}
                onAnswers={(t) => planner.answer(t)} onAcceptAssumptions={() => planner.acceptAssumptions()}
                onResolveAssumptions={(t) => planner.resolveAssumptions(t)}
                onOpenReasoning={(id) => { setChangeOpen(false); setReasoningFor(id); }} />
            )}
            {busy && !livePipeline && running?.kind !== "deploy" && st && !st.items.some((i) => liveIds.has(i.id) && i.kind === "progress") && (
              <div className="v3-ask-thinking"><span /><span /><span /></div>
            )}
            {planner.jobError && (
              <div className="v3-cc-banner error">
                <span>{planner.jobError}</span>
                <button type="button" aria-label="Dismiss" onClick={planner.clearError}><Icon name="close" size={11} /></button>
              </div>
            )}
            <div ref={threadEnd} />
          </div>

          {st && (busy || st.stage !== "intake" || st.items.length > 0) && (
            <div className="v3-cc-composer">
              {composerHint ? (
                <div className="v3-cc-composer-hint">
                  <span>{composerHint}</span>
                  {busy && running?.kind !== "deploy" && <button type="button" className="v3-link" onClick={planner.cancel}>Stop</button>}
                </div>
              ) : (st.stage === "briefing" || st.stage === "blueprint") && (
                <form onSubmit={(e) => { e.preventDefault(); sendComposer(); }}>
                  <textarea rows={2} value={composer} disabled={busy || (st.stage === "briefing" && !llmOn)}
                    placeholder={st.stage === "blueprint" ? "Describe a change to the journey…" : llmOn ? "Describe a change to the brief…" : "Changing the brief needs the AI model"}
                    onChange={(e) => setComposer(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendComposer(); } }} />
                  <button type="submit" disabled={busy || !composer.trim() || (st.stage === "briefing" && !llmOn)}>Send</button>
                </form>
              )}
            </div>
          )}
        </aside>

        <section className="v3-ws-output">
          {st?.briefing ? (
            <div className="v3-cc-out">
              <div className="v3-av-tabs" role="tablist">
                <button type="button" role="tab" aria-selected={tab === "brief"} className={tab === "brief" ? "active" : ""} onClick={() => setTab("brief")}>Campaign brief</button>
                <button type="button" role="tab" aria-selected={tab === "blueprint"} className={tab === "blueprint" ? "active" : ""}
                  disabled={!st.blueprint && running?.kind !== "blueprint"} onClick={() => setTab("blueprint")}>Journey blueprint</button>
              </div>

              {tab === "brief" && (
                <>
                  {viewing ? (
                    <div className="v3-ws-viewing">
                      <span>Viewing <b>v{viewing.version}</b>. The current brief is v{st.briefing_version}.</span>
                      <button type="button" disabled={busy} onClick={() => { planner.restoreBriefing(viewing.version); setViewing(null); }}>Restore this version</button>
                      <button type="button" className="ghost" onClick={() => setViewing(null)}>Back to current</button>
                    </div>
                  ) : st.briefing_note && <p className="v3-cc-banner warn">{st.briefing_note}</p>}
                  <BriefingDocument briefing={viewing?.briefing ?? st.briefing} version={viewing?.version ?? st.briefing_version} />
                  {!viewing && (
                    <div className="v3-cc-doc-actions">
                      <p>Review your Campaign Briefing Document. Download it, request changes, or proceed to journey blueprint generation.</p>
                      <div>
                        {session && <a className="v3-cc-btn" href={ccApi.exportUrl(session.id, "pdf")}>Download brief (PDF)</a>}
                        <button type="button" className="v3-cc-btn" disabled={busy || !llmOn} title={!llmOn ? "Changing the brief needs the AI model" : undefined}
                          onClick={() => { setReasoningFor(null); setChangeOpen(true); }}>Make changes</button>
                        <button type="button" className="v3-cc-btn primary" disabled={busy} onClick={() => { planner.buildBlueprint(); }}>
                          {st.blueprint ? "Regenerate journey" : "Proceed & generate journey"}
                        </button>
                      </div>
                    </div>
                  )}
                </>
              )}

              {tab === "blueprint" && (
                running?.kind === "blueprint" ? (
                  <div className="v3-cc-bp">
                    <header className="v3-cc-bp-head">
                      <div><span className="v3-cc-eyebrow">Generating</span><h1>Campaign Blueprint</h1></div>
                      <span className="v3-cc-chip"><span className="v3-cc-spinner small" /> Agents at work</span>
                    </header>
                    <p className="v3-cc-bp-meta">The agents are turning the approved brief into a Salesforce Flow spec and a journey diagram. Follow them on the left, or open Live reasoning.</p>
                    {livePipeline && (
                      <button type="button" className="v3-cc-reason-btn live" onClick={() => { setChangeOpen(false); setReasoningFor(livePipeline.id); }}>
                        <Icon name="eye" size={13} /> Live reasoning
                      </button>
                    )}
                    {planner.liveMermaid && <section className="v3-cc-bp-sec"><div className="v3-cc-bp-sec-head"><span><Icon name="branch" size={14} /></span><b>Journey Flow (draft)</b></div><MermaidView code={planner.liveMermaid} /></section>}
                  </div>
                ) : st.blueprint ? (
                  <Blueprint bp={st.blueprint} stale={st.blueprint_stale} onRegenerate={() => { planner.buildBlueprint(); }}
                    deploy={session && (
                      <DeployPanel canDeploy={Boolean(st.spec)} deploying={running?.kind === "deploy"} deployment={st.deployment} sf={sf}
                        packageUrl={ccApi.packageUrl(session.id)} onDeploy={() => { planner.deploy(); }}
                        onConnect={() => { window.location.href = sfApi.connectUrl(returnTo); }}
                        onDisconnect={planner.disconnectSf} />
                    )} />
                ) : (
                  <div className="v3-ws-empty"><b>No journey yet</b><p>Proceed from the brief to generate the journey blueprint.</p></div>
                )
              )}
            </div>
          ) : (
            <div className="v3-ws-empty">
              <span className="v3-app-icon lg"><Icon name={agent.icon} size={22} /></span>
              <b>Your Campaign Briefing Document appears here</b>
              <p>{st?.stage === "clarifying" ? "Answer the clarification questions on the left and the agent writes the brief."
                : st?.stage === "assumptions" ? "Confirm or override the assumptions on the left and the agent writes the brief."
                  : "Share the campaign brief on the left. The agent asks only about what's genuinely missing, writes the Campaign Briefing Document, then builds and deploys the Salesforce journey."}</p>
            </div>
          )}
        </section>

        {changeOpen && st?.briefing && (
          <aside className="v3-refine" aria-label="Change the brief">
            <div className="v3-refine-head">
              <b><Icon name="sparkles" size={14} /> Make changes to the brief</b>
              <button type="button" aria-label="Close" onClick={() => setChangeOpen(false)}><Icon name="close" size={13} /></button>
            </div>
            <div className="v3-refine-body">
              <p className="v3-muted">Describe any corrections, missing details or overrides. Only what you provide is used; the rest of the brief stays as it is. Each change saves a new version.</p>
              {running?.kind === "update" && <div className="v3-ask-thinking"><span /><span /><span /></div>}
            </div>
            <form className="v3-refine-compose" onSubmit={(e) => {
              e.preventDefault();
              const t = changeText.trim();
              if (t) planner.updateBriefing(t).then((ok) => { if (ok) setChangeText(""); });
            }}>
              <textarea rows={3} value={changeText} disabled={busy} placeholder="e.g. Update the primary channel to Email & SMS, change the indication to Type 2 Diabetes…"
                onChange={(e) => setChangeText(e.target.value)} />
              <button type="submit" disabled={busy || !changeText.trim()}>{running?.kind === "update" ? "Updating…" : "Apply"}</button>
            </form>
          </aside>
        )}
        {reasoningItem && (
          <ReasoningDrawer item={reasoningItem} live={Boolean(running && liveIds.has(reasoningItem.id))} onClose={() => setReasoningFor(null)} />
        )}
      </div>
    </div>
  );
}
