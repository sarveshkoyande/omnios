import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import { tokens, glass, glassFallback, indigoTint } from "../../theme/tokens";

export const WORKFLOW_STAGES = [
  { id: 1, name: "Planning & Strategy", icon: "strategy", blurb: "Brief, multi-agent research and the Brand Engagement Plan." },
  { id: 2, name: "Campaign Setup & Orchestration", icon: "account_tree", blurb: "Stand up delivery: Jira, stakeholder register, vendors, timeline, resourcing, RACI and BRD." },
  { id: 3, name: "Campaign Operations", icon: "dashboard", blurb: "Execute in parallel tracks by channel — assets, MLR status and tactics per lane." },
  { id: 4, name: "Reporting & Insights", icon: "insights", blurb: "Measurement scorecard, channel performance framework and insights." },
] as const;

type StepState = "active" | "done" | "locked" | "idle";

const StepButton = styled("button")<{ state: StepState }>(({ theme, state }) => {
  const active = state === "active";
  const locked = state === "locked";
  return {
    display: "flex",
    alignItems: "center",
    gap: theme.spacing(1.5),
    padding: theme.spacing(1.5, 2),
    borderRadius: tokens.radius.md,
    flex: "1 1 0",
    minWidth: 0,
    font: "inherit",
    textAlign: "left",
    cursor: locked ? "not-allowed" : "pointer",
    transition: "background 160ms ease, box-shadow 160ms ease, border-color 160ms ease",
    // Tier B for active, translucent frosted chip otherwise.
    background: active ? glassFallback : "rgba(255,255,255,0.32)",
    border: active ? glass.borderTint : `1px solid ${indigoTint(0.1)}`,
    boxShadow: active ? glass.shadowElevated : "none",
    color: locked ? tokens.color.inkSoft : tokens.color.text,
    "@supports ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px)))": {
      background: active ? glass.panelStrong : "rgba(255,255,255,0.32)",
      backdropFilter: glass.blur,
      WebkitBackdropFilter: glass.blur,
    },
    "&:hover": locked ? {} : { background: glass.panelStrong, borderColor: indigoTint(0.2) },
    "&:focus-visible": { outline: `2px solid ${tokens.color.primary}`, outlineOffset: 2 },
  };
});

const Circle = styled("span")<{ state: StepState }>(({ state }) => {
  const active = state === "active";
  const done = state === "done";
  return {
    width: 30,
    height: 30,
    borderRadius: "50%",
    flex: "0 0 auto",
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    background: active
      ? `linear-gradient(180deg, ${tokens.color.primary}, ${tokens.color.secondary})`
      : done
        ? indigoTint(0.14)
        : "rgba(255,255,255,0.6)",
    border: done ? `1px solid ${indigoTint(0.3)}` : "1px solid rgba(255,255,255,0.7)",
    color: active ? "#fff" : done ? tokens.color.primary : tokens.color.inkSoft,
    boxShadow: active ? "0 2px 8px rgba(79,70,229,0.4)" : "none",
  };
});

export function WorkflowStepper({
  stage,
  unlocked,
  onSelect,
}: {
  stage: number;
  unlocked: boolean;
  onSelect: (n: number) => void;
}) {
  return (
    <Box sx={{ display: "flex", gap: 1.5, p: 2, overflowX: "auto" }}>
      {WORKFLOW_STAGES.map((s) => {
        const locked = s.id > 1 && !unlocked;
        const state: StepState = s.id === stage ? "active" : locked ? "locked" : unlocked && s.id < stage ? "done" : "idle";
        return (
          <StepButton
            key={s.id}
            state={state}
            aria-disabled={locked || undefined}
            aria-current={state === "active" ? "step" : undefined}
            title={locked ? "Locked — complete Planning & Strategy first" : s.blurb}
            onClick={() => !locked && onSelect(s.id)}
          >
            <Circle state={state}>
              <span className="material-symbols-outlined" style={{ fontSize: 17 }}>
                {locked ? "lock" : state === "done" ? "check" : s.icon}
              </span>
            </Circle>
            <Box sx={{ minWidth: 0 }}>
              <Typography sx={{ fontWeight: 700, fontSize: tokens.fontSize.md, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", lineHeight: 1.25 }}>
                {s.name}
              </Typography>
              <Typography sx={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.08em", color: locked ? "text.secondary" : "primary.main" }}>
                {`STAGE ${s.id}`}
              </Typography>
            </Box>
          </StepButton>
        );
      })}
    </Box>
  );
}
