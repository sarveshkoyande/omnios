import { useEffect, useMemo, useRef, useState } from "react";
import { getBrandTree } from "../../api";
import { REGISTRY } from "../../agents";
import { Icon } from "../../components/Icon";
import type { BrandSummary, BrandTree } from "../../types";
import type { Favorite } from "../store";
import type { SegState } from "./api";
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

const STAGES = ["Describe", "Consent", "SQL", "Name", "Size", "Create"];
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
  if (runningKind === "create") return 5;
  if (runningKind === "estimate") return 4;
  if (runningKind === "generate") return 2;
  if (st.stage === "confirm") return 5;
  if (st.stage === "naming") return 3;
  if (st.stage === "consent") return 1;
  return st.items[st.items.length - 1]?.kind === "success" ? STAGES.length : 0;
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
  const [tab, setTab] = useState<Tab>("segment");
  const [exportOpen, setExportOpen] = useState(false);
  const threadEnd = useRef<HTMLDivElement>(null);
  const composerRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { setComposer(""); setTab("segment"); }, [session?.id]);
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

  if (!agent) return <p className="v3-muted">The Segmentation Planner isn't registered.</p>;

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
              <p className="v3-cc-banner info">No AI model is configured on this server, so the SQL is built by rules from the exact dataset values your request names.</p>
            )}
            {session && !dcOn && (
              <p className="v3-cc-banner warn">Data Cloud isn't connected on this server: the planner writes the SQL, but can't size or create segments. Set the DC_* settings to connect it.</p>
            )}
            {planner.loadError && <p className="v3-cc-banner error">Couldn't open the Segmentation Planner: {planner.loadError}</p>}
            {!session && !planner.loadError && <p className="v3-muted">{brands.length ? "Opening the Segmentation Planner…" : "Add a brand first: the Segmentation Planner works inside a brand."}</p>}

            {st && !st.items.length && !busy ? (
              <section className="v3-cc-intake v3-seg-welcome">
                <div className="v3-cc-intake-head">
                  <b>Create a Data Cloud segment</b>
                  <span>Describe your target audience in plain English. The agent asks which email consent statuses to include, writes the Data Cloud SQL, sizes the segment and creates it once you confirm.</span>
                </div>
                <span className="v3-cc-hint">Try asking:</span>
                {EXAMPLES.map((e) => (
                  <button key={e} type="button" className="v3-seg-example" onClick={() => { setComposer(e); composerRef.current?.focus(); }}>“{e}”</button>
                ))}
              </section>
            ) : st && (
              <SegConversation items={st.items} liveIds={planner.liveIds} busy={busy}
                onConsent={(values) => { planner.consent(values); }}
                onCreate={() => { planner.create(); }}
                onDiscard={() => { planner.discard(); }} />
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

          {st && (
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

        <section className="v3-ws-output">
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
      </div>
    </div>
  );
}
