import type { ReactNode } from "react";
import { useState } from "react";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import type { ButtonProps } from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import type { ChipProps } from "@mui/material/Chip";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import { tokens, glass, glassFallback, motion } from "../theme/tokens";
import { enterRise, enterWith } from "../theme/motionPresets";
import { accent } from "../theme/stageTheme";

type Tier = "A" | "B" | "0";

const TIER: Record<Tier, { bg: string; border: string; shadow: string }> = {
  A: { bg: glass.panel, border: glass.border, shadow: glass.shadow },
  B: { bg: glass.panelStrong, border: glass.borderTint, shadow: "none" },
  "0": { bg: glass.content, border: `1px solid ${tokens.color.outline}`, shadow: "none" },
};

const GlassBase = styled(Box, { shouldForwardProp: (p) => p !== "tier" })<{ tier?: Tier }>(({ tier = "A" }) => {
  const t = TIER[tier];
  return {
    position: "relative",
    backgroundColor: glassFallback,
    backgroundImage: "none",
    border: t.border,
    boxShadow: t.shadow,
    borderRadius: tokens.radius.md,
    color: tokens.color.text,
    overflow: "hidden",
  };
});

export function GlassPanel({ className, tier = "A", ...rest }: { tier?: Tier } & React.ComponentProps<typeof GlassBase>) {
  return <GlassBase className={className ?? ""} tier={tier} {...rest} />;
}

const SectionLabel = styled(Typography)({
  fontSize: tokens.fontSize.xs,
  fontWeight: 700,
  letterSpacing: "0.6px",
  textTransform: "uppercase",
  // Follows the stage accent inside a workspace stage; the fallback is the original blue,
  // so every other screen in the app is unaffected.
  color: accent.onContainer,
  lineHeight: 1.4,
});

export function SectionCard({
  icon,
  label,
  action,
  collapsible = false,
  defaultOpen = true,
  children,
  sx,
  ...rest
}: {
  icon?: string;
  label: string;
  action?: ReactNode;
  collapsible?: boolean;
  defaultOpen?: boolean;
  children: ReactNode;
  sx?: object;
} & Omit<React.ComponentProps<typeof GlassPanel>, "children" | "tier">) {
  const [open, setOpen] = useState(defaultOpen);
  const hasHeader = Boolean(label || icon || action || collapsible);
  return (
    // A panel arriving mid-session (a stage's data landing, a section the run just produced)
    // used to blink into existence and shove everything below it down with no warning. The
    // rise is deliberately small and lives on the SectionCard root only, not on GlassPanel,
    // so bare panels used as static chrome stay still.
    <GlassPanel tier="A" sx={{ p: 0, animation: enterWith(enterRise), ...sx }} {...rest}>
      {hasHeader && (
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, px: 2, py: 1.5, backgroundColor: accent.container, borderBottom: `1px solid ${tokens.color.outline}` }}>
          {icon && (
            <span className="material-symbols-outlined" style={{ fontSize: 18, color: accent.onContainer }}>
              {icon}
            </span>
          )}
          <SectionLabel>{label}</SectionLabel>
          <Box sx={{ flex: 1 }} />
          {action}
          <Box
            role={collapsible ? "button" : undefined}
            aria-expanded={collapsible ? open : undefined}
            aria-label={collapsible ? `${open ? "Collapse" : "Expand"} ${label}` : undefined}
            tabIndex={collapsible ? 0 : undefined}
            onClick={collapsible ? () => setOpen((v) => !v) : undefined}
            onKeyDown={
              collapsible
                ? (e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setOpen((v) => !v);
                    }
                  }
                : undefined
            }
            sx={{
              display: "inline-flex",
              cursor: collapsible ? "pointer" : "default",
              color: tokens.color.onPrimaryContainer,
              borderRadius: 1,
              transition: `transform ${motion.duration.press} ${motion.easeOut}`,
              "&:active": collapsible ? { transform: "scale(0.9)" } : undefined,
              "&:focus-visible": { outline: `2px solid ${tokens.color.primary}`, outlineOffset: 2 },
            }}
          >
            <span
              className="material-symbols-outlined"
              style={{
                fontSize: 20,
                transform: open ? "none" : "rotate(180deg)",
                transition: `transform ${motion.duration.hover} ${motion.easeOut}`,
              }}
            >
              {collapsible ? "keyboard_arrow_up" : ""}
            </span>
          </Box>
        </Box>
      )}
      {/* Collapse via a 0fr/1fr grid row rather than unmounting: it animates height
          without measuring the content, and because it is a transition (not a
          keyframe) a double-click retargets from the current height instead of
          restarting. The inner `minHeight: 0` is what lets the row actually
          collapse -- grid items floor at their content size without it. */}
      <Box
        sx={{
          display: "grid",
          gridTemplateRows: open ? "1fr" : "0fr",
          transition: `grid-template-rows ${motion.duration.panel} ${motion.easeOut}`,
        }}
      >
        {/* Children now stay mounted so the height can animate, so a collapsed
            section must be taken out of the tab order and the a11y tree by hand. */}
        <Box sx={{ minHeight: 0, overflow: "hidden" }} inert={!open} aria-hidden={!open}>
          <Box sx={{ p: 2 }}>{children}</Box>
        </Box>
      </Box>
    </GlassPanel>
  );
}

