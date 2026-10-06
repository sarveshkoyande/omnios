import { useEffect, useMemo, useRef, useState } from "react";
import { ackSegmentation, getBrandTree, uploadAgentIntake, type AgentAck } from "../../api";
import { REGISTRY } from "../../agents";
import { Icon } from "../../components/Icon";
import type { BrandSummary, BrandTree } from "../../types";
import type { Favorite } from "../store";
import type { SegItem, SegState } from "./api";
import { AckCard, CommandBar, ReasoningButton, ReasoningPanel, type ReasonEntry } from "../agentkit/AgentKit";
import "../agentkit/agentkit.css";
import { SegConversation } from "./Conversation";
import { CreatedList, CreatedSegmentCard, DatasetView, PendingSegment, downloadText } from "./SegmentPanel";
import { useSegmentationPlanner } from "./useSegmentationPlanner";
import "../campaignplanner/campaignPlanner.css";
import "./segmentation.css";

/** The Segmentation Planner (Cockpit v3 "segmentation-planner"): Camille's Segmentation Agent
 *  in the Cockpit's workspace layout -- the conversation on the left (the request, the consent
 *  question, the generated SQL, the name, the size and the confirmation), the segment's
 *  definition, the segments created and the dataset on the right. Scoped to a brand and
 *  campaign like every workspace; the backend is strategy/segmentation. */

const STAGES = ["Understand the audience", "Consent & rules", "Build & size", "Create & publish"];
// Camille's welcome examples named data the dataset doesn't have (cardiologists, New York);
// these use its real values.
const EXAMPLES = [
  "Hematology/Oncology HCPs in Florida with decile 8 or higher",
  "Internal Medicine HCPs not engaged in the last 90 days who allow rep contact",
  "Low Awareness HCPs who prefer Email and have an engagement score above 10",
];
type Handoff = { brand: string; planId: number | null; campaignId: number | null };
type Tab = "segment" | "created" | "dataset";

function stepIndex(st: SegState, runningKind: string | null): number {
  if (runningKind === "create") return 3;
  if (runningKind === "estimate" || runningKind === "generate") return 2;
  if (st.items[st.items.length - 1]?.kind === "success") return STAGES.length;
  if (st.stage === "confirm") return 3;
  if (st.stage === "naming") return 2;
  if (st.stage === "consent") return 1;
  return 0;
}

/** Which of the four steps each conversation item belongs to, so the left side shows only the
 *  current step's cards (finished steps collapse to one row each). */
function itemSteps(items: SegItem[]): number[] {
  let seenCount = false;
  return items.map((it) => {
    switch (it.kind) {
      case "user": return 0;
      case "consent": return 1;
      case "sql": case "name": return 2;
      case "count": seenCount = true; return 2;
      case "success": return 3;
      case "progress": return seenCount ? 3 : 2;
      default: return 2;
    }
  });
}

