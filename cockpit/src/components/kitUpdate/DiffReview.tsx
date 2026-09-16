import { useMemo, useState } from "react";
import type { KitDraft } from "../../types";
import { Icon } from "../Icon";

function formatValue(v: unknown): string {
  if (v === null || v === undefined) return "(empty)";
  if (typeof v === "string") return v;
  return JSON.stringify(v);
}

/** One row per changed field (current -> proposed), each with its own Accept/Reject --
 *  the per-field diff review R3 requires so an agent's turn is never applied as a silent
 *  full-section overwrite. Publish only sends the accepted field names; anything left
 *  rejected (the default) never reaches the drafts store. */
export function DiffReview({ draft, onPublish, publishing }: {
  draft: KitDraft;
  onPublish: (acceptedFields: string[]) => void;
  publishing: boolean;
}) {
  const fields = useMemo(() => Object.keys(draft.diff), [draft.diff]);
  const [accepted, setAccepted] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(fields.map((f) => [f, true])));

  if (draft.status === "published" && fields.length === 0) {
    return <p className="kit-diff-empty">Published. No pending changes for this section.</p>;
  }
  if (fields.length === 0) {
    return (
      <p className="kit-diff-empty">
        Nothing new found for this section yet. Ask the agent something, or ingest a
        document, to get a first draft.
      </p>
    );
  }

  const acceptedCount = fields.filter((f) => accepted[f]).length;

  return (
    <div className="kit-diff-review">
      {fields.map((field) => (
        <div className="kit-diff-row" key={field}>
          <div className="kit-diff-field">{field}</div>
          <div className="kit-diff-values">
            <div className="kit-diff-current">{formatValue(draft.diff[field].current)}</div>
            <div className="kit-diff-arrow" aria-hidden><Icon name="arrowRight" size={13} /></div>
            <div className="kit-diff-proposed">{formatValue(draft.diff[field].proposed)}</div>
          </div>
          <div className="kit-diff-toggle">
            <button
              type="button"
              className={`kit-diff-toggle-btn ${accepted[field] ? "accept active" : "accept"}`}
              onClick={() => setAccepted((a) => ({ ...a, [field]: true }))}
            >
              Accept
            </button>
            <button
              type="button"
              className={`kit-diff-toggle-btn ${!accepted[field] ? "reject active" : "reject"}`}
              onClick={() => setAccepted((a) => ({ ...a, [field]: false }))}
            >
              Reject
            </button>
          </div>
        </div>
      ))}
      <button
        type="button"
        className="kit-diff-publish"
        disabled={acceptedCount === 0 || publishing}
        onClick={() => onPublish(fields.filter((f) => accepted[f]))}
      >
        {publishing ? "Publishing…" : `Publish ${acceptedCount} accepted field${acceptedCount === 1 ? "" : "s"}`}
      </button>
    </div>
  );
}
