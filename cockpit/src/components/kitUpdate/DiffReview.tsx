import { useEffect, useMemo, useState } from "react";
import type { KitDraft } from "../../types";
import { Icon } from "../Icon";

function formatValue(v: unknown): string {
  if (v === null || v === undefined) return "(empty)";
  if (typeof v === "string") return v;
  if (Array.isArray(v)) return v.join(", ");
  return JSON.stringify(v);
}

/** `personas` diffs are the whole {hcp, patient, payer} object -- rendering it as one
 *  raw JSON blob is technically correct but not reviewable. Summarize per-HCP instead:
 *  which persona, which of their fields actually changed. Matches current<->proposed
 *  entries by name (falls back to index when a proposed persona is genuinely new). */
function summarizePersonas(current: unknown, proposed: unknown): string {
  const curHcp = Array.isArray((current as { hcp?: unknown[] })?.hcp) ? (current as { hcp: Record<string, unknown>[] }).hcp : [];
  const propHcp = Array.isArray((proposed as { hcp?: unknown[] })?.hcp) ? (proposed as { hcp: Record<string, unknown>[] }).hcp : [];
  if (propHcp.length === 0) return formatValue(proposed);

  const lines = propHcp.flatMap((p, i) => {
    const match = curHcp.find((c) => c.name === p.name) ?? curHcp[i];
    const changedFields = Object.keys(p).filter((k) => JSON.stringify(p[k]) !== JSON.stringify(match?.[k]));
    const name = typeof p.name === "string" ? p.name : `HCP ${i + 1}`;
    const isNew = !match;
    if (!isNew && changedFields.length === 0) return []; // untouched persona -- not worth a line
    return [isNew
      ? `${name} (new)`
      : `${name} -- ${changedFields.length} field${changedFields.length === 1 ? "" : "s"} changed: ${changedFields.join(", ")}`];
  });
  return lines.join("\n") || "(no per-HCP changes)";
}

function summarizeBrandPersonification(v: unknown): string {
  const p = v as { archetype?: string; traits?: string[]; narrative?: string } | null | undefined;
  if (!p) return "(empty)";
  const parts = [];
  if (p.archetype) parts.push(`Archetype: ${p.archetype}`);
  if (p.traits?.length) parts.push(`Traits: ${p.traits.join(", ")}`);
  if (p.narrative) parts.push(`Narrative: ${p.narrative}`);
  return parts.join("\n") || "(empty)";
}

function formatFieldDiff(field: string, current: unknown, proposed: unknown): { current: string; proposed: string } {
  if (field === "personas") {
    return { current: "(current personas)", proposed: summarizePersonas(current, proposed) };
  }
  if (field === "brand_personification") {
    return { current: summarizeBrandPersonification(current), proposed: summarizeBrandPersonification(proposed) };
  }
  return { current: formatValue(current), proposed: formatValue(proposed) };
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

  // The diff usually doesn't exist yet when this component first mounts (kickoff's
  // draft arrives asynchronously after the auto-kickoff LLM call returns, or a later
  // chat turn revises it) -- useState's initializer only runs once, so without this a
  // freshly-arrived field was never actually in `accepted` and read as unaccepted
  // (Publish showed "0 accepted fields" even though every row looked selected).
  // New fields default to accepted (matches the initializer above); a field the user
  // already toggled keeps their choice as long as it's still present in the diff.
  useEffect(() => {
    setAccepted((prev) => {
      const next: Record<string, boolean> = {};
      for (const f of fields) next[f] = f in prev ? prev[f] : true;
      return next;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fields.join("|")]);

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
      {fields.map((field) => {
        const { current, proposed } = formatFieldDiff(field, draft.diff[field].current, draft.diff[field].proposed);
        return (
        <div className="kit-diff-row" key={field}>
          <div className="kit-diff-field">{field}</div>
          <div className="kit-diff-values">
            <div className="kit-diff-current">{current}</div>
            <div className="kit-diff-arrow" aria-hidden><Icon name="arrowRight" size={13} /></div>
            <div className="kit-diff-proposed">{proposed}</div>
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
        );
      })}
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
