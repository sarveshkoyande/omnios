import { useRef, useState } from "react";
import { keyframes } from "@emotion/react";
import Box from "@mui/material/Box";
import InputBase from "@mui/material/InputBase";
import Typography from "@mui/material/Typography";
import { GlassPanel } from "../glass/primitives";
import { tokens, indigoTint, light, motion, hoverOnly } from "../theme/tokens";

const settleIn = keyframes`
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: none; }
`;

const SUGGESTIONS = [
  "Launch campaign for Nuvexa in cardiology, targeting cardiologists across the US this quarter.",
  "Refresh the campaign plan for a mature oncology brand ahead of a competitor launch.",
  "Build an LOE defense plan for a respiratory brand losing exclusivity next year.",
  "Plan a patient-support omnichannel push for a rare-disease launch.",
];

// Short labels for the example chips — the full text is dropped into the field on click.
const SUGGESTION_CHIPS = [
  { label: "Launch a new brand", text: SUGGESTIONS[0] },
  { label: "Refresh a mature brand", text: SUGGESTIONS[1] },
  { label: "LOE defense plan", text: SUGGESTIONS[2] },
  { label: "Patient-support push", text: SUGGESTIONS[3] },
];

const ACCEPTED_EXT = [".pdf", ".docx", ".txt", ".md"];

function hasAcceptedExtension(name: string) {
  const lower = name.toLowerCase();
  return ACCEPTED_EXT.some((ext) => lower.endsWith(ext));
}

/**
 * HomeIntakeCard — the starting screen's brief intake, styled as a clean
 * AI-agent input window: one white composer surface with the requirement
 * field on top and a single aligned toolbar row underneath (import on the
 * left, send on the right), plus example chips to seed the field. The whole
 * surface is a drag-and-drop target so a brand plan can be dropped straight
 * from Home before a project even exists.
 */
