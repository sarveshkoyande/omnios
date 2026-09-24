import { useEffect, useState } from "react";
import { getCampaignDrift, refreshCampaignSnapshot } from "../api";
import type { CampaignDrift } from "../types";
import { ValueView } from "./journey/DraftValue";

const STEP_LABEL: Record<string, string> = { brief: "Brief", audience: "Audience", message: "Message", kit: "Kit" };

/** Hierarchy idea 5: the campaign was built on brand content that has since changed. Shows
 *  what changed (Compare) and offers "Update to current content" (P-R3, P-R4, P-KD3). */
export function DriftBanner({ campaignId, reloadKey, onUpdated, subject = "This campaign" }: {
  campaignId: number;
  /** Changes whenever the caller's data changes, so the drift is re-read. */
  reloadKey?: unknown;
  onUpdated?: () => void;
  subject?: string;
}) {
  const [drift, setDrift] = useState<CampaignDrift | null>(null);
  const [compare, setCompare] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    getCampaignDrift(campaignId).then((d) => { if (live) setDrift(d); }).catch(() => undefined);
    return () => { live = false; };
  }, [campaignId, reloadKey]);

  if (!drift) return null;
  if (!drift.tracked) {
    return <div className="jc-drift jc-drift-quiet" role="status">Built before content tracking: this campaign has no record of the brand content it used.</div>;
  }
  if (!drift.has_drift) return null;

  const update = () => {
    setBusy(true);
    setError(null);
    refreshCampaignSnapshot(campaignId)
      .then((d) => { setDrift(d); setCompare(false); onUpdated?.(); })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setBusy(false));
  };

  return (
    <div className="jc-drift" role="status">
      <div className="jc-drift-head">
        <span>
          The brand's {Object.keys(drift.changed).map((s) => STEP_LABEL[s] ?? s).join(", ")} changed since this
          campaign was built. {subject} still uses the earlier content.
        </span>
        <span className="jc-drift-actions">
          <button type="button" className="jc-link" onClick={() => setCompare((c) => !c)}>{compare ? "Hide" : "Compare"}</button>
          <button type="button" className="jc-btn jc-btn-keep" disabled={busy} onClick={update}>
            {busy ? "Updating…" : "Update to current content"}
          </button>
        </span>
      </div>
      {error && <div className="step-chat-error">{error}</div>}
      {compare && (
        <dl className="jc-drift-list">
          {Object.entries(drift.changed).flatMap(([step, changes]) => (changes ?? []).map((c) => (
            <div key={`${step}-${c.key}`} className="jc-drift-row">
              <dt>{STEP_LABEL[step] ?? step} · {c.label}</dt>
              <dd><span className="jc-drift-then"><ValueView value={c.then} /></span><span aria-hidden>→</span><ValueView value={c.now} /></dd>
            </div>
          )))}
        </dl>
      )}
    </div>
  );
}
