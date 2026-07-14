import Box from "@mui/material/Box";
import { styled } from "@mui/material/styles";
import type { Slots } from "./types";
import { tokens, indigoTint } from "../theme/tokens";
import { DefinitionRow, PillChip } from "../glass/primitives";

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
          {extras.map(([label, key]) => (
            <DefinitionRow key={key} label={label} value={String(slots[key])} />
          ))}
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