export function HomeIntakeCard({
  value,
  onChange,
  onSubmit,
  onImport,
}: {
  value: string;
  onChange: (text: string) => void;
  onSubmit: () => void;
  onImport: (file: File) => void;
}) {
  const [dragActive, setDragActive] = useState(false);
  const dragDepth = useRef(0);
  const fileRef = useRef<HTMLInputElement>(null);

  const resetDrag = () => {
    dragDepth.current = 0;
    setDragActive(false);
  };

  const hasText = value.trim().length > 0;

  return (
    <GlassPanel
      tier="A"
      sx={{
        // Transparent container, no card chrome — the composer below is the only box, so it
        // sits edge-to-edge with the dashboard stat cards instead of being inset inside a panel.
        p: 0,
        background: "transparent",
        border: "none",
        boxShadow: "none",
        overflow: "visible",
        animation: `${settleIn} ${motion.duration.enter} ${motion.easeOut}`,
      }}
      onDragEnter={(e: React.DragEvent) => {
        e.preventDefault();
        dragDepth.current += 1;
        if (Array.from(e.dataTransfer.items || []).some((it) => it.kind === "file")) setDragActive(true);
      }}
      onDragOver={(e: React.DragEvent) => e.preventDefault()}
      onDragLeave={(e: React.DragEvent) => {
        e.preventDefault();
        dragDepth.current = Math.max(0, dragDepth.current - 1);
        if (dragDepth.current === 0) setDragActive(false);
      }}
      onDrop={(e: React.DragEvent) => {
        e.preventDefault();
        resetDrag();
        const f = Array.from(e.dataTransfer.files || [])[0];
        if (f && hasAcceptedExtension(f.name)) onImport(f);
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center", gap: 1.25, mb: 2.5 }}>
        <span
          className="material-symbols-outlined"
          style={{ fontSize: 22, color: tokens.color.primary, display: "inline-block" }}
        >
          bolt
        </span>
        <Typography sx={{ fontSize: tokens.fontSize.lg, fontWeight: 700, color: "text.primary" }}>
          Start a new requirement
        </Typography>
      </Box>

      {/* Composer surface — the single frosted input box: translucent so the page glow bleeds
          through, brand-tinted border, spanning the full width to line up with the stat cards. */}
      <Box
        sx={{
          borderRadius: tokens.radius.md,
          background: dragActive ? light(0.7) : light(0.82),
          backdropFilter: "blur(10px)",
          border: dragActive ? `1.5px dashed ${tokens.color.primary}` : `1px solid ${indigoTint(0.28)}`,
          boxShadow: dragActive ? `0 8px 28px ${indigoTint(0.22)}` : `0 10px 30px ${indigoTint(0.12)}`,
          transition: "border-color 140ms ease, box-shadow 140ms ease, background 140ms ease",
          "&:focus-within": {
            borderColor: tokens.color.primary,
            boxShadow: `0 0 0 3px ${indigoTint(0.16)}, 0 10px 30px ${indigoTint(0.14)}`,
          },
        }}
      >
        {dragActive ? (
          <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, px: 3, py: 4 }}>
            <span className="material-symbols-outlined" style={{ fontSize: 24, color: tokens.color.primary }}>
              file_download
            </span>
            <Typography sx={{ fontSize: 15, fontWeight: 600, color: "text.primary" }}>
              Drop it here — I'll read it and fill the brief for you.
            </Typography>
          </Box>
        ) : (
          <>
            <InputBase
              multiline
              minRows={2}
              maxRows={6}
              value={value}
              onChange={(e) => onChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); onSubmit(); }
              }}
              placeholder="Describe a requirement, or drag a brand-plan file (.pdf/.docx/.txt/.md) here…"
              sx={{
                display: "block",
                width: "100%",
                color: "text.primary",
                fontSize: tokens.fontSize.md,
                lineHeight: 1.55,
                px: 3,
                pt: 2.5,
                pb: 1,
                "& textarea::placeholder, & input::placeholder": { color: tokens.color.inkSecondary, opacity: 1 },
              }}
            />

            {/* Toolbar — import on the left, send on the right, single baseline. */}
            <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 1.5, px: 2, py: 1.5 }}>
              <Box
                role="button"
                tabIndex={0}
                onClick={() => fileRef.current?.click()}
                onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileRef.current?.click(); } }}
                sx={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 0.75,
                  height: 34,
                  px: 1.5,
                  borderRadius: tokens.radius.pill,
                  cursor: "pointer",
                  color: "text.secondary",
                  fontSize: tokens.fontSize.xs,
                  fontWeight: 700,
                  border: `1px solid ${tokens.color.outline}`,
                  background: tokens.color.surface,
                  transition: [
                    `background ${motion.duration.hover} ${motion.easeOut}`,
                    `color ${motion.duration.hover} ${motion.easeOut}`,
                    `border-color ${motion.duration.hover} ${motion.easeOut}`,
                    `transform ${motion.duration.press} ${motion.easeOut}`,
                  ].join(", "),
                  [hoverOnly]: {
                    "&:hover": { background: tokens.color.canvas, color: "text.primary", borderColor: tokens.color.outlineStrong },
                  },
                  "&:active": { transform: "scale(0.96)" },
                  "&:focus-visible": { outline: `2px solid ${tokens.color.primary}`, outlineOffset: 2 },
                }}
              >
                <span className="material-symbols-outlined" style={{ fontSize: 18 }}>attach_file</span>
                Import file
              </Box>

              <Box
                role="button"
                tabIndex={0}
                aria-label={hasText ? "Start plan" : "New plan"}
                onClick={onSubmit}
                onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSubmit(); } }}
                sx={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 0.75,
                  height: 38,
                  pl: hasText ? 2.25 : 0,
                  pr: hasText ? 1.5 : 0,
                  width: hasText ? "auto" : 38,
                  justifyContent: "center",
                  borderRadius: tokens.radius.pill,
                  cursor: "pointer",
                  color: "#fff",
                  fontSize: tokens.fontSize.sm,
                  fontWeight: 700,
                  background: `linear-gradient(120deg, ${tokens.color.primary}, ${tokens.color.primaryDark})`,
                  boxShadow: `0 4px 14px ${indigoTint(0.32)}`,
                  transition: [
                    `filter ${motion.duration.hover} ${motion.easeOut}`,
                    `transform ${motion.duration.press} ${motion.easeOut}`,
                  ].join(", "),
                  [hoverOnly]: {
                    "&:hover": { filter: "brightness(1.06)" },
                  },
                  // This is the primary action on the dashboard, so it gets the full
                  // press scale rather than the gentler card value.
                  "&:active": { transform: "scale(0.94)" },
                  "&:focus-visible": { outline: `2px solid ${tokens.color.primary}`, outlineOffset: 2 },
                }}
              >
                {hasText && <Box component="span" sx={{ whiteSpace: "nowrap" }}>Start plan</Box>}
                <span className="material-symbols-outlined" style={{ fontSize: 20 }}>arrow_upward</span>
              </Box>

              <input
                ref={fileRef}
                type="file"
                accept=".pdf,.docx,.txt,.md"
                style={{ display: "none" }}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) onImport(f);
                  e.target.value = "";
                }}
              />
            </Box>
          </>
        )}
      </Box>

      {/* Example chips — click to seed the field. */}
      <Box sx={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 1, mt: 2 }}>
        <Typography sx={{ fontSize: tokens.fontSize.xs, fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase", color: "text.secondary", mr: 0.5 }}>
          Try
        </Typography>
        {SUGGESTION_CHIPS.map((s) => (
          <Box
            key={s.label}
            role="button"
            tabIndex={0}
            onClick={() => onChange(s.text)}
            onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onChange(s.text); } }}
            sx={{
              px: 1.5,
              py: 0.5,
              borderRadius: tokens.radius.pill,
              cursor: "pointer",
              fontSize: tokens.fontSize.xs,
              fontWeight: 700,
              color: tokens.color.primary,
              background: tokens.color.infoSoft,
              border: `1px solid ${indigoTint(0.18)}`,
              transition: [
                `background ${motion.duration.hover} ${motion.easeOut}`,
                `border-color ${motion.duration.hover} ${motion.easeOut}`,
                `transform ${motion.duration.press} ${motion.easeOut}`,
              ].join(", "),
              [hoverOnly]: {
                "&:hover": { background: indigoTint(0.12), borderColor: tokens.color.primary },
              },
              "&:active": { transform: "scale(0.95)" },
              "&:focus-visible": { outline: `2px solid ${tokens.color.primary}`, outlineOffset: 2 },
            }}
          >
            {s.label}
          </Box>
        ))}
      </Box>
    </GlassPanel>
  );
}
