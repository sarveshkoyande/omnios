import { useState } from "react";
import Box from "@mui/material/Box";
import { styled } from "@mui/material/styles";
import type { Slots } from "./types";
import { tokens, indigoTint } from "../theme/tokens";
import { PillChip } from "../glass/primitives";
import { BriefFields, type BriefField } from "./BriefFields";

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

/** label, slot key, and how many columns the field wants. Short scalars pair up; captured
 *  prose takes the full width, since a paragraph in a half column wraps to five lines. */
const EXTRA_FIELDS: [string, keyof Slots, 1 | 2][] = [
  ["Campaign", "campaign_name", 1],
  ["Molecule", "molecule", 1],
  ["Audience", "audience", 1],
  ["Geography", "geography", 1],
  ["Duration", "duration", 1],
  ["Objective", "objective", 2],
  ["Target KPI", "kpi", 2],
  ["Preferred channels", "preferred_channels", 2],
  ["Existing assets", "existing_assets", 2],
  ["Constraints", "constraints", 2],
  ["Reason", "reason", 2],
  ["Notes", "notes", 2],
];

export interface Inferred {
  persona: string;
  stage_label: string;
  lifecycle_label: string;
  competitors: string[];
  cx_maturity?: string;
}

/** An unset value renders as N/A in secondary ink rather than an empty cell — an empty cell
 *  reads as a rendering bug, not as "we don't know this yet". */
const orNA = (v?: string) =>
  v && v.trim() ? v : <Box component="span" sx={{ fontWeight: 400, color: tokens.color.inkSecondary }}>N/A</Box>;

export function BriefCard({ slots, inferred, columns = 2 }: { slots: Slots; inferred: Inferred; columns?: 1 | 2 }) {
  const extras = EXTRA_FIELDS.filter(([, key]) => {
    const v = slots[key];
    return v && v !== "(not specified)";
  });
  const hasInferred =
    inferred.persona || inferred.stage_label || inferred.cx_maturity || (inferred.competitors?.length ?? 0) > 0;
  const budget = fmtBudget(slots.budget);

  const core: BriefField[] = [
    { label: "Brand", value: orNA(slots.brand), span: 1 },
    { label: "Therapy area", value: orNA(slots.therapy_area), span: 1 },
    ...(slots.indication ? [{ label: "Indication", value: slots.indication, span: 1 as const }] : []),
    { label: "Lifecycle", value: orNA(inferred.lifecycle_label || slots.lifecycle_key), span: 1 },
    {
      label: "Budget",
      value: budget || (
        <Box component="span" sx={{ fontWeight: 400, color: tokens.color.inkSecondary }}>percentages only</Box>
      ),
      span: 2,
    },
  ];

  const fromBrief: BriefField[] = extras.map(([label, key, span]) => {
    const full = String(slots[key]);
    // Show the server's ≤15-word gist, not the whole paragraph from the deck.
    const short = slots.brief_summary?.[key as string] || full;
    return { label, value: <ExpandableValue short={short} full={full} />, span };
  });

  const agentInferred: BriefField[] = [
    ...(inferred.persona ? [{ label: "Persona", value: inferred.persona, span: 1 as const }] : []),
    ...(inferred.stage_label ? [{ label: "Journey stage", value: inferred.stage_label, span: 1 as const }] : []),
    ...(inferred.cx_maturity ? [{ label: "CX maturity", value: inferred.cx_maturity, span: 1 as const }] : []),
    ...(inferred.competitors?.length
      ? [{
          label: "Competitors",
          span: 2 as const,
          value: (
            <Box sx={{ display: "flex", gap: 0.5, flexWrap: "wrap" }}>
              {inferred.competitors.map((c) => (
                <PillChip key={c} label={c} />
              ))}
            </Box>
          ),
        }]
      : []),
  ];

  return (
    <Box>
      <BriefFields fields={core} columns={columns} />

      {fromBrief.length > 0 && (
        <>
          <GroupLabel>From your brief</GroupLabel>
          <BriefFields fields={fromBrief} columns={columns} />
        </>
      )}

      {hasInferred && (
        <>
          <GroupLabel>Inferred by agent</GroupLabel>
          <BriefFields fields={agentInferred} columns={columns} />
        </>
      )}
    </Box>
  );
}
