import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import type { StudioState } from "./studio/studioTypes";
import { indigoTint, tokens, motion, hoverOnly } from "../theme/tokens";

/** Static, known-ahead-of-time titles for the Sequential Plan Studio sections
 * (strategy/studio_run.py's SEQUENCE, resolved against plan_document._SECTION_TABLE) --
 * shown before a section is even reached, not just once it lands.
 *
 * Only the sections that actually render are listed, in run order, so row N here is the Nth
 * section the studio emits. Steps marked `render: False` in SEQUENCE still run and still ask
 * their question -- they just produce no section, so they have no row and the numbering
 * closes up behind them. The campaign brief is absent for a different reason: it has its own
 * pinned row below and its own artifact panel. */
export const SECTION_TITLES = [
  "Message Flow Template",
  "Channel Selection Template",
  "Map Existing Content & Identify",
  "Design Channel Flow",
  "Design Message Flow",
  "Metrics to Track CX Success",
  "CX Execution Work Plan",
  "Develop Closed Loop Model",
  "Tactical plan overview & CSF map",
  "Field approach & targeting",
  "Omnichannel & media tactics",
];

/** Fired by a row's onClick; AssemblyCanvas listens for this to expand (if
 * collapsed) and scroll to the matching rendered section. */
export const SCROLL_TO_SECTION_EVENT = "omni:scroll-to-section";

const Row = styled(Box)<{ active?: boolean; clickable?: boolean }>(({ theme, active, clickable }) => ({
  display: "flex",
  alignItems: "center",
  gap: theme.spacing(1.5),
  padding: theme.spacing(1, 1.25),
  borderRadius: tokens.radius.sm,
  borderLeft: `3px solid ${active ? tokens.color.primary : "transparent"}`,
  background: active ? tokens.color.primaryContainer : "transparent",
  cursor: clickable ? "pointer" : "default",
  transition: [
    `background ${motion.duration.hover} ${motion.easeOut}`,
    `border-left-color ${motion.duration.hover} ${motion.easeOut}`,
    `transform ${motion.duration.press} ${motion.easeOut}`,
  ].join(", "),
  ...(clickable
    ? {
        [hoverOnly]: { "&:hover": { background: indigoTint(0.08) } },
        "&:active": { transform: "scale(0.98)" },
      }
    : {}),
}));

const Dot = styled(Box)<{ state: "done" | "active" | "pending" }>(({ state }) => ({
  flex: "0 0 auto",
  // 24 rather than 20: the numeral inside is 15px now and was touching the circle.
  width: 24,
  height: 24,
  borderRadius: "50%",
  display: "grid",
  placeItems: "center",
  fontSize: 15,
  color: state === "pending" ? tokens.color.inkSoft : "#fff",
  background: state === "done" ? tokens.color.success : "transparent",
  border: state === "pending" ? `1.5px solid ${indigoTint(0.3)}` : "none",
}));

/** Left-rail table of contents for the Sequential Plan Studio build (Stage 1) --
 * every title shown upfront, checked off as each lands; the in-progress one shows
 * a spinner instead of a tick. Completed rows are clickable and jump the main pane
 * to that section. */
/**
 * How many section rows a plan actually has.
 *
 * NOT `studio.total` -- that is the length of the studio SEQUENCE (19), which counts the
 * ask-only steps that pose a question and emit no section. Showing it as a section count
 * told the user "19 sections" next to a list of 11, and made a finished plan look two-thirds
 * done. Anything that renders "x of y sections" must use this.
 */
export const sectionTotal = (studio: StudioState) =>
  Math.max(SECTION_TITLES.length, studio.sections.length);

