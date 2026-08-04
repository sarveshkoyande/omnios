import { keyframes } from "@emotion/react";
import { useEffect, useState } from "react";
import Accordion from "@mui/material/Accordion";
import AccordionDetails from "@mui/material/AccordionDetails";
import AccordionSummary from "@mui/material/AccordionSummary";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import { tokens } from "../../theme/tokens";
import { AgentAvatar } from "../Avatar";
import { PlanDocument } from "../PlanDocument";
import { SCROLL_TO_SECTION_EVENT, sectionTotal } from "../PlanSectionsRail";
import { STAGE_AGENTS } from "../types";
import type { StudioState } from "./studioTypes";

/**
 * AssemblyCanvas is the LIVE PLAN PREVIEW for the sequential studio run: renders the real
 * Brand Engagement Plan content ONE section at a time (not an endless stacked scroll) --
 * whichever section is currently "in view". By default that follows the live build (the
 * section currently drafting, or the one that just landed); clicking a completed row in the
 * Plan Sections rail pins the view to that section instead, until "Jump to latest" is clicked.
 */
const shimmerMove = keyframes`
  from { background-position: 200% 0; }
  to { background-position: 0 0; }
`;

const Shimmer = styled("div")({
  height: 9,
  borderRadius: tokens.radius.pill,
  marginTop: 8,
  background: `linear-gradient(90deg, ${tokens.color.primaryContainer} 25%, ${tokens.color.surface} 50%, ${tokens.color.primaryContainer} 75%)`,
  backgroundSize: "200% 100%",
  animation: `${shimmerMove} 1.2s linear infinite`,
});

const GroundChip = styled("span")({
  display: "inline-flex",
  alignItems: "center",
  gap: 5,
  fontSize: 15,
  fontWeight: 600,
  color: tokens.color.primary,
  background: tokens.color.primaryContainer,
  border: `1px solid ${tokens.color.outline}`,
  borderRadius: tokens.radius.pill,
  padding: "3px 10px",
  margin: "4px 6px 0 0",
  "&::before": { content: '""', width: 6, height: 6, borderRadius: 2, background: tokens.color.primary },
});

const ProgressTrack = styled("div")({
  height: 6,
  borderRadius: tokens.radius.pill,
  background: tokens.color.primaryContainer,
  overflow: "hidden",
  marginTop: 10,
  marginBottom: 4,
});

const ProgressFill = styled("div")({
  height: "100%",
  borderRadius: tokens.radius.pill,
  background: tokens.color.primary,
  transition: "width 500ms ease",
});

