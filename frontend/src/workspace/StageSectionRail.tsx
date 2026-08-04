import { useEffect, useMemo, useState } from "react";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import { accent } from "../theme/stageTheme";
import { indigoTint, tokens, motion, hoverOnly } from "../theme/tokens";

/**
 * StageSectionRail — the left-hand table of contents for Stages 2-4, mirroring Stage 1's
 * PlanSectionsRail. Each row jumps the main pane to a section anchor and highlights the one
 * currently scrolled into view. The section list is static per stage, but a section's anchor
 * may not exist yet (data still loading, or a conditional panel), so the rail scans the DOM and
 * only shows rows whose anchor is actually present, re-scanning as panels mount.
 */
export interface RailSection {
  /** DOM id of the section's anchor element in the stage content. */
  id: string;
  label: string;
  icon: string;
}

/** Anchor ids here must match the `id`s set on the panels in each stage component. */
export const ORCH_SECTIONS: RailSection[] = [
  { id: "orch-timeline", label: "Timeline & time-saved", icon: "timeline" },
  { id: "orch-activities", label: "Activities & setup tasks", icon: "checklist" },
  { id: "orch-agent", label: "Nudge agent", icon: "smart_toy" },
];

export const OPS_SECTIONS: RailSection[] = [
  { id: "ops-summary", label: "Planning summary", icon: "summarize" },
  { id: "ops-flow", label: "Engagement flow", icon: "account_tree" },
];

export const REPORT_SECTIONS: RailSection[] = [
  { id: "rep-funnel", label: "Stage-promotion signals", icon: "conversion_path" },
  { id: "rep-kpicards", label: "Delivery & engagement KPIs", icon: "speed" },
  { id: "rep-demographics", label: "HCP audience", icon: "groups" },
  { id: "rep-tagging", label: "Link & tagging matrix", icon: "link" },
  { id: "rep-test", label: "Test design", icon: "science" },
  { id: "rep-kpi", label: "KPI scorecard", icon: "scoreboard" },
  { id: "rep-channels", label: "Channel measurement", icon: "insights" },
  { id: "rep-tml", label: "Test · Measure · Learn", icon: "biotech" },
];

const Row = styled(Box)<{ active?: boolean }>(({ theme, active }) => ({
  display: "flex",
  alignItems: "center",
  gap: theme.spacing(1.25),
  padding: theme.spacing(1, 1.25),
  borderRadius: tokens.radius.sm,
  borderLeft: `3px solid ${active ? accent.primary : "transparent"}`,
  background: active ? accent.container : "transparent",
  cursor: "pointer",
  transition: [
    `background ${motion.duration.hover} ${motion.easeOut}`,
    `border-left-color ${motion.duration.hover} ${motion.easeOut}`,
    `transform ${motion.duration.press} ${motion.easeOut}`,
  ].join(", "),
  [hoverOnly]: { "&:hover": { background: active ? accent.container : indigoTint(0.08) } },
  "&:active": { transform: "scale(0.98)" },
}));

/** Which of `sections` currently have an anchor element mounted, re-scanned on DOM changes. */
function useExistingSections(sections: RailSection[]): RailSection[] {
  const [presentIds, setPresentIds] = useState<string[]>([]);
  useEffect(() => {
    const scan = () => {
      const present = sections.filter((s) => document.getElementById(s.id)).map((s) => s.id);
      setPresentIds((prev) =>
        prev.length === present.length && prev.every((v, i) => v === present[i]) ? prev : present,
      );
    };
    scan();
    // Panels mount asynchronously (data fetches, conditional sections); re-scan on any DOM change.
    const observer = new MutationObserver(scan);
    observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, [sections]);
  return useMemo(() => sections.filter((s) => presentIds.includes(s.id)), [sections, presentIds]);
}

export function StageSectionRail({ sections, title = "Sections" }: { sections: RailSection[]; title?: string }) {
  const visible = useExistingSections(sections);
  const [activeId, setActiveId] = useState<string>("");

  useEffect(() => {
    const els = visible.map((s) => document.getElementById(s.id)).filter((el): el is HTMLElement => Boolean(el));
    if (!els.length) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const inView = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (inView[0]) setActiveId(inView[0].target.id);
      },
      // Trip the active row when a section reaches the upper third of the viewport.
      { rootMargin: "-15% 0px -70% 0px", threshold: 0 },
    );
    els.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [visible]);

  const go = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
    setActiveId(id);
  };

  // Nothing to navigate yet — don't show an empty rail (avoids a bare column before content loads).
  if (visible.length === 0) return null;

  return (
    <Box sx={{ width: 240, flex: "0 0 240px", borderRight: `1px solid ${indigoTint(0.1)}`, overflowY: "auto", py: 2 }}>
      <Box sx={{ px: 2, mb: 1.5 }}>
        <Typography sx={{ fontWeight: 700, fontSize: 15 }}>{title}</Typography>
      </Box>
      <Box sx={{ px: 1.25 }}>
        {visible.map((s) => (
          <Row key={s.id} active={s.id === activeId} onClick={() => go(s.id)}>
            <span className="material-symbols-outlined" style={{ fontSize: 18, flex: "0 0 auto", color: accent.primary }}>
              {s.icon}
            </span>
            <Typography sx={{ fontSize: 15, fontWeight: s.id === activeId ? 700 : 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {s.label}
            </Typography>
          </Row>
        ))}
      </Box>
    </Box>
  );
}
