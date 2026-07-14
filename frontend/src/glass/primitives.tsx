import type { ReactNode } from "react";
import { useState } from "react";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import type { ButtonProps } from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import type { ChipProps } from "@mui/material/Chip";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import { tokens, glass, glassFallback, indigoTint } from "../theme/tokens";

/* ------------------------------------------------------------------ *
 * GlassPanel — the base surface. tier A (panels) · B (emphasis) · 0
 * (content: inputs, tables, long-form reading). Carries `glass-surface`
 * so the a11y media rules in CssBaseline can collapse it to solid.
 * ------------------------------------------------------------------ */
type Tier = "A" | "B" | "0";

const TIER: Record<Tier, { bg: string; border: string; shadow: string; blur: string }> = {
  A: { bg: glass.panel, border: glass.border, shadow: glass.shadow, blur: glass.blur },
  B: { bg: glass.panelStrong, border: glass.borderTint, shadow: glass.shadowElevated, blur: glass.blur },
  "0": { bg: glass.content, border: `1px solid ${indigoTint(0.14)}`, shadow: "none", blur: glass.blurLight },
};

const GlassBase = styled(Box, { shouldForwardProp: (p) => p !== "tier" })<{ tier?: Tier }>(({ tier = "A" }) => {
  const t = TIER[tier];
  return {
    position: "relative",
    background: glassFallback,
    border: t.border,
    boxShadow: t.shadow,
    borderRadius: tokens.radius.md,
    color: tokens.color.text,
    "@supports ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px)))": {
      background: t.bg,
      backdropFilter: t.blur,
      WebkitBackdropFilter: t.blur,
    },
  };
});

export function GlassPanel({ className, tier = "A", ...rest }: { tier?: Tier } & React.ComponentProps<typeof GlassBase>) {
  return <GlassBase className={`glass-surface ${className ?? ""}`.trim()} tier={tier} {...rest} />;
}

/* ------------------------------------------------------------------ *
 * SectionCard — Tier-A panel with a header row: material-symbol icon +
 * small-caps letter-spaced indigo label + optional collapse chevron and
 * right-aligned action slot. (BRIEF, AGENT TEAM …)
 * ------------------------------------------------------------------ */
const SectionLabel = styled(Typography)({
  fontSize: tokens.fontSize.xs,
  fontWeight: 700,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: tokens.color.primary,
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
    <GlassPanel tier="A" sx={{ p: 4, ...sx }} {...rest}>
      {hasHeader && (
      <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
        {icon && (
          <span className="material-symbols-outlined" style={{ fontSize: 18, color: tokens.color.primary }}>
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
            color: "text.secondary",
            borderRadius: 1,
            "&:focus-visible": { outline: `2px solid ${tokens.color.primary}`, outlineOffset: 2 },
          }}
        >
          <span
            className="material-symbols-outlined"
            style={{ fontSize: 20, transform: open ? "none" : "rotate(180deg)", transition: "transform 160ms ease" }}
          >
            {collapsible ? "keyboard_arrow_up" : ""}
          </span>
        </Box>
      </Box>
      )}
      {open && <Box sx={{ mt: hasHeader ? 2.5 : 0 }}>{children}</Box>}
    </GlassPanel>
  );
}

/* ------------------------------------------------------------------ *
 * DefinitionRow — label (ink) / hairline divider / right value (medium)
 * or em-dash, with an optional right-aligned inkSoft hint.
 * ------------------------------------------------------------------ */
const RowRoot = styled("div")(({ theme }) => ({
  display: "flex",
  alignItems: "baseline",
  justifyContent: "space-between",
  gap: theme.spacing(3),
  padding: theme.spacing(2, 0),
  borderBottom: `1px solid ${indigoTint(0.1)}`,
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
      <Box component="span" sx={{ color: "text.primary" }}>
        {label}
      </Box>
      <Box sx={{ display: "flex", alignItems: "baseline", gap: 1.5, minWidth: 0, textAlign: "right" }}>
        {hint && (
          <Typography component="span" variant="caption" sx={{ color: "text.secondary" }}>
            {hint}
          </Typography>
        )}
        <Box component="span" sx={{ fontWeight: 500, color: empty ? "text.secondary" : "text.primary" }}>
          {empty ? "—" : value}
        </Box>
      </Box>
    </RowRoot>
  );
}

/* ------------------------------------------------------------------ *
 * BrandButton — primary = brand-gradient pill (theme handles the fill);
 * this just standardises the trailing-arrow affordance. Secondary uses
 * MUI <Button variant="text">.
 * ------------------------------------------------------------------ */
export function BrandButton({ arrow, children, sx, ...rest }: { arrow?: boolean } & ButtonProps) {
  return (
    <Button
      variant="contained"
      sx={{ borderRadius: tokens.radius.pill, px: 3, py: 1, gap: 0.75, ...sx }}
      {...rest}
    >
      {children}
      {arrow && (
        <span className="material-symbols-outlined" style={{ fontSize: 18 }}>
          arrow_forward
        </span>
      )}
    </Button>
  );
}

/* ------------------------------------------------------------------ *
 * PillChip — translucent white pill; optional status dot (statusGreen).
 * ------------------------------------------------------------------ */
export function PillChip({ dot, label, sx, ...rest }: { dot?: boolean } & ChipProps) {
  return (
    <Chip
      size="small"
      label={
        dot ? (
          <Box component="span" sx={{ display: "inline-flex", alignItems: "center", gap: 0.75 }}>
            <Box
              component="span"
              sx={{ width: 8, height: 8, borderRadius: "50%", background: tokens.color.success, boxShadow: `0 0 5px ${tokens.color.success}` }}
            />
            {label}
          </Box>
        ) : (
          label
        )
      }
      sx={{ height: 26, px: 0.5, ...sx }}
      {...rest}
    />
  );
}