const RowRoot = styled("div")(({ theme }) => ({
  display: "flex",
  alignItems: "baseline",
  justifyContent: "space-between",
  gap: theme.spacing(3),
  padding: theme.spacing(2, 0),
  borderBottom: `1px solid ${tokens.color.outline}`,
  fontSize: tokens.fontSize.md,
  "&:last-of-type": { borderBottom: "none" },
}));

export function DefinitionRow({
  label,
  value,
  hint,
}: {
  label: ReactNode;
  value?: ReactNode;
  hint?: string;
}) {
  const empty = value === undefined || value === null || value === "";
  return (
    <RowRoot>
      {/* The label keeps its natural width (it is short and fixed); the value column takes
          whatever is left and wraps inside it -- otherwise a long value squeezed the label
          into a two-line stack while still not fitting itself. */}
      <Box component="span" sx={{ color: "text.primary", flex: "0 0 auto" }}>
        {label}
      </Box>
      <Box sx={{ display: "flex", alignItems: "baseline", gap: 1.5, flex: "1 1 auto", minWidth: 0, textAlign: "right", justifyContent: "flex-end" }}>
        {hint && (
          <Typography component="span" variant="caption" sx={{ color: "text.secondary" }}>
            {hint}
          </Typography>
        )}
        <Box component="span" sx={{ fontWeight: 700, minWidth: 0, overflowWrap: "anywhere", color: empty ? "text.secondary" : "text.primary" }}>
          {empty ? "N/A" : value}
        </Box>
      </Box>
    </RowRoot>
  );
}

export function BrandButton({ arrow, children, sx, ...rest }: { arrow?: boolean } & ButtonProps) {
  return (
    <Button variant="contained" sx={{ borderRadius: tokens.radius.sm, px: 3, py: 1, gap: 0.75, ...sx }} {...rest}>
      {children}
      {arrow && (
        <span className="material-symbols-outlined" style={{ fontSize: 18 }}>
          arrow_forward
        </span>
      )}
    </Button>
  );
}

export function PillChip({ dot, label, sx, ...rest }: { dot?: boolean } & ChipProps) {
  return (
    <Chip
      size="small"
      label={
        dot ? (
          <Box component="span" sx={{ display: "inline-flex", alignItems: "center", gap: 0.75 }}>
            <Box
              component="span"
              sx={{ width: 8, height: 8, borderRadius: "50%", background: tokens.color.success }}
            />
            {label}
          </Box>
        ) : (
          label
        )
      }
      sx={{
        height: 26,
        px: 0.5,
        backgroundColor: tokens.color.surface,
        border: `1px solid ${tokens.color.outline}`,
        boxShadow: "none",
        ...sx,
      }}
      {...rest}
    />
  );
}
