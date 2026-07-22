import type { ReactNode } from "react";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Typography from "@mui/material/Typography";
import Accordion from "@mui/material/Accordion";
import AccordionSummary from "@mui/material/AccordionSummary";
import AccordionDetails from "@mui/material/AccordionDetails";
import { styled } from "@mui/material/styles";
import { glass, indigoTint, tokens } from "../../theme/tokens";
import type { DecisionRecord } from "./studioTypes";

/** The reasoning trail: one card per spine stage, laid out as an explicit
 * reasoning path — WHAT WE USED → HOW WE REASONED → WHAT WE REJECTED →
 * THE DECISION → WHAT IT SHAPES. The decision itself is the hero of the card;
 * the numbered steps make "how we got there" legible at a glance. */

const SOURCE_COLOR: Record<string, { bg: string; ink: string }> = {
  internal: { bg: "#EAF0FE", ink: "#2451C4" },
  external: { bg: "#E3F6EE", ink: "#0B6B4C" },
  user: { bg: "#F1EAFB", ink: "#5B21B6" },
};

const RecordCard = styled(Accordion)({
  background: glass.panel,
  border: `1px solid ${indigoTint(0.12)}`,
  borderRadius: `${tokens.radius.md}px !important`,
  boxShadow: "none",
  "&:before": { display: "none" },
  marginBottom: 10,
});

/** The hero: the decision itself, unmissable. */
const DecisionBox = styled(Box)({
  background: tokens.color.primaryContainer,
  borderLeft: `4px solid ${tokens.color.primary}`,
  borderRadius: tokens.radius.sm,
  padding: "12px 16px",
  marginBottom: 16,
});

/** One numbered step on the reasoning path, with a connector line to the next. */
const Step = styled(Box)({
  position: "relative",
  paddingLeft: 40,
  paddingBottom: 18,
  "&:not(:last-of-type)::before": {
    content: '""',
    position: "absolute",
    left: 13,
    top: 28,
    bottom: 0,
    width: 2,
    background: indigoTint(0.15),
  },
});

const StepBadge = styled("span")({
  position: "absolute",
  left: 0,
  top: 0,
  width: 28,
  height: 28,
  borderRadius: "50%",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  fontSize: tokens.fontSize.xs,
  fontWeight: 800,
  background: tokens.color.surface,
  border: `2px solid ${tokens.color.primary}`,
  color: tokens.color.primary,
});

const StepTitle = styled(Typography)({
  fontSize: tokens.fontSize.xs,
  fontWeight: 800,
  letterSpacing: "0.07em",
  textTransform: "uppercase",
  color: tokens.color.inkSecondary,
  marginBottom: 6,
  lineHeight: "28px",
});

function SourceTag({ source_class }: { source_class: string }) {
  const c = SOURCE_COLOR[source_class] ?? SOURCE_COLOR.internal;
  return (
    <Box component="span" sx={{ fontSize: 11, fontWeight: 700, px: 0.75, py: 0.2, borderRadius: 1, background: c.bg, color: c.ink, flex: "0 0 auto" }}>
      {source_class}
    </Box>
  );
}

export function DecisionTrail({ records, dense }: { records: DecisionRecord[]; dense?: boolean }) {
  if (!records.length) return null;
  return (
    <Box>
      {records.map((r) => {
        const steps: { title: string; body: ReactNode }[] = [];

        if (r.inputs.length > 0) {
          steps.push({
            title: "What we looked at",
            body: (
              <Box>
                {r.inputs.map((inp, i) => (
                  <Box key={i} sx={{ display: "flex", gap: 1, alignItems: "baseline", mb: 0.75 }}>
                    <SourceTag source_class={inp.source_class} />
                    <Typography variant="body2" sx={{ color: tokens.color.text }}>
                      <b>{inp.label}:</b> {inp.value}{" "}
                      <Box component="span" sx={{ color: "text.secondary", fontStyle: "italic" }}>({inp.source})</Box>
                    </Typography>
                  </Box>
                ))}
              </Box>
            ),
          });
        }

        steps.push({
          title: "How we reasoned",
          body: (
            <Box>
              <Chip size="small" variant="outlined" label={r.framework} sx={{ height: 22, fontSize: tokens.fontSize.xs, mb: 0.75 }} />
              <Typography variant="body2" sx={{ color: tokens.color.text, lineHeight: 1.65 }}>
                {r.rationale}
              </Typography>
            </Box>
          ),
        });

        if (r.alternatives?.length > 0) {
          steps.push({
            title: "What we set aside",
            body: (
              <Box>
                {r.alternatives.map((a, i) => (
                  <Box key={i} sx={{ display: "flex", gap: 1, alignItems: "baseline", mb: 0.5 }}>
                    <Box component="span" className="material-symbols-outlined" sx={{ fontSize: "16px !important", color: tokens.color.inkSecondary, flex: "0 0 auto", position: "relative", top: 2 }}>
                      block
                    </Box>
                    <Typography variant="body2" sx={{ color: "text.secondary" }}>
                      <b style={{ color: tokens.color.text }}>{a.label}</b> — {a.why_rejected}
                    </Typography>
                  </Box>
                ))}
              </Box>
            ),
          });
        }

        return (
          <RecordCard key={r.stage_id} defaultExpanded={!dense}>
            <AccordionSummary expandIcon={<span className="material-symbols-outlined">expand_more</span>}>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap", minWidth: 0 }}>
                <Chip size="small" label={r.stage_id} sx={{ height: 22, fontWeight: 700, fontSize: tokens.fontSize.xs }} />
                <Typography sx={{ fontWeight: 700, fontSize: tokens.fontSize.sm }}>{r.stage_name}</Typography>
                <Typography sx={{ fontSize: tokens.fontSize.sm, color: "text.secondary", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 360 }}>
                  {r.decision}
                </Typography>
                {r.answered_by_user && (
                  <Chip size="small" color="secondary" variant="outlined" label="your call" sx={{ height: 20, fontSize: 11 }} />
                )}
              </Box>
            </AccordionSummary>
            <AccordionDetails sx={{ pt: 0.5 }}>
              <DecisionBox>
                <Typography sx={{ fontSize: tokens.fontSize.xs, fontWeight: 800, letterSpacing: "0.07em", textTransform: "uppercase", color: tokens.color.primary, mb: 0.5 }}>
                  {r.answered_by_user ? "The decision — your call" : "The decision"}
                </Typography>
                <Typography sx={{ fontSize: tokens.fontSize.md, fontWeight: 700, color: tokens.color.onPrimaryContainer, lineHeight: 1.5 }}>
                  {r.decision}
                </Typography>
              </DecisionBox>

              {steps.map((s, i) => (
                <Step key={s.title}>
                  <StepBadge>{i + 1}</StepBadge>
                  <StepTitle>{s.title}</StepTitle>
                  {s.body}
                </Step>
              ))}

              {r.feeds.length > 0 && (
                <Box sx={{ display: "flex", alignItems: "center", gap: 0.75, flexWrap: "wrap", pt: 0.5, borderTop: `1px dashed ${indigoTint(0.18)}` }}>
                  <Typography variant="caption" sx={{ fontWeight: 700, color: "text.secondary" }}>
                    Shapes in the brief →
                  </Typography>
                  {r.feeds.map((f) => (
                    <Chip key={f} size="small" variant="outlined" color="primary" label={f} sx={{ height: 22, fontSize: tokens.fontSize.xs }} />
                  ))}
                </Box>
              )}
            </AccordionDetails>
          </RecordCard>
        );
      })}
    </Box>
  );
}
