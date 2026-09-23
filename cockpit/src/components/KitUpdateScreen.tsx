import { useEffect, useState } from "react";
import {
  askKitUpdate, generateRandomBrandPlan, getKitUpdateState, inferBrandName, ingestKitUpdate,
  publishKitUpdate, sampleKitPdfUrl, setupBrand,
} from "../api";
import {
  KIT_UPDATE_SECTIONS, KIT_UPDATE_SECTION_LABELS,
} from "../types";
import type { KitDraft, KitUpdateSection } from "../types";
import { DiffReview } from "./kitUpdate/DiffReview";
import { KitUpdateChat } from "./kitUpdate/KitUpdateChat";
import { Icon } from "./Icon";

const STATUS_LABEL: Record<KitDraft["status"], string> = {
  not_started: "Not started",
  drafting: "Drafting",
  awaiting_review: "Awaiting your review",
  published: "Published",
};

/** The guided brand-plan update screen (R1/R2/R6): five per-section tabs, each its own
 *  persisted chat + diff review, opened from any section's "Update" action and landing on
 *  the tab matching the section clicked from. On first open for a brand with no drafts
 *  yet, offers to ingest a sample or uploaded "Brand Plan" PDF (F1); on a later open it
 *  restores whatever each tab already has (F2).
 *
 *  `newBrand` folds the New Brand setup flow (naming + territory + first ingest) into
 *  this SAME screen instead of a separate full-page wizard: the ingest panel below grows
 *  a name field and territory pills when there's no brand yet, "Finish setup" creates the
 *  brand and seeds all five drafts in one call, and the screen then falls straight through
 *  into its normal five-tab view -- one continuous screen, not a handoff between two. */
