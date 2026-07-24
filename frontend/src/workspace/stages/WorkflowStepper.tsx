import { styled } from "@mui/material/styles";
import { tokens, focusRingOnBrand } from "../../theme/tokens";
import { accent } from "../../theme/stageTheme";

export const WORKFLOW_STAGES = [
  { id: 1, name: "Planning & Strategy", icon: "strategy", blurb: "Brief, multi-agent research and the Brand Engagement Plan." },
  { id: 2, name: "Engagement Orchestration", icon: "account_tree", blurb: "Turn the plan into an orchestrated journey: triggers, next-best-channel and cadence." },
  { id: 3, name: "Campaign Operations", icon: "dashboard", blurb: "Execute in parallel tracks by channel: assets, MLR status and tactics per lane." },
  { id: 4, name: "Reporting & Insights", icon: "insights", blurb: "Measurement scorecard, channel performance framework and insights." },
] as const;

/** Fill shared by the active tab and its concave flares. Must match what sits
 *  directly under the sub-bar (the chat pane's canvas) so the active tab reads
 *  as one continuous folder sheet with the workspace below. */
const FILL = tokens.color.canvas;
/** Radius of the tab's top corners and of the concave flares at its feet. */
const R = 12;

const Row = styled("div")({
  display: "flex",
  alignItems: "flex-end",
  width: "100%",
  // Room for the outermost tabs' concave flares.
  paddingLeft: R,
  paddingRight: R,
});

const Tab = styled("button")<{ active: boolean }>(({ active }) => ({
  position: "relative",
  flex: "1 1 0",
  minWidth: 0,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  gap: 8,
  padding: "9px 14px 11px",
  border: "none",
  font: "inherit",
  cursor: "pointer",
  whiteSpace: "nowrap",
  borderRadius: `${R}px ${R}px 0 0`,
  background: active ? FILL : "transparent",
  color: active ? tokens.color.text : "rgba(255,255,255,0.78)",
  fontWeight: active ? 700 : 600,
  fontSize: tokens.fontSize.sm,
  transition: "color 160ms ease, background 160ms ease",
  "& .tab-name": { overflow: "hidden", textOverflow: "ellipsis" },
  "&:hover": active ? undefined : { color: "#fff", background: "rgba(255,255,255,0.10)" },
  "&:focus-visible": { ...focusRingOnBrand, zIndex: 2 },
  // Concave flares where the active tab meets the workspace, for the folder look.
  "&::before, &::after": active
    ? {
        content: '""',
        position: "absolute",
        bottom: 0,
        width: R,
        height: R,
        pointerEvents: "none",
      }
    : undefined,
  "&::before": active
    ? { left: -R, background: `radial-gradient(circle ${R}px at 0 0, transparent ${R - 0.5}px, ${FILL} ${R}px)` }
    : undefined,
  "&::after": active
    ? { right: -R, background: `radial-gradient(circle ${R}px at 100% 0, transparent ${R - 0.5}px, ${FILL} ${R}px)` }
    : undefined,
}));

const StepNumber = styled("span")<{ active: boolean }>(({ active }) => ({
  width: 22,
  height: 22,
  flex: "0 0 auto",
  borderRadius: "50%",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  fontSize: tokens.fontSize.xs,
  fontWeight: 700,
  background: active ? accent.primary : "transparent",
  border: active ? "none" : "1.5px solid rgba(255,255,255,0.5)",
  color: active ? "#fff" : "rgba(255,255,255,0.85)",
  transition: "background 160ms ease, color 160ms ease, border-color 160ms ease",
}));

const SubChip = styled("span")({
  fontSize: 10,
  fontWeight: 700,
  letterSpacing: "0.06em",
  color: "inherit",
  opacity: 0.85,
});

/**
 * Folder-tab stage nav on the dark sub-bar: four numbered tabs spread across
 * the full width, and the active one is flush with the workspace below —
 * flaring into it like the tab of a paper folder. Every tab is always
 * clickable; there is no gating or forced order.
 */
export function WorkflowStepper({
  stage,
  onSelect,
  subLabel,
}: {
  stage: number;
  onSelect: (n: number) => void;
  /** Stage-1 sub-progress during a studio build, e.g. "SECTION 3/11". */
  subLabel?: string;
}) {
  return (
    <Row role="tablist">
      {WORKFLOW_STAGES.map((s) => {
        const active = s.id === stage;
        return (
          <Tab
            key={s.id}
            role="tab"
            aria-selected={active}
            active={active}
            title={s.blurb}
            onClick={() => onSelect(s.id)}
          >
            <StepNumber active={active}>{s.id}</StepNumber>
            <span className="tab-name">{s.name}</span>
            {s.id === 1 && subLabel && <SubChip>{subLabel}</SubChip>}
          </Tab>
        );
      })}
    </Row>
  );
}
