/**
 * Campaign journey performance — the same funnel volumes drawn as the flow they came from,
 * so each decision point shows both branches: who carried on and who dropped out.
 *
 * Laid out as flex nodes rather than a Sankey library: at five steps the ribbon widths a
 * Sankey buys you are noise, and the drop-off branch is the number people actually read.
 */
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { enterRise, enterWith, stagger } from "../../../theme/motionPresets";
import { tokens } from "../../../theme/tokens";
import { radius, CardTitle, DashCard, dataColor } from "./dashboardKit";
import type { ReportingJourneyStep } from "../../types";

const KIND_STYLE: Record<ReportingJourneyStep["kind"], { bg: string; ink: string; border: string }> = {
  send: { bg: dataColor.info.soft, ink: dataColor.info.ink, border: dataColor.info.line },
  step: { bg: "#F2F4F7", ink: tokens.color.ink, border: tokens.color.outline },
  decision: { bg: tokens.color.surface, ink: tokens.color.ink, border: dataColor.info.line },
  outcome: { bg: dataColor.positive.soft, ink: dataColor.positive.ink, border: dataColor.positive.line },
};

export function JourneyCard({ steps }: { steps: ReportingJourneyStep[] }) {
  if (!steps.length) return null;
  return (
    <DashCard sx={{ flex: "1 1 480px" }}>
      <CardTitle title="Campaign journey performance" hint="Both branches at every decision point" />
      <Box sx={{ display: "flex", alignItems: "stretch", gap: 1, overflowX: "auto", pb: 1 }}>
        {steps.map((step, i) => {
          const s = KIND_STYLE[step.kind];
          return (
            <Box key={step.id} sx={{ display: "flex", alignItems: "stretch", gap: 1, flex: "1 1 0", minWidth: 128 }}>
              <Box sx={{ flex: 1, display: "flex", flexDirection: "column", gap: 0.75, animation: enterWith(enterRise, stagger(i, 60)) }}>
                <Box sx={{
                  background: s.bg, border: `1px solid ${s.border}`, borderRadius: radius.sm,
                  px: 1.5, py: 1.25, minWidth: 0,
                }}>
                  <Typography sx={{ fontSize: 15, fontWeight: 700, color: s.ink, lineHeight: 1.25 }}>
                    {step.label}
                  </Typography>
                  <Typography sx={{ fontSize: 20, fontWeight: 800, lineHeight: 1.2, fontVariantNumeric: "tabular-nums" }}>
                    {step.count.toLocaleString()}
                  </Typography>
                  <Typography sx={{ fontSize: 15, color: "text.secondary" }}>{step.pct}% of prior</Typography>
                </Box>

                {step.branch && (
                  <Box sx={{
                    border: `1px dashed ${tokens.color.outline}`, borderRadius: radius.sm,
                    px: 1.5, py: 0.75, background: "#FAFBFC",
                  }}>
                    <Typography sx={{ fontSize: 15, color: "text.secondary", lineHeight: 1.3 }}>
                      {step.branch.label}
                    </Typography>
                    <Typography sx={{ fontSize: 15, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>
                      {step.branch.count.toLocaleString()} · {step.branch.pct}%
                    </Typography>
                  </Box>
                )}
              </Box>

              {i < steps.length - 1 && (
                <Box sx={{ display: "flex", alignItems: "flex-start", pt: 3 }}>
                  <span className="material-symbols-outlined" style={{ fontSize: 20, color: tokens.color.outlineStrong }}>
                    chevron_right
                  </span>
                </Box>
              )}
            </Box>
          );
        })}
      </Box>
    </DashCard>
  );
}