export function SegmentationPlanner({ handoff, brands, activeBrand, isFavorite, toggleFavorite }: {
  handoff?: Handoff;
  brands: BrandSummary[];
  activeBrand: string | null;
  isFavorite: (type: Favorite["type"], id: string) => boolean;
  toggleFavorite: (fav: Favorite) => void;
}) {
  const agent = REGISTRY.find((a) => a.id === "segmentation-planner");
  const planner = useSegmentationPlanner();
  const { session, running } = planner;
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
  useEffect(() => { if (!brand && !handoff && brands.length) setBrand(activeBrand ?? brands[0].brand); }, [brand, brands, activeBrand, handoff]);
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
  const [composer, setComposer] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [audienceText, setAudienceText] = useState("");
  const [ack, setAck] = useState<(AgentAck & { audience?: string }) | null>(null);
  const [audience, setAudience] = useState("");
  const [reading, setReading] = useState(false);
  const [ackError, setAckError] = useState<string | null>(null);
  const [showReasoning, setShowReasoning] = useState(false);
  const [tab, setTab] = useState<Tab>("segment");
  const [exportOpen, setExportOpen] = useState(false);
  const threadEnd = useRef<HTMLDivElement>(null);
  const composerRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { setComposer(""); setTab("segment"); setAck(null); setFiles([]); setAudienceText(""); }, [session?.id]);
  // Follow the work: the segment tab whenever a definition appears or a segment is created.
  const pendingSql = st?.pending?.sql_item;
  const created = st?.segments.length ?? 0;
  useEffect(() => { if (pendingSql) setTab("segment"); }, [pendingSql]);
  useEffect(() => { if (created) setTab("segment"); }, [created]);
  const itemCount = st?.items.length ?? 0;
  useEffect(() => { threadEnd.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [itemCount, planner.jobError]);

  const busy = Boolean(running);
  const llmOn = session?.llm.available ?? false;
  const dcOn = session?.datacloud.configured ?? false;
  const stepIdx = st ? stepIndex(st, running?.kind ?? null) : 0;
  const fav = agent ? isFavorite("app", agent.id) : false;
  const latest = st?.segments[0] ?? null;
  const exportSql = st?.pending?.sql ?? latest?.sql ?? null;
  const exportName = st?.pending ? (st.pending.name || st.pending.segmentName) : latest?.segmentName ?? "segment";

  const readIntake = async () => {
    if (!brand) return;
    setReading(true); setAckError(null);
    try {
      await uploadAgentIntake("segmentation-planner", brand, files, audienceText);
      const a = await ackSegmentation(brand, audienceText);
      setAck(a);
      setAudience(a.audience || audienceText);
    } catch (e) {
      setAckError(e instanceof Error ? e.message : String(e));
    } finally {
      setReading(false);
    }
  };
  const confirmAudience = () => {
    const t = audience.trim();
    if (!t) return;
    planner.query(t).then((ok) => { if (ok) setAck(null); });
  };

  const items = st?.items ?? [];
  const steps = itemSteps(items);
  const shownStep = Math.min(stepIdx, STAGES.length - 1);
  const currentItems = items.filter((_, i) => steps[i] === shownStep);
  const stepSummary = (i: number): string => {
    if (i === 0) return items.find((x) => x.kind === "user")?.kind === "user" ? (items.find((x) => x.kind === "user") as { text: string }).text : "";
    if (i === 1) { const c = items.find((x) => x.kind === "consent"); return c && c.kind === "consent" ? (c.answered?.length ? c.answered.join(", ") : "No consent filter") : ""; }
    if (i === 2) { const c = [...items].reverse().find((x) => x.kind === "count"); return c && c.kind === "count" && c.count != null ? `${c.count.toLocaleString()} HCPs` : ""; }
    return "";
  };
  const entries: ReasonEntry[] = [];
  if (ack) entries.push({ id: "ack", title: "Understanding the audience", status: "done", lines: [ack.understood ?? "", ...(ack.approach ?? [])].filter(Boolean) });
  items.forEach((it) => {
    if (it.kind === "progress") entries.push({ id: it.id, title: it.title, status: it.status === "running" ? "running" : "done", lines: it.steps.map((x) => `${x.title}${x.details ? ` — ${x.details}` : ""}`) });
    if (it.kind === "sql") entries.push({ id: it.id, title: `SQL for “${it.segmentName}”`, status: "done", lines: [it.explanation, ...it.problems, ...(it.warnings ?? [])].filter(Boolean) });
    if (it.kind === "count") entries.push({ id: it.id, title: "Sizing the segment", status: "done", lines: [it.count != null ? `${it.count.toLocaleString()} HCPs match.` : "No count.", it.note ?? ""].filter(Boolean) });
  });

  const saveTitle = () => {
    if (session && title.trim() && title.trim() !== session.title) planner.rename(title.trim());
  };
  const send = () => {
    if (!st || busy) return;
    const t = composer.trim();
    if (st.stage === "naming") {
      planner.name(t).then((ok) => { if (ok) setComposer(""); });
    } else if (st.stage === "ready" && t) {
      planner.query(t).then((ok) => { if (ok) setComposer(""); });
    }
  };
  const pickValue = (v: string) => {
    setComposer((c) => (c.trim() ? `${c.trim()} ${v}` : v));
    composerRef.current?.focus();
  };

  const hint = useMemo(() => {
    if (!st) return "";
    if (busy) return running?.kind === "create" ? "Creating the segment in Salesforce Data Cloud…" : "The Segmentation Agent is working…";
    if (st.stage === "consent") return "Select the consent statuses above, or skip the consent filter.";
    if (st.stage === "confirm") return "Confirm the segment above to create it.";
    return "";
  }, [st, busy, running?.kind]);

  if (!agent) return <p className="v3-muted">The Segmentation Agent isn't registered.</p>;

  return (
    <div className="v3-ws v3-cc v3-seg">
      <div className="v3-ws-top">
        <input className="v3-ws-title" value={title} aria-label="Title" disabled={!session}
          onChange={(e) => setTitle(e.target.value)} onBlur={saveTitle}
          onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }} />
        <span className="v3-ws-save">
          {busy ? <><span className="v3-cc-spinner small" /> Working…</>
            : created ? <><Icon name="check" size={13} /> {created} segment{created === 1 ? "" : "s"} created</>
              : <><Icon name="document" size={13} /> Not started</>}
        </span>
        <span className="v3-ws-top-actions">
          <span className="v3-ws-versions">
            <button type="button" disabled={!exportSql && !created} onClick={() => setExportOpen((o) => !o)} aria-expanded={exportOpen}>Export</button>
            {exportOpen && (
              <div className="v3-new-menu v3-ws-version-menu">
                {exportSql && (
                  <button type="button" className="v3-ws-version" onClick={() => { setExportOpen(false); downloadText(`${exportName.replace(/[^A-Za-z0-9]+/g, "-").toLowerCase()}.sql`, exportSql + "\n", "application/sql"); }}>
                    <b>Segment SQL · .sql</b><span>{st?.pending ? "The segment being defined" : "The last segment created"}</span>
                  </button>
                )}
                {created > 0 && st && (
                  <button type="button" className="v3-ws-version" onClick={() => { setExportOpen(false); downloadText("segments.json", JSON.stringify(st.segments, null, 2), "application/json"); }}>
                    <b>Created segments · JSON</b><span>IDs, names, SQL and links</span>
                  </button>
                )}
              </div>
            )}
          </span>
          <ReasoningButton live={busy || reading} onClick={() => setShowReasoning((v) => !v)} />
          <button type="button" disabled={!st || !st.items.length || running?.kind === "create"}
            onClick={() => { if (window.confirm("Start over? This clears the conversation. Segments already created in Data Cloud stay listed.")) planner.reset(); }}>
            Start over
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
                  <p className="v3-ws-note">Segments are built on the Data Cloud data model object for every brand in it; this setting only decides which workspace the conversation is saved in.</p>
                </div>
              )}
            </section>

            <ol className="v3-cc-stepper" aria-label="Segment workflow progress">
              {STAGES.map((s, i) => (
                <li key={s} className={i < stepIdx ? "done" : i === stepIdx ? "active" : ""}>
                  <span>{i < stepIdx ? <Icon name="check" size={9} /> : i + 1}</span>{s}
                </li>
              ))}
            </ol>

            {session && !llmOn && (
              <p className="v3-cc-banner info">No AI model is configured on this server, so the planner can't write SQL. Configure the model and try again — Omni doesn't build SQL from keywords.</p>
            )}
            {session && session.datacloud.mode === "local" && (
              <p className="v3-cc-banner info">Data Cloud isn't connected, so segments are sized and created against a generated local copy of the HCP table (synthetic rows with the real columns and values). Set the DC_* settings to use your org.</p>
            )}
            {session && !dcOn && (
              <p className="v3-cc-banner warn">Data Cloud isn't connected on this server: the planner writes the SQL, but can't size or create segments. Set the DC_* settings to connect it.</p>
            )}
            {planner.loadError && <p className="v3-cc-banner error">Couldn't open the Segmentation Agent: {planner.loadError}</p>}
            {!session && !planner.loadError && <p className="v3-muted">{brands.length ? "Opening the Segmentation Agent…" : "Add a brand first: the Segmentation Agent works inside a brand."}</p>}

            {st && !st.items.length && !busy ? (
              ack ? (
                <>
                  <AckCard ack={ack} onConfirm={confirmAudience} onEdit={() => setAck(null)} />
                  <label className="v3-glass-label" htmlFor="seg-audience">The audience the agent will build (edit if needed)</label>
                  <textarea id="seg-audience" className="v3-glass-text" rows={3} value={audience} onChange={(e) => setAudience(e.target.value)} />
                </>
              ) : (
                <section className="v3-ak-intake v3-seg-welcome">
                  <CommandBar brand={brand} value={audienceText} setValue={setAudienceText} files={files} setFiles={setFiles}
                    onGo={readIntake} busy={reading} busyLabel="Reading…" goLabel="Build segment"
                    placeholder="Who should be in the segment? Leave empty and the agent proposes one from Brand IQ." />
                  <div className="v3-cmd-examples">
                    {EXAMPLES.map((e) => <button key={e} type="button" disabled={reading} onClick={() => setAudienceText(e)}>{e}</button>)}
                  </div>
                  {ackError && <p className="v3-cc-banner error">{ackError}</p>}
                </section>
              )
            ) : st && (
              <div className="v3-ak-progress">
                {STAGES.slice(0, shownStep).map((name, i) => (
                  <div key={name} className="v3-ak-row done">
                    <span className="v3-ak-dot"><Icon name="check" size={9} /></span><b>{name}</b>
                    {stepSummary(i) && <small className="v3-seg-row-sum">{stepSummary(i)}</small>}
                  </div>
                ))}
                <div className={`v3-ak-row ${stepIdx >= STAGES.length ? "done" : "current"}`}>
                  <div className="v3-ak-row-head">
                    <span className="v3-ak-dot">{stepIdx >= STAGES.length ? <Icon name="check" size={9} /> : busy ? <span className="v3-cc-spinner small" /> : shownStep + 1}</span>
                    <b>{STAGES[shownStep]}</b>
                  </div>
                  <SegConversation items={currentItems} liveIds={planner.liveIds} busy={busy}
                    onConsent={(values) => { planner.consent(values); }}
                    onCreate={() => { planner.create(); }}
                    onDiscard={() => { planner.discard(); }} />
                </div>
              </div>
            )}
            {busy && st && !st.items.some((i) => planner.liveIds.has(i.id) && i.kind === "progress") && (
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

          {st && (st.items.length > 0 || busy) && (
            <div className="v3-cc-composer">
              {hint ? (
                <div className="v3-cc-composer-hint">
                  <span>{hint}</span>
                  {busy && running?.kind !== "create" && <button type="button" className="v3-link" onClick={() => { planner.cancel(); }}>Stop</button>}
                  {!busy && st.stage === "consent" && <button type="button" className="v3-link" onClick={() => { planner.discard(); }}>Discard</button>}
                </div>
              ) : (
                <form onSubmit={(e) => { e.preventDefault(); send(); }}>
                  <textarea ref={composerRef} rows={2} value={composer} disabled={busy}
                    placeholder={st.stage === "naming" ? "Enter segment name…" : "Describe the audience segment you want to create…"}
                    onChange={(e) => setComposer(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} />
                  {st.stage === "naming" && st.pending && (
                    <button type="button" className="v3-cc-btn v3-seg-suggest" disabled={busy} onClick={() => setComposer(st.pending?.segmentName ?? "")}>Use suggested</button>
                  )}
                  <button type="submit" disabled={busy || (st.stage === "ready" && !composer.trim())}>Send</button>
                </form>
              )}
              {!hint && st.stage === "naming" && (
                <div className="v3-cc-composer-hint v3-seg-subhint">
                  <span>Name the segment, or press Enter to use the suggested name.</span>
                  <button type="button" className="v3-link" onClick={() => { planner.discard(); }}>Discard</button>
                </div>
              )}
            </div>
          )}
        </aside>

        <section className="v3-ws-output v3-seg-out">
          <div className="v3-cc-out">
            <div className="v3-av-tabs" role="tablist">
              <button type="button" role="tab" aria-selected={tab === "segment"} className={tab === "segment" ? "active" : ""} onClick={() => setTab("segment")}>Segment</button>
              <button type="button" role="tab" aria-selected={tab === "created"} className={tab === "created" ? "active" : ""} onClick={() => setTab("created")}>
                Created segments{created ? ` (${created})` : ""}
              </button>
              <button type="button" role="tab" aria-selected={tab === "dataset"} className={tab === "dataset" ? "active" : ""} onClick={() => setTab("dataset")}>Dataset</button>
            </div>

            {tab === "segment" && (
              st?.pending ? <PendingSegment p={st.pending} engine={session?.llm.engine ?? ""} />
                : latest ? (
                  <div className="v3-cc-bp">
                    <header className="v3-cc-bp-head">
                      <div><span className="v3-cc-eyebrow">Last segment created</span><h1>{latest.segmentName}</h1></div>
                      <span className="v3-cc-chip ok">Created in Data Cloud</span>
                    </header>
                    <CreatedSegmentCard seg={latest} open onToggle={() => setTab("created")} />
                  </div>
                ) : (
                  <div className="v3-ws-empty">
                    <span className="v3-app-icon lg"><Icon name={agent.icon} size={22} /></span>
                    <b>Your segment appears here</b>
                    <p>{st?.stage === "consent" ? "Choose the email consent statuses on the left and the agent writes the SQL."
                      : "Describe the audience on the left. The agent writes Salesforce Data Cloud SQL for it, sizes it, and creates the segment when you confirm. See the Dataset tab for everything you can segment on."}</p>
                  </div>
                )
            )}
            {tab === "created" && <CreatedList segments={st?.segments ?? []} />}
            {tab === "dataset" && (
              <DatasetView dataset={planner.dataset} busy={planner.datasetBusy} canRefresh={dcOn}
                onRefresh={() => planner.loadDataset(true)}
                onPick={(v) => { if (st?.stage === "ready" && !busy) pickValue(v); }} />
            )}
          </div>
        </section>
        {showReasoning && <ReasoningPanel entries={entries} live={busy || reading} onClose={() => setShowReasoning(false)} />}
      </div>
    </div>
  );
}