export function KitUpdateScreen({ brand, initialSection, newBrand = false, knownTerritories = [], onClose, onBrandCreated }: {
  brand: string;
  initialSection: KitUpdateSection;
  newBrand?: boolean;
  knownTerritories?: string[];
  onClose: () => void;
  onBrandCreated?: (brand: string) => void;
}) {
  const [sections, setSections] = useState<Record<KitUpdateSection, KitDraft> | null>(null);
  const [active, setActive] = useState<KitUpdateSection>(initialSection);
  const [error, setError] = useState<string | null>(null);
  const [ingesting, setIngesting] = useState(false);
  const [sending, setSending] = useState(false);
  const [publishing, setPublishing] = useState(false);

  // New-brand setup state -- only touched when `newBrand` is true and no brand exists yet.
  const [createdBrand, setCreatedBrand] = useState<string | null>(null);
  const [setupFile, setSetupFile] = useState<File | null>(null);
  const [inferring, setInferring] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [setupName, setSetupName] = useState("");
  const [nameWasInferred, setNameWasInferred] = useState(false);
  const [territory, setTerritory] = useState<string | null>(null);
  const [customTerritory, setCustomTerritory] = useState("");
  const [usingCustomTerritory, setUsingCustomTerritory] = useState(false);
  const [settingUp, setSettingUp] = useState(false);

  const isPendingNewBrand = newBrand && !createdBrand;
  const effectiveBrand = createdBrand ?? brand;

  const load = () => {
    getKitUpdateState(effectiveBrand)
      .then((r) => {
        const bySection = Object.fromEntries(r.sections.map((s) => [s.section, s])) as Record<KitUpdateSection, KitDraft>;
        setSections(bySection);
      })
      .catch((e) => setError(String(e)));
  };

  useEffect(() => {
    if (!isPendingNewBrand) load();
  }, [effectiveBrand, isPendingNewBrand]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSetupFile = async (f: File) => {
    setSetupFile(f);
    setError(null);
    setInferring(true);
    try {
      const r = await inferBrandName(f);
      if (r.name) {
        setSetupName(r.name);
        setNameWasInferred(true);
      }
    } catch (e) {
      // Name inference failing is not fatal -- the user can still type the name.
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setInferring(false);
    }
  };

  /** Hidden escape hatch for when there's no real brand-plan document handy: fabricates
   *  a complete fictional one and runs it through the exact same handleSetupFile() path a
   *  real upload takes -- no separate ingestion code path to keep in sync. */
  const generateRandom = async () => {
    setError(null);
    setGenerating(true);
    try {
      const { text } = await generateRandomBrandPlan();
      const f = new File([text], "generated-brand-plan.txt", { type: "text/plain" });
      await handleSetupFile(f);
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setGenerating(false);
    }
  };

  const effectiveTerritory = usingCustomTerritory ? customTerritory.trim() : territory;

  const finishSetup = async () => {
    if (!setupFile || !setupName.trim() || !effectiveTerritory) return;
    setSettingUp(true);
    setError(null);
    try {
      const r = await setupBrand(setupFile, setupName.trim(), effectiveTerritory);
      setCreatedBrand(r.brand);
      // setupBrand's own response sections are kickoff_all()'s raw drafts, which don't
      // carry `history` (that's assembled by getKitUpdateState, not kickoff) -- refetch
      // from there instead of using the raw response directly so activeDraft.history is
      // never undefined once the screen falls through to its normal five-tab view.
      const full = await getKitUpdateState(r.brand);
      const bySection = Object.fromEntries(full.sections.map((s) => [s.section, s])) as Record<KitUpdateSection, KitDraft>;
      setSections(bySection);
      onBrandCreated?.(r.brand);
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setSettingUp(false);
    }
  };

  const hasAnyProgress = sections && Object.values(sections).some((d) => d.status !== "not_started");

  const ingest = async (opts: { useSample: true } | { file: File }) => {
    setIngesting(true);
    setError(null);
    try {
      await ingestKitUpdate(effectiveBrand, opts);
      load();
    } catch (e) {
      setError(String(e));
    } finally {
      setIngesting(false);
    }
  };

  const send = async (message: string) => {
    setSending(true);
    try {
      await askKitUpdate(effectiveBrand, active, message);
      load();
    } catch (e) {
      setError(String(e));
    } finally {
      setSending(false);
    }
  };

  const publish = async (acceptedFields: string[]) => {
    setPublishing(true);
    try {
      await publishKitUpdate(effectiveBrand, active, acceptedFields);
      load();
    } catch (e) {
      setError(String(e));
    } finally {
      setPublishing(false);
    }
  };

  const activeDraft = sections?.[active];

  return (
    <div className="kit-update-screen">
      <div className="kit-update-header">
        <div>
          <div className="kit-update-eyebrow">
            {isPendingNewBrand ? "Set up a new brand" : `Brand plan update -- ${effectiveBrand}`}
          </div>
          <h1 className="kit-update-title">{isPendingNewBrand ? "Add a brand plan" : "Guided update"}</h1>
        </div>
        {isPendingNewBrand && (
          <button
            type="button"
            className="new-brand-secret-generate"
            title="Don't have a brand plan handy? Generate a fictional one to try the flow."
            aria-label="Generate a random brand plan"
            disabled={generating || inferring}
            onClick={generateRandom}
          >
            <Icon name="zap" size={13} />
          </button>
        )}
        <button type="button" className="kit-update-close" onClick={onClose}>Close</button>
      </div>

      <div className="kit-update-scroll">
      {error && <div className="error-banner">{error}</div>}

      {isPendingNewBrand && (
        <div className="kit-update-ingest new-brand-card">
          <p className="new-brand-help">
            Upload the brand-plan document for the new brand. We'll read the brand name
            off it -- you can still edit it before continuing.
          </p>
          <label className="new-brand-upload">
            {setupFile ? setupFile.name : "Choose a file (.pdf, .docx, .txt, .md)"}
            <input
              type="file"
              accept=".pdf,.docx,.txt,.md"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) handleSetupFile(f); }}
            />
          </label>

          {setupFile && (
            <div className="new-brand-name-field">
              <label htmlFor="new-brand-name">Brand name</label>
              <input
                id="new-brand-name"
                type="text"
                value={inferring ? "Reading the document…" : setupName}
                disabled={inferring}
                onChange={(e) => { setSetupName(e.target.value); setNameWasInferred(false); }}
                placeholder="e.g. CardioPulse"
              />
              {nameWasInferred && !inferring && (
                <p className="new-brand-inferred-note">
                  <Icon name="check" size={12} /> Read from the document -- edit it if that's not right.
                </p>
              )}
            </div>
          )}

          {setupFile && !inferring && (
            <>
              <p className="new-brand-help" style={{ marginTop: 4 }}>
                Which territory does this brand plan apply to? This starts unknown on
                purpose -- pick one, or add your own if it's not in the list.
              </p>
              <div className="new-brand-territory-grid">
                {knownTerritories.map((t) => (
                  <button
                    key={t}
                    type="button"
                    className={`new-brand-territory-pill ${!usingCustomTerritory && territory === t ? "active" : ""}`}
                    onClick={() => { setTerritory(t); setUsingCustomTerritory(false); }}
                  >
                    {t}
                  </button>
                ))}
                <button
                  type="button"
                  className={`new-brand-territory-pill ${usingCustomTerritory ? "active" : ""}`}
                  onClick={() => setUsingCustomTerritory(true)}
                >
                  Other
                </button>
              </div>
              {usingCustomTerritory && (
                <input
                  type="text"
                  className="new-brand-territory-input"
                  value={customTerritory}
                  onChange={(e) => setCustomTerritory(e.target.value)}
                  placeholder="Type the territory (e.g. Australia)"
                  autoFocus
                />
              )}
            </>
          )}

          <button
            type="button"
            className="new-brand-next"
            disabled={!setupFile || inferring || !setupName.trim() || !effectiveTerritory || settingUp}
            onClick={finishSetup}
          >
            {settingUp ? "Setting up…" : "Finish setup"}
          </button>
        </div>
      )}

      {!isPendingNewBrand && sections && !hasAnyProgress && (
        <div className="kit-update-ingest">
          <p>
            No update session started yet for {effectiveBrand}. Generate a sample brand-plan PDF to
            seed all five sections, or upload your own.
          </p>
          <div className="kit-update-ingest-actions">
            <button type="button" className="kit-update-ingest-btn" disabled={ingesting}
              onClick={() => ingest({ useSample: true })}>
              {ingesting ? "Generating & ingesting…" : "Generate a sample brand plan PDF"}
            </button>
            <a className="kit-update-ingest-link" href={sampleKitPdfUrl(effectiveBrand)} target="_blank" rel="noreferrer">
              Preview the sample PDF
            </a>
            <label className="kit-update-upload">
              Upload your own
              <input type="file" accept=".pdf,.docx,.txt,.md" disabled={ingesting}
                onChange={(e) => { const f = e.target.files?.[0]; if (f) ingest({ file: f }); }} />
            </label>
          </div>
        </div>
      )}

      {!isPendingNewBrand && sections && (
        <>
          <div className="kit-update-rail">
            {KIT_UPDATE_SECTIONS.map((section) => {
              const d = sections[section];
              return (
                <button
                  key={section}
                  type="button"
                  className={`kit-update-rail-tab ${active === section ? "active" : ""} status-${d.status}`}
                  onClick={() => setActive(section)}
                >
                  <span className="kit-update-rail-label">{KIT_UPDATE_SECTION_LABELS[section]}</span>
                  <span className={`kit-update-rail-status status-${d.status}`}>{STATUS_LABEL[d.status]}</span>
                </button>
              );
            })}
          </div>

          {activeDraft && (
            <div className="kit-update-body">
              <div className="kit-update-chat-pane">
                <KitUpdateChat history={activeDraft.history} onSend={send} sending={sending} />
              </div>
              <div className="kit-update-diff-pane">
                <h3 className="kit-update-diff-title">Proposed changes</h3>
                <DiffReview draft={activeDraft} onPublish={publish} publishing={publishing} />
              </div>
            </div>
          )}
        </>
      )}

      {!isPendingNewBrand && !sections && !error && <div className="loading">Loading update session&hellip;</div>}
      </div>
    </div>
  );
}
