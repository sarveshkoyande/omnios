/**
 * Engagement funnel — audience → delivered → opened → clicked → converted.
 *
 * Counts are real HCPs from the current cohort run through that cohort's own rates, so the
 * top of the funnel is a population you could list by NPI. Bars are CSS-width transitions
 * (not keyframes) so a filter change retargets from the current width instead of restarting.
 */
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { motion } from "../../../theme/tokens";
import { radius, CardTitle, DashCard, dataColor, useCountUp } from "./dashboardKit";
import type { FunnelStep } from "../../types";

const STEP_TINT = [0.16, 0.32, 0.5, 0.72, 1]; // pale at the top of the funnel, solid at the outcome

function StepRow({ step, index, total }: { step: FunnelStep; index: number; total: number }) {
  const count = useCountUp(step.count);
  const tint = STEP_TINT[Math.min(index, STEP_TINT.length - 1)];
  const isOutcome = index === total - 1;
  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Box sx={{ display: "flex", alignItems: "baseline", gap: 1, mb: 0.5 }}>
          <Typography sx={{ fontSize: 15, fontWeight: 700 }}>{step.stage}</Typography>
          <Typography sx={{ fontSize: 15, color: "text.secondary", fontVariantNumeric: "tabular-nums" }}>
            {Math.round(count).toLocaleString()}
          </Typography>
        </Box>
        <Box sx={{ height: 26, borderRadius: radius.sm, background: "#F2F4F7", overflow: "hidden" }}>
          <Box
            sx={{
              width: `${Math.max(step.pct_of_audience, 1.5)}%`,
              height: "100%",
              borderRadius: radius.sm,
              background: isOutcome
                ? dataColor.positive.line
                : `color-mix(in srgb, ${dataColor.info.line} ${Math.round(tint * 100)}%, white)`,
              transition: `width 620ms ${motion.easeOut}, background ${motion.duration.hover} ${motion.easeOut}`,
            }}
          />
        </Box>
      </Box>
      <Box sx={{ width: 76, textAlign: "right", flex: "0 0 auto" }}>
        <Typography sx={{ fontSize: 17, fontWeight: 800, fontVariantNumeric: "tabular-nums", lineHeight: 1.1 }}>
          {step.pct_of_audience.toFixed(1)}%
        </Typography>
        <Typography sx={{ fontSize: 15, color: "text.secondary" }}>
          {index === 0 ? "of panel" : `${step.pct_of_prior.toFixed(1)}% step`}
        </Typography>
      </Box>
    </Box>
  );
}

export function FunnelCard({ steps }: { steps: FunnelStep[] }) {
  if (!steps.length) return null;
  return (
    <DashCard sx={{ flex: "1 1 320px" }}>
      <CardTitle title="Engagement funnel" hint="Real cohort counts at each step" />
      <Box sx={{ display: "flex", flexDirection: "column", gap: 1.75 }}>
        {steps.map((step, i) => (
          <StepRow key={step.stage} step={step} index={i} total={steps.length} />
        ))}
      </Box>
    </DashCard>
  );
}
