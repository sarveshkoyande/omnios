import { useRef, useState } from "react";
import { keyframes } from "@emotion/react";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { GlassPanel, BrandButton } from "../glass/primitives";
import { tokens, indigoTint, motion, hoverOnly } from "../theme/tokens";
import { BRIEF_TEMPLATE } from "./types";

const settleIn = keyframes`
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: none; }
`;

const ACCEPTED_EXT = [".pdf", ".docx", ".txt", ".md"];

function hasAcceptedExtension(name: string) {
  const lower = name.toLowerCase();
  return ACCEPTED_EXT.some((ext) => lower.endsWith(ext));
}

/**
 * IntakeCard — a fill-in-the-blanks brief pad. Its header is a title-case card
 * heading (not a small-caps section label — those are reserved for the right-rail
 * section cards); the field is a Tier-0 white surface, read/edited as prose.
 *
 * The import dropzone is a real drag-and-drop target (not just click-to-browse):
 * dragging a file over it lifts and highlights the zone, dropping it hands straight
 * to `onImport` the same as picking one from the file dialog.
 */
export function IntakeCard({
  onSubmit,
  onSkip,
  onImport,
}: {
  onSubmit: (text: string) => void;
  onSkip: () => void;
  onImport: (file: File) => void;
}) {
  const [text, setText] = useState(BRIEF_TEMPLATE);
  const [dragActive, setDragActive] = useState(false);
  const dragDepth = useRef(0);
  const fileRef = useRef<HTMLInputElement>(null);

  const resetDrag = () => {
    dragDepth.current = 0;
    setDragActive(false);
  };

  return (
    <GlassPanel tier="A" sx={{ p: 4, mb: 3, minWidth: 0, animation: `${settleIn} ${motion.duration.enter} ${motion.easeOut}` }}>
      <Box sx={{ display: "flex", alignItems: "center", gap: 1.25, mb: 1.5 }}>
        <span
          className="material-symbols-outlined"
          style={{ fontSize: 22, color: tokens.color.primary }}
        >
          edit_note
        </span>
        <Typography sx={{ fontSize: tokens.fontSize.lg, fontWeight: 700, color: "text.primary" }}>
          Start with a quick brief
        </Typography>
      </Box>
      <Typography variant="body2" sx={{ color: "text.secondary", mb: 2, lineHeight: 1.55 }}>
        Fill in the blanks below, or paste your own brief in any wording. I'll read it and pull out
        brand, molecule, indication, lifecycle, audience, budget and the rest, then ask about anything
        important that's missing.
      </Typography>

      {/* Import a brand plan — click to browse, or drag a file straight onto the zone. */}
      <Box
        role="button"
        tabIndex={0}
        onClick={() => fileRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            fileRef.current?.click();
          }
        }}
        onDragEnter={(e) => {
          e.preventDefault();
          dragDepth.current += 1;
          if (Array.from(e.dataTransfer.items || []).some((it) => it.kind === "file")) setDragActive(true);
        }}
        onDragOver={(e) => e.preventDefault()}
        onDragLeave={(e) => {
          e.preventDefault();
          dragDepth.current = Math.max(0, dragDepth.current - 1);
          if (dragDepth.current === 0) setDragActive(false);
        }}
        onDrop={(e) => {
          e.preventDefault();
          resetDrag();
          const f = Array.from(e.dataTransfer.files || [])[0];
          if (f && hasAcceptedExtension(f.name)) onImport(f);
        }}
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 1.5,
          mb: 2.5,
          p: 2,
          cursor: "pointer",
          borderRadius: `${tokens.radius.md}px`,
          border: `1.5px dashed ${dragActive ? tokens.color.primary : indigoTint(0.35)}`,
          background: dragActive ? indigoTint(0.14) : indigoTint(0.04),
          transform: dragActive ? "scale(1.012)" : "none",
          boxShadow: dragActive ? `0 6px 20px ${indigoTint(0.28)}` : "none",
          transition: [
            `background ${motion.duration.hover} ${motion.easeOut}`,
            `border-color ${motion.duration.hover} ${motion.easeOut}`,
            `box-shadow ${motion.duration.hover} ${motion.easeOut}`,
            `transform ${motion.duration.press} ${motion.easeOut}`,
          ].join(", "),
          [hoverOnly]: {
            "&:hover": { background: indigoTint(0.08), borderColor: tokens.color.primary },
          },
          // Not applied while a file is being dragged over -- the drop zone is already
          // scaled up in that state and the two transforms would fight.
          "&:active": dragActive ? undefined : { transform: "scale(0.99)" },
          "&:focus-visible": { outline: `2px solid ${tokens.color.primary}`, outlineOffset: 2 },
        }}
      >
        <span
          className="material-symbols-outlined"
          style={{ fontSize: 24, color: tokens.color.primary, flex: "0 0 auto" }}
        >
          {dragActive ? "file_download" : "upload_file"}
        </span>
        <Box sx={{ minWidth: 0 }}>
          <Typography sx={{ fontSize: 15, fontWeight: 600, color: "text.primary" }}>
            {dragActive ? "Drop it here" : "Import a brand plan"}
          </Typography>
          <Typography variant="caption" sx={{ color: "text.secondary", display: "block", lineHeight: 1.45 }}>
            {dragActive
              ? "Release to read it and fill the brief for you."
              : "Drag a PDF, Word or text file here, or click to browse (.pdf/.docx/.txt/.md)."}
          </Typography>
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

      <Typography variant="overline" sx={{ display: "block", mb: 1.5, color: "text.secondary" }}>
        or fill it in yourself
      </Typography>
      <TextField
        multiline
        minRows={9}
        fullWidth
        value={text}
        onChange={(e) => setText(e.target.value)}
        slotProps={{ input: { sx: { fontSize: 15, lineHeight: 1.6 } } }}
      />
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mt: 2 }}>
        <Button variant="text" onClick={onSkip}>
          Skip, I'll just chat
        </Button>
        <BrandButton arrow onClick={() => onSubmit(text.trim())}>
          Extract brief
        </BrandButton>
      </Box>
    </GlassPanel>
  );
}
