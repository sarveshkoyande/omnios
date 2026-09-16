import { useEffect, useState } from "react";
import {
  askKitUpdate, getKitUpdateState, ingestKitUpdate, publishKitUpdate, sampleKitPdfUrl,
} from "../api";
import {
  KIT_UPDATE_SECTIONS, KIT_UPDATE_SECTION_LABELS,
} from "../types";
import type { KitDraft, KitUpdateSection } from "../types";
import { DiffReview } from "./kitUpdate/DiffReview";
import { KitUpdateChat } from "./kitUpdate/KitUpdateChat";

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
 *  restores whatever each tab already has (F2). */
export function KitUpdateScreen({ brand, initialSection, onClose }: {
  brand: string;
  initialSection: KitUpdateSection;
  onClose: () => void;
}) {
  const [sections, setSections] = useState<Record<KitUpdateSection, KitDraft> | null>(null);
  const [active, setActive] = useState<KitUpdateSection>(initialSection);
  const [error, setError] = useState<string | null>(null);
  const [ingesting, setIngesting] = useState(false);
  const [sending, setSending] = useState(false);
  const [publishing, setPublishing] = useState(false);

  const load = () => {
    getKitUpdateState(brand)
      .then((r) => {
        const bySection = Object.fromEntries(r.sections.map((s) => [s.section, s])) as Record<KitUpdateSection, KitDraft>;
        setSections(bySection);
      })
      .catch((e) => setError(String(e)));
  };

  useEffect(() => { load(); }, [brand]); // eslint-disable-line react-hooks/exhaustive-deps

  const hasAnyProgress = sections && Object.values(sections).some((d) => d.status !== "not_started");

  const ingest = async (opts: { useSample: true } | { file: File }) => {
    setIngesting(true);
    setError(null);
    try {
      await ingestKitUpdate(brand, opts);
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
      await askKitUpdate(brand, active, message);
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
      await publishKitUpdate(brand, active, acceptedFields);
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
          <div className="kit-update-eyebrow">Brand plan update -- {brand}</div>
          <h1 className="kit-update-title">Guided update</h1>
        </div>
        <button type="button" className="kit-update-close" onClick={onClose}>Close</button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {sections && !hasAnyProgress && (
        <div className="kit-update-ingest">
          <p>
            No update session started yet for {brand}. Generate a sample brand-plan PDF to
            seed all five sections, or upload your own.
          </p>
          <div className="kit-update-ingest-actions">
            <button type="button" className="kit-update-ingest-btn" disabled={ingesting}
              onClick={() => ingest({ useSample: true })}>
              {ingesting ? "Generating & ingesting…" : "Generate a sample brand plan PDF"}
            </button>
            <a className="kit-update-ingest-link" href={sampleKitPdfUrl(brand)} target="_blank" rel="noreferrer">
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

      {sections && (
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

      {!sections && !error && <div className="loading">Loading update session&hellip;</div>}
    </div>
  );
}
