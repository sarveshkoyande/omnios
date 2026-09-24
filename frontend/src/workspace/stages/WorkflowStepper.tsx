import { styled } from "@mui/material/styles";
import { tokens, focusRingOnBrand, motion, hoverOnly } from "../../theme/tokens";
import { stageMark } from "../../theme/stageTheme";
import { GLOSSARY } from "../../glossary";

/** Tab order is this array's order; `id` is the routing key and never changes. The two are
 *  deliberately decoupled so a tab can be inserted mid-way (see id 5, the Campaign Ops
 *  sandbox sitting after the flow planner) without renumbering every existing stage and the
 *  `stage === n` checks throughout Workspace.tsx / useWorkspace.ts. The number rendered on
 *  each tab is its position here, not its id. */
export const WORKFLOW_STAGES = [
  { id: 1, name: "Planning & Strategy", icon: "strategy", blurb: `Brief, multi-agent research and the ${GLOSSARY.campaign_plan.label}.` },
  { id: 2, name: "Engagement Orchestration", icon: "account_tree", blurb: "Turn the plan into an orchestrated journey: triggers, next-best-channel and cadence." },
  { id: 3, name: "Campaign Operations", icon: "dashboard", blurb: "Execute in parallel tracks by channel: assets, MLR status and tactics per lane." },
  { id: 5, name: "Campaign Ops (2)", icon: "checklist_rtl", blurb: "Sandbox: launch readiness — deliverables, coverage, approvals and the go-live verdict." },
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
  // Marker slot 2: the active tab is the only tab that carries the stage's colour, and it
  // carries it as a 3px top edge rather than a fill. Inset so it follows the tab's radius.
  boxShadow: active ? `inset 0 3px 0 0 ${stageMark.primary}` : "none",
  color: active ? tokens.color.text : "rgba(255,255,255,0.78)",
  fontWeight: active ? 700 : 600,
  fontSize: tokens.fontSize.sm,
  transition: [
    `color ${motion.duration.hover} ${motion.easeOut}`,
    `background ${motion.duration.hover} ${motion.easeOut}`,
    // The tab is a button, so it owes the same press feedback as every other pressable
    // surface -- and it has to land under the finger, hence the shorter press duration.
    `transform ${motion.duration.press} ${motion.easeOut}`,
  ].join(", "),
  "& .tab-name": { overflow: "hidden", textOverflow: "ellipsis" },
  // Ungated, a tap on a touch device left the hover fill stuck on the tab it just left.
  [hoverOnly]: {
    "&:hover": active ? undefined : { color: "#fff", background: "rgba(255,255,255,0.10)" },
  },
  // Only the inactive tabs press: pressing the tab you are already on would animate a
  // no-op. Origin is the foot of the tab so it stays hinged to the workspace sheet.
  "&:active": active ? undefined : { transform: "scale(0.98)" },
  transformOrigin: "50% 100%",
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
  background: active ? stageMark.primary : "transparent",
  border: active ? "none" : "1.5px solid rgba(255,255,255,0.5)",
  color: active ? "#fff" : "rgba(255,255,255,0.85)",
  transition: [
    `background ${motion.duration.hover} ${motion.easeOut}`,
    `color ${motion.duration.hover} ${motion.easeOut}`,
    `border-color ${motion.duration.hover} ${motion.easeOut}`,
  ].join(", "),
}));

const SubChip = styled("span")({
  fontSize: 15,
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
      {WORKFLOW_STAGES.map((s, i) => {
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
            {/* Position, not id — so the inserted sandbox tab reads 1..5 left to right. */}
            <StepNumber active={active}>{i + 1}</StepNumber>
            <span className="tab-name">{s.name}</span>
            {s.id === 1 && subLabel && <SubChip>{subLabel}</SubChip>}
          </Tab>
        );
      })}
    </Row>
  );
}
