import { useState } from "react";
import Box from "@mui/material/Box";
import { styled } from "@mui/material/styles";
import type { Slots } from "./types";
import { tokens, indigoTint } from "../theme/tokens";
import { DefinitionRow, PillChip } from "../glass/primitives";

/** Words shown on the single collapsed line before "See more" takes over. */
const PREVIEW_WORDS = 10;

/** Sub-section label inside the brief (small caps, indigo). */
const GroupLabel = styled("div")(({ theme }) => ({
  borderTop: `1px solid ${indigoTint(0.12)}`,
  marginTop: theme.spacing(1.5),
  paddingTop: theme.spacing(1.5),
  fontSize: tokens.fontSize.xs,
  fontWeight: 700,
  textTransform: "uppercase",
  letterSpacing: "0.08em",
  color: tokens.color.primary,
}));

function fmtBudget(n?: number) {
  if (!n) return "";
  return `$${n.toLocaleString()}`;
}

/** First `n` words, so the collapsed line is a predictable length rather than
 *  however much happens to fit the pane width. */
function previewWords(text: string, n: number) {
  const words = text.split(/\s+/).filter(Boolean);
  return words.length <= n ? text : `${words.slice(0, n).join(" ")}…`;
}

/** Small inline "See more" / "See less" affordance. */
const ToggleLink = styled("button")({
  appearance: "none",
  background: "none",
  border: "none",
  padding: 0,
  marginTop: 2,
  font: "inherit",
  fontSize: tokens.fontSize.xs,
  fontWeight: 700,
  color: tokens.color.primary,
  cursor: "pointer",
  "&:hover": { textDecoration: "underline" },
});

/** A brief value that shows ONE ~10-word line by default and reveals the full
 *  captured text on demand. Collapsed is the default for every row.
 *  Shared with BriefExtractCard so the brief reads identically in the chat rail
 *  and in the workspace panel. */
export function ExpandableValue({ short, full }: { short: string; full: string }) {
  const [open, setOpen] = useState(false);
  const collapsed = previewWords(short, PREVIEW_WORDS);
  // Nothing gained by a toggle when the one-line preview is already the whole value.
  const hasMore = full.trim().length > 0 && full.trim() !== collapsed.trim();

  return (
    <Box sx={{ minWidth: 0 }}>
      <Box
        component="span"
        sx={{
          display: "block",
          // The WORD clamp above is the only truncation -- and it always comes with a
          // "See more". CSS must never clip on its own: a value short enough to skip the
          // clamp but too wide for the rail (a long indication, a slash-joined audience
          // list) used to be cut mid-word with no way to reveal the rest.
          whiteSpace: "normal",
          overflowWrap: "anywhere",
        }}
      >
        {open ? full : collapsed}
      </Box>
      {hasMore && (
        <ToggleLink type="button" onClick={() => setOpen((v) => !v)}>
          {open ? "See less" : "See more"}
        </ToggleLink>
      )}
    </Box>
  );
}

const EXTRA_FIELDS: [string, keyof Slots][] = [
  ["Campaign", "campaign_name"],
  ["Molecule", "molecule"],
  ["Audience", "audience"],
  ["Geography", "geography"],
  ["Duration", "duration"],
  ["Objective", "objective"],
  ["Target KPI", "kpi"],
  ["Preferred channels", "preferred_channels"],
  ["Existing assets", "existing_assets"],
  ["Constraints", "constraints"],
  ["Reason", "reason"],
  ["Notes", "notes"],
];

export interface Inferred {
  persona: string;
  stage_label: string;
  lifecycle_label: string;
  competitors: string[];
  cx_maturity?: string;
}

export function BriefCard({ slots, inferred }: { slots: Slots; inferred: Inferred }) {
  const extras = EXTRA_FIELDS.filter(([, key]) => {
    const v = slots[key];
    return v && v !== "(not specified)";
  });
  const hasInferred =
    inferred.persona || inferred.stage_label || inferred.cx_maturity || (inferred.competitors?.length ?? 0) > 0;
  const budget = fmtBudget(slots.budget);

  return (
    <Box>
      <DefinitionRow label="Brand" value={slots.brand} />
      <DefinitionRow label="Therapy area" value={slots.therapy_area} />
      {slots.indication && <DefinitionRow label="Indication" value={slots.indication} />}
      <DefinitionRow label="Lifecycle" value={inferred.lifecycle_label || slots.lifecycle_key} />
      <DefinitionRow label="Budget" value={budget || undefined} hint={budget ? undefined : "percentages only"} />

      {extras.length > 0 && (
        <>
          <GroupLabel>From your brief</GroupLabel>
          {extras.map(([label, key]) => {
            const full = String(slots[key]);
            // Show the server's ≤15-word gist, not the whole paragraph from the deck.
            const short = slots.brief_summary?.[key as string] || full;
            return (
              <DefinitionRow
                key={key}
                label={label}
                value={<ExpandableValue short={short} full={full} />}
              />
            );
          })}
        </>
      )}

      {hasInferred && (
        <>
          <GroupLabel>Inferred by agent</GroupLabel>
          {inferred.persona && <DefinitionRow label="Persona" value={inferred.persona} />}
          {inferred.stage_label && <DefinitionRow label="Journey stage" value={inferred.stage_label} />}
          {inferred.cx_maturity && <DefinitionRow label="CX maturity" value={inferred.cx_maturity} />}
          {inferred.competitors?.length > 0 && (
            <DefinitionRow
              label="Competitors"
              value={
                <Box sx={{ display: "flex", gap: 0.5, flexWrap: "wrap", justifyContent: "flex-end" }}>
                  {inferred.competitors.map((c) => (
                    <PillChip key={c} label={c} />
                  ))}
                </Box>
              }
            />
          )}
        </>
      )}

    </Box>
  );
}
