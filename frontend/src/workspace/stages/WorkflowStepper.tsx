import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import { tokens, shade, light, insetShadow, pressedShadow } from "../../theme/tokens";

export const WORKFLOW_STAGES = [
  { id: 1, name: "Planning & Strategy", icon: "strategy", blurb: "Brief, multi-agent research and the Brand Engagement Plan." },
  { id: 2, name: "Engagement Orchestration", icon: "account_tree", blurb: "Turn the plan into an orchestrated journey: triggers, next-best-channel and cadence." },
  { id: 3, name: "Campaign Operations", icon: "dashboard", blurb: "Execute in parallel tracks by channel — assets, MLR status and tactics per lane." },
  { id: 4, name: "Reporting & Insights", icon: "insights", blurb: "Measurement scorecard, channel performance framework and insights." },
] as const;

const StepButton = styled("button")<{ active: boolean; done: boolean; locked: boolean }>(({ theme, active, done, locked }) => ({
  display: "flex",
  alignItems: "center",
  gap: theme.spacing(2),
  padding: theme.spacing(1.5, 2.5),
  borderRadius: 10,
  border: `1px solid ${shade(active ? 0.3 : 0.16)}`,
  background: active
    ? `linear-gradient(180deg, ${shade(0.1)}, ${light(0.2)}), ${tokens.color.surface}`
    : tokens.color.surface,
  boxShadow: active ? pressedShadow : locked ? "none" : insetShadow,
  cursor: locked ? "not-allowed" : "pointer",
  opacity: locked ? 0.5 : 1,
  font: "inherit",
  flex: "1 1 0",
  minWidth: 0,
  transition: "box-shadow 150ms ease",
  "&:focus-visible": { outline: `2px solid ${tokens.color.text}`, outlineOffset: 2 },
  ...(done && { borderColor: shade(0.24) }),
}));

const NumBadge = styled(Box)<{ active: boolean; done: boolean }>(({ active, done }) => ({
  width: 26,
  height: 26,
  borderRadius: "50%",
  flex: "0 0 auto",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  background: active ? tokens.color.primary : done ? tokens.color.success : shade(0.1),
  color: active || done ? tokens.color.text : shade(0.5),
}));

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
    <Box sx={{ display: "flex", gap: 1, p: 2, borderBottom: `1px solid ${shade(0.14)}`, overflowX: "auto" }}>
      {WORKFLOW_STAGES.map((s) => {
        const active = s.id === stage;
        const done = unlocked && s.id < stage;
        const locked = s.id > 1 && !unlocked;
        return (
          <StepButton
            key={s.id}
            active={active}
            done={done}
            locked={locked}
            disabled={locked}
            title={locked ? "Complete Planning & Strategy first" : s.blurb}
            onClick={() => onSelect(s.id)}
          >
            <NumBadge active={active} done={done}>
              <span className="material-symbols-outlined" style={{ fontSize: 15 }}>
                {locked ? "lock" : done ? "check" : s.icon}
              </span>
            </NumBadge>
            <Box sx={{ textAlign: "left", minWidth: 0 }}>
              <Typography sx={{ fontWeight: 700, fontSize: 12, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{s.name}</Typography>
              <Typography variant="caption" sx={{ color: "text.secondary" }}>Stage {s.id}</Typography>
            </Box>
          </StepButton>
        );
      })}
    </Box>
  );
}