export function AssemblyCanvas({ studio, onSkip }: { studio: StudioState; onSkip: () => void }) {
  const built = studio.sections.length;
  const activeDisplayNum = built + 1;
  // Section count, not `studio.total` (the 19-step SEQUENCE, 8 of which are ask-only and
  // emit no section) -- see sectionTotal in PlanSectionsRail.
  const total = sectionTotal(studio);
  const pct = total > 0 ? Math.round((built / total) * 100) : 0;
  const latestSection = built > 0 ? studio.sections[built - 1] : null;

  // null = "follow live" (whatever's currently drafting, or the most recently landed section).
  // Set to a specific id when the user clicks an older completed section in the rail.
  const [pinnedId, setPinnedId] = useState<string | null>(null);

  // Auto-open while the build is actively running so the live plan is visible instead of hiding
  // behind a collapsed summary; collapses once done (the finished plan renders below). The
  // user's own manual toggle wins until the next run starts.
  const [manualExpanded, setManualExpanded] = useState<boolean | null>(null);
  useEffect(() => {
    if (studio.active && !studio.done) setManualExpanded(null);
  }, [studio.active]);
  const expanded = manualExpanded ?? (studio.active && !studio.done);

  // The Plan Sections rail dispatches this when a completed section is clicked -- pin the
  // canvas to that section (expanding it first if collapsed).
  useEffect(() => {
    const onGoTo = (e: Event) => {
      const sectionId = (e as CustomEvent<{ sectionId: string }>).detail?.sectionId;
      if (!sectionId) return;
      setManualExpanded(true);
      setPinnedId(sectionId);
    };
    window.addEventListener(SCROLL_TO_SECTION_EVENT, onGoTo);
    return () => window.removeEventListener(SCROLL_TO_SECTION_EVENT, onGoTo);
  }, []);

  const pinnedSection = pinnedId ? studio.sections.find((s) => s.section_id === pinnedId) ?? null : null;
  const viewingPinned = pinnedSection !== null;
  const showingLatestWhilePinned = viewingPinned && pinnedSection.section_id === latestSection?.section_id;

  return (
    <Accordion
      expanded={expanded}
      onChange={(_e, isExpanded) => setManualExpanded(isExpanded)}
      sx={{
        background: tokens.color.surface,
        border: `1px solid ${tokens.color.outline}`,
        borderRadius: tokens.radius.md,
        boxShadow: "none",
        "&:before": { display: "none" },
      }}
    >
      <AccordionSummary expandIcon={<span className="material-symbols-outlined">expand_more</span>}>
        <Box sx={{ width: "100%" }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
            <Typography
              sx={{
                fontSize: tokens.fontSize.xs,
                fontWeight: 700,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                color: "primary.main",
                flex: 1,
              }}
            >
              {studio.done ? "Plan canvas" : "Building your plan — live"} · {built}/{total}
            </Typography>
            {viewingPinned && !showingLatestWhilePinned && (
              <Button
                variant="text"
                size="small"
                onClick={(e) => { e.stopPropagation(); setPinnedId(null); }}
                onFocus={(e) => e.stopPropagation()}
                sx={{ fontSize: tokens.fontSize.xs }}
              >
                Jump to latest
              </Button>
            )}
            {!studio.done && (
              <Button
                variant="text"
                size="small"
                onClick={(e) => {
                  e.stopPropagation();
                  onSkip();
                }}
                onFocus={(e) => e.stopPropagation()}
                sx={{ fontSize: tokens.fontSize.xs }}
              >
                Skip ahead
              </Button>
            )}
          </Box>
          {!studio.done && studio.total > 0 && (
            <Box onClick={(e) => e.stopPropagation()}>
              <ProgressTrack>
                <ProgressFill style={{ width: `${pct}%` }} />
              </ProgressTrack>
            </Box>
          )}
        </Box>
      </AccordionSummary>
      <AccordionDetails>
        {/* Exactly one section's content is shown at a time -- no stacked/endless scroll. */}
        <Box>
          {viewingPinned ? (
            <>
              <Typography sx={{ fontSize: tokens.fontSize.xs, fontWeight: 700, color: "text.secondary", mb: 0.75 }}>
                {pinnedSection.num} · {pinnedSection.title}
              </Typography>
              <PlanDocument html={pinnedSection.html} editing={false} />
              {studio.slot && (
                <Typography variant="caption" sx={{ color: "text.secondary", fontStyle: "italic", display: "block", mt: 1.5 }}>
                  A new section is drafting live — <Box component="span" onClick={() => setPinnedId(null)} sx={{ color: "primary.main", cursor: "pointer", fontWeight: 700 }}>jump to it</Box>.
                </Typography>
              )}
            </>
          ) : studio.slot ? (
            <Box>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <Typography sx={{ fontWeight: 700, fontSize: tokens.fontSize.md, flex: 1 }}>
                  {activeDisplayNum} · {studio.slot.title}
                </Typography>
                <Box
                  component="span"
                  sx={{
                    fontSize: 15,
                    fontWeight: 700,
                    letterSpacing: "0.07em",
                    color: "#fff",
                    background: tokens.color.primary,
                    borderRadius: 999,
                    px: 1.25,
                    py: 0.4,
                  }}
                >
                  DRAFTING
                </Box>
              </Box>
              <Box sx={{ display: "flex", alignItems: "center", gap: 0.75, mt: 0.5 }}>
                <AgentAvatar id={STAGE_AGENTS.planning.id} size={16} />
                <Typography variant="caption" sx={{ color: "text.secondary" }}>{studio.slot.ownerName}</Typography>
              </Box>

              {studio.slot.state === "ground" && (
                <Box sx={{ mt: 1 }}>
                  {studio.slot.grounding.length === 0 ? (
                    <>
                      <Typography variant="body2" sx={{ color: "text.secondary" }}>
                        Pulling from the Omni OS knowledge graph…
                      </Typography>
                      <Shimmer />
                    </>
                  ) : (
                    <Box>
                      {studio.slot.grounding.map((g, i) => (
                        <GroundChip key={i} title={g.snippet}>{g.source} · {g.label}</GroundChip>
                      ))}
                      <Shimmer />
                    </Box>
                  )}
                </Box>
              )}
              {studio.slot.state === "ask" && (
                <Typography variant="body2" sx={{ color: "text.secondary", mt: 1, fontStyle: "italic" }}>
                  Waiting on your answer in the conversation…
                </Typography>
              )}
              {studio.slot.state === "draft" && (
                <Box sx={{ mt: 1 }}>
                  <Typography variant="body2" sx={{ color: "text.secondary" }}>{studio.slot.draftNote}</Typography>
                  <Shimmer />
                </Box>
              )}
            </Box>
          ) : latestSection ? (
            <Box>
              <Typography sx={{ fontSize: tokens.fontSize.xs, fontWeight: 700, color: "text.secondary", mb: 0.75 }}>
                {built} · {latestSection.title}
              </Typography>
              <PlanDocument html={latestSection.html} editing={false} />
            </Box>
          ) : (
            <Typography variant="body2" sx={{ color: "text.secondary" }}>
              Your plan will appear here section by section as it's built…
            </Typography>
          )}

          {studio.done && !viewingPinned && (
            <Typography variant="body2" sx={{ color: "success.main", fontWeight: 600, textAlign: "center", mt: 1 }}>
              ✓ All {total} sections assembled.
            </Typography>
          )}
        </Box>
      </AccordionDetails>
    </Accordion>
  );
}
