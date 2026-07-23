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
import { SCROLL_TO_SECTION_EVENT } from "../PlanSectionsRail";
import { STAGE_AGENTS } from "../types";
import type { StudioState } from "./studioTypes";

/**
 * AssemblyCanvas is the LIVE PLAN PREVIEW for the sequential studio run: instead of an
 * abstract build-trace (dots + placeholder cards), it renders the real Brand Engagement Plan
 * document growing section-by-section as each one lands, with the currently-drafting section
 * shown inline at the bottom. Auto-expanded while a build runs; collapses to a one-line
 * summary once done, since the finished brief + plan take over below it.
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

const settleIn = keyframes`
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: none; }
`;

const GroundChip = styled("span")({
  display: "inline-flex",
  alignItems: "center",
  gap: 5,
  fontSize: 10.5,
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

/** One real section of the plan, rendered as document content as soon as it lands. */
const SectionBlock = styled("div")({
  animation: `${settleIn} 420ms ease`,
  paddingBottom: 18,
  marginBottom: 18,
  borderBottom: `1px solid ${tokens.color.outline}`,
  "&:last-of-type": { borderBottom: "none", marginBottom: 0, paddingBottom: 0 },
});

export function AssemblyCanvas({
  studio,
  onSkip,
  onContinue,
}: {
  studio: StudioState;
  onSkip: () => void;
  onContinue?: () => void;
}) {
  const built = studio.sections.length;
  const activeDisplayNum = built + 1;
  const pct = studio.total > 0 ? Math.round((built / studio.total) * 100) : 0;

  // Auto-open while the build is actively running so the live plan is visible instead of hiding
  // behind a collapsed summary; collapses once done (the finished plan renders below). The
  // user's own manual toggle wins until the next run starts.
  const [manualExpanded, setManualExpanded] = useState<boolean | null>(null);
  useEffect(() => {
    if (studio.active && !studio.done) setManualExpanded(null);
  }, [studio.active]);
  const expanded = manualExpanded ?? (studio.active && !studio.done);

  // The Plan Sections rail dispatches this when a completed section is clicked --
  // expand (if collapsed) and scroll the real rendered section into view.
  useEffect(() => {
    const onGoTo = (e: Event) => {
      const sectionId = (e as CustomEvent<{ sectionId: string }>).detail?.sectionId;
      if (!sectionId) return;
      setManualExpanded(true);
      requestAnimationFrame(() => {
        setTimeout(() => {
          document.getElementById(`plan-section-${sectionId}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
        }, 60);
      });
    };
    window.addEventListener(SCROLL_TO_SECTION_EVENT, onGoTo);
    return () => window.removeEventListener(SCROLL_TO_SECTION_EVENT, onGoTo);
  }, []);

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
              {studio.done ? "Plan canvas" : "Building your plan — live"} · {built}/{studio.total}
            </Typography>
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
        {/* The live plan preview: every built section rendered as real document content,
            growing top-to-bottom, with the active section drafting inline at the bottom. */}
        <Box>
          {studio.sections.map((s, idx) => (
            <SectionBlock key={s.section_id} id={`plan-section-${s.section_id}`}>
              <Typography
                sx={{ fontSize: tokens.fontSize.xs, fontWeight: 700, color: "text.secondary", mb: 0.75 }}
              >
                {idx + 1} · {s.title}
              </Typography>
              <PlanDocument html={s.html} editing={false} />
            </SectionBlock>
          ))}

          {studio.slot && (
            <SectionBlock>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <Typography sx={{ fontWeight: 700, fontSize: tokens.fontSize.md, flex: 1 }}>
                  {activeDisplayNum} · {studio.slot.title}
                </Typography>
                <Box
                  component="span"
                  sx={{
                    fontSize: 10,
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
            </SectionBlock>
          )}

          {studio.awaitingContinue && !studio.done && (
            <Box sx={{ display: "flex", justifyContent: "flex-end", mt: 1.5, pt: 1.5, borderTop: `1px solid ${tokens.color.outline}` }}>
              <Button variant="contained" size="small" onClick={onContinue} endIcon={<span className="material-symbols-outlined" style={{ fontSize: 16 }}>arrow_forward</span>}>
                Continue to next section
              </Button>
            </Box>
          )}
          {built === 0 && !studio.slot && !studio.awaitingContinue && (
            <Typography variant="body2" sx={{ color: "text.secondary" }}>
              Your plan will appear here section by section as it's built…
            </Typography>
          )}
          {studio.done && (
            <Typography variant="body2" sx={{ color: "success.main", fontWeight: 600, textAlign: "center", mt: 1 }}>
              ✓ All {studio.total} sections assembled.
            </Typography>
          )}
        </Box>
      </AccordionDetails>
    </Accordion>
  );
}
