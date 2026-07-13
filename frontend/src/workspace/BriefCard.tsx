import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import type { Slots } from "./types";
import { shade, tokens } from "../theme/tokens";

const Row = styled("div")(({ theme }) => ({
  display: "flex",
  justifyContent: "space-between",
  gap: theme.spacing(3),
  padding: theme.spacing(1.75, 0),
  borderBottom: `1px solid ${shade(0.1)}`,
  fontSize: tokens.fontSize.sm,
  "&:last-of-type": { borderBottom: "none" },
}));

const SectionLabel = styled("div")(({ theme }) => ({
  borderTop: `1px dashed ${shade(0.18)}`,
  marginTop: theme.spacing(1),
  paddingTop: theme.spacing(1.5),
  fontSize: tokens.fontSize.xs,
  fontWeight: 700,
  textTransform: "uppercase",
  letterSpacing: "0.06em",
  color: shade(0.55),
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

  return (
    <Box>
      <Row>
        <span style={{ color: shade(0.6) }}>Brand</span>
        <b>{slots.brand || "—"}</b>
      </Row>
      <Row>
        <span style={{ color: shade(0.6) }}>Therapy area</span>
        <b>{slots.therapy_area || "—"}</b>
      </Row>
      {slots.indication && (
        <Row>
          <span style={{ color: shade(0.6) }}>Indication</span>
          <b>{slots.indication}</b>
        </Row>
      )}
      <Row>
        <span style={{ color: shade(0.6) }}>Lifecycle</span>
        <b>{inferred.lifecycle_label || slots.lifecycle_key || "—"}</b>
      </Row>
      <Row>
        <span style={{ color: shade(0.6) }}>Budget</span>
        <b>{fmtBudget(slots.budget) || "—"}</b>
      </Row>

      {extras.length > 0 && (
        <>
          <SectionLabel>From your brief</SectionLabel>
          {extras.map(([label, key]) => (
            <Row key={key}>
              <span style={{ color: shade(0.6) }}>{label}</span>
              <b>{String(slots[key])}</b>
            </Row>
          ))}
        </>
      )}

      {hasInferred && (
        <>
          <SectionLabel>Inferred by agent</SectionLabel>
          {inferred.persona && (
            <Row>
              <span style={{ color: shade(0.6) }}>Persona</span>
              <b>{inferred.persona}</b>
            </Row>
          )}
          {inferred.stage_label && (
            <Row>
              <span style={{ color: shade(0.6) }}>Journey stage</span>
              <b>{inferred.stage_label}</b>
            </Row>
          )}
          {inferred.cx_maturity && (
            <Row>
              <span style={{ color: shade(0.6) }}>CX maturity</span>
              <b>{inferred.cx_maturity}</b>
            </Row>
          )}
          {inferred.competitors?.length > 0 && (
            <Row>
              <span style={{ color: shade(0.6) }}>Competitors</span>
              <Box sx={{ display: "flex", gap: 0.5, flexWrap: "wrap", justifyContent: "flex-end" }}>
                {inferred.competitors.map((c) => (
                  <Chip key={c} size="small" label={c} />
                ))}
              </Box>
            </Row>
          )}
        </>
      )}

      {!slots.brand && (
        <Typography variant="body2" sx={{ color: "text.secondary", fontStyle: "italic", pt: 1 }}>
          The brief fills in here as you talk to the agent.
        </Typography>
      )}
    </Box>
  );
}