export function PlanSectionsRail({ studio }: { studio: StudioState }) {
  const doneCount = studio.sections.length;
  const rows = SECTION_TITLES.map((title, i) => {
    const num = i + 1;
    const completed = studio.sections[i];
    const isActive = !completed && studio.slot && num === doneCount + 1;
    if (completed) return { num, title, state: "done" as const, sectionId: completed.section_id };
    if (isActive) return { num, title, state: "active" as const, sectionId: null };
    return { num, title, state: "pending" as const, sectionId: null };
  });

  const goToSection = (sectionId: string) => {
    window.dispatchEvent(new CustomEvent(SCROLL_TO_SECTION_EVENT, { detail: { sectionId } }));
  };

  const goToAnchor = (domId: string) => {
    document.getElementById(domId)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const briefReady = studio.done;
  const trailReady = studio.records.length > 0;

  return (
    <Box sx={{ width: 280, flex: "0 0 280px", borderRight: `1px solid ${indigoTint(0.1)}`, overflowY: "auto", py: 2 }}>
      <Box sx={{ px: 1.25, mb: 2 }}>
        {/* The PLAN brief -- the inputs -- exists from the moment the workspace opens, so this
            row is never gated. The CAMPAIGN brief below it is the run's output and waits. */}
        <Row clickable onClick={() => goToAnchor("plan-brief-anchor")}>
          <Box sx={{ flex: "0 0 auto", width: 20, display: "grid", placeItems: "center" }}>
            <span className="material-symbols-outlined" style={{ fontSize: 17, color: tokens.color.primary }}>assignment</span>
          </Box>
          <Typography sx={{ fontSize: 15, fontWeight: 700, flex: 1 }}>Plan brief</Typography>
        </Row>
        <Row clickable={briefReady} onClick={briefReady ? () => goToAnchor("campaign-brief-anchor") : undefined}>
          <Box sx={{ flex: "0 0 auto", width: 20, display: "grid", placeItems: "center" }}>
            <span className="material-symbols-outlined" style={{ fontSize: 17, color: tokens.color.primary }}>assignment_turned_in</span>
          </Box>
          <Typography sx={{ fontSize: 15, fontWeight: 700, flex: 1 }}>Campaign brief</Typography>
          <Chip
            size="small"
            label={briefReady ? "Ready" : "Drafting"}
            sx={{
              height: 24,
              fontSize: 15,
              fontWeight: 700,
              color: briefReady ? "#fff" : tokens.color.inkSoft,
              background: briefReady ? tokens.color.success : indigoTint(0.1),
            }}
          />
        </Row>
        <Row clickable={trailReady} onClick={trailReady ? () => goToAnchor("decision-trail-anchor") : undefined}>
          <Box sx={{ flex: "0 0 auto", width: 20, display: "grid", placeItems: "center" }}>
            <span className="material-symbols-outlined" style={{ fontSize: 17, color: tokens.color.primary }}>psychology</span>
          </Box>
          <Typography sx={{ fontSize: 15, fontWeight: 700, flex: 1 }}>Decision trail</Typography>
        </Row>
      </Box>

      <Box sx={{ px: 2, mb: 1.5, display: "flex", alignItems: "baseline", gap: 1 }}>
        <Typography sx={{ fontWeight: 700, fontSize: 15 }}>Plan sections</Typography>
        <Typography variant="caption" sx={{ color: "text.secondary" }}>
          {doneCount}/{sectionTotal(studio)} completed
        </Typography>
      </Box>
      {rows.map((r) => (
        <Row
          key={r.num}
          active={r.state === "active"}
          clickable={r.state === "done"}
          onClick={r.state === "done" && r.sectionId ? () => goToSection(r.sectionId!) : undefined}
        >
          <Dot state={r.state}>
            {r.state === "done" ? (
              <span className="material-symbols-outlined" style={{ fontSize: 15 }}>check</span>
            ) : r.state === "active" ? (
              <CircularProgress size={13} thickness={6} />
            ) : (
              ""
            )}
          </Dot>
          <Typography
            sx={{
              fontSize: 15,
              fontWeight: r.state === "active" ? 700 : 400,
              color: r.state === "pending" ? "text.secondary" : "text.primary",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {r.num}. {r.title}
          </Typography>
        </Row>
      ))}
    </Box>
  );
}
