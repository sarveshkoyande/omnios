import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import type { ProjectSummary } from "../workspace/types";
import { tokens, indigoTint, motion, hoverOnly } from "../theme/tokens";

/**
 * PlanCard — a wide, horizontal, clickable card for one saved plan on the Home
 * dashboard. Reads the enriched ProjectSummary digest (brand / campaign / therapy
 * area / lifecycle / status) so the portfolio of in-flight plans is scannable at a
 * glance and one click deep. Status is derived from phase + has_result.
 */
type Status = { label: string; color: string; bg: string; icon: string };

function deriveStatus(p: ProjectSummary): Status {
  if (p.has_result || p.phase === "done") {
    return { label: "Plan ready", color: tokens.color.success, bg: tokens.color.successSoft, icon: "task_alt" };
  }
  if (p.phase === "running") {
    return { label: "Building plan", color: tokens.color.primary, bg: tokens.color.infoSoft, icon: "autorenew" };
  }
  return { label: "Drafting brief", color: tokens.color.warningInk, bg: tokens.color.warningSoft, icon: "edit_note" };
}

const LIFECYCLE_LABEL: Record<string, string> = {
  launch: "Launch",
  growth: "Growth",
  mature: "Mature",
  loe: "Loss of exclusivity",
};

function relativeTime(iso?: string): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const mins = Math.round((Date.now() - then) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.round(hrs / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

const Root = styled("button")({
  display: "flex",
  alignItems: "center",
  gap: 20,
  width: "100%",
  textAlign: "left",
  font: "inherit",
  cursor: "pointer",
  padding: "18px 22px",
  borderRadius: tokens.radius.lg,
  background: tokens.color.surface,
  border: `1px solid ${tokens.color.outline}`,
  transition: [
    `border-color ${motion.duration.hover} ${motion.easeOut}`,
    `background-color ${motion.duration.hover} ${motion.easeOut}`,
    `transform ${motion.duration.press} ${motion.easeOut}`,
  ].join(", "),
  [hoverOnly]: {
    "&:hover": { borderColor: tokens.color.primary, background: indigoTint(0.035) },
  },
  // The card is large, so the press scale is smaller than a button's -- 0.97 on a
  // full-width row reads as the whole list flinching.
  "&:active": { transform: "scale(0.995)" },
  "&:focus-visible": { outline: `2px solid ${tokens.color.primary}`, outlineOffset: 2 },
});

export function PlanCard({ plan, onOpen }: { plan: ProjectSummary; onOpen: (id: string) => void }) {
  const status = deriveStatus(plan);
  const brand = plan.brand?.trim();
  const campaign = plan.campaign_name?.trim();
  const title = campaign || plan.name || "Untitled plan";
  const subline = [brand, plan.therapy_area?.trim(), plan.lifecycle_key ? LIFECYCLE_LABEL[plan.lifecycle_key] : ""]
    .filter(Boolean)
    .join(" · ");
  const initial = (brand || plan.name || "?").charAt(0).toUpperCase();

  return (
    <Root onClick={() => onOpen(plan.id)} aria-label={`Open plan ${title}`}>
      {/* Brand monogram */}
      <Box
        sx={{
          flex: "0 0 auto",
          width: 48,
          height: 48,
          borderRadius: tokens.radius.md,
          display: "grid",
          placeItems: "center",
          background: indigoTint(0.1),
          color: tokens.color.primary,
          fontSize: 22,
          fontWeight: 800,
        }}
      >
        {initial}
      </Box>

      {/* Title + brief */}
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography
          sx={{ fontSize: tokens.fontSize.lg, fontWeight: 700, color: "text.primary", lineHeight: 1.25, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}
        >
          {title}
        </Typography>
        {subline && (
          <Typography sx={{ fontSize: tokens.fontSize.sm, color: "text.secondary", mt: 0.25, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {subline}
          </Typography>
        )}
        {plan.objective?.trim() && (
          <Typography sx={{ fontSize: tokens.fontSize.xs, color: "text.secondary", mt: 0.5, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {plan.objective.trim()}
          </Typography>
        )}
      </Box>

      {/* Status + time */}
      <Box sx={{ flex: "0 0 auto", display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 0.75 }}>
        <Chip
          size="small"
          icon={<span className="material-symbols-outlined" style={{ fontSize: 15, color: status.color }}>{status.icon}</span>}
          label={status.label}
          sx={{ height: 24, fontWeight: 700, fontSize: 12, color: status.color, background: status.bg, border: `1px solid ${status.color}22`, "& .MuiChip-icon": { ml: 0.75 } }}
        />
        <Typography sx={{ fontSize: tokens.fontSize.xs, color: "text.secondary", fontVariantNumeric: "tabular-nums" }}>
          {relativeTime(plan.updated_at)}
        </Typography>
      </Box>

      <span className="material-symbols-outlined" style={{ fontSize: 22, color: tokens.color.outlineStrong, flex: "0 0 auto" }}>
        chevron_right
      </span>
    </Root>
  );
}
