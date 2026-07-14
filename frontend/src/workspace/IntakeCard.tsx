import { useState } from "react";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { GlassPanel, BrandButton } from "../glass/primitives";
import { tokens } from "../theme/tokens";
import { BRIEF_TEMPLATE } from "./types";

/**
 * IntakeCard — a fill-in-the-blanks brief pad. Its header is a title-case card
 * heading (not a small-caps section label — those are reserved for the right-rail
 * section cards); the field is a Tier-0 white surface, read/edited as prose.
 */
export function IntakeCard({
  onSubmit,
  onSkip,
}: {
  onSubmit: (text: string) => void;
  onSkip: () => void;
}) {
  const [text, setText] = useState(BRIEF_TEMPLATE);
  return (
    <GlassPanel tier="A" sx={{ p: 4, mb: 3 }}>
      <Box sx={{ display: "flex", alignItems: "center", gap: 1.25, mb: 1.5 }}>
        <span className="material-symbols-outlined" style={{ fontSize: 22, color: tokens.color.primary }}>
          edit_note
        </span>
        <Typography sx={{ fontSize: 16, fontWeight: 600, color: "text.primary" }}>
          Start with a quick brief
        </Typography>
      </Box>
      <Typography variant="body2" sx={{ color: "text.secondary", mb: 2, lineHeight: 1.55 }}>
        Fill in the blanks below — or paste your own brief in any wording. I'll read it and pull out
        brand, molecule, indication, lifecycle, audience, budget and the rest, then ask about anything
        important that's missing.
      </Typography>
      <TextField
        multiline
        minRows={9}
        fullWidth
        value={text}
        onChange={(e) => setText(e.target.value)}
        slotProps={{ input: { sx: { fontSize: 14, lineHeight: 1.6 } } }}
      />
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mt: 2 }}>
        <Button variant="text" onClick={onSkip}>
          Skip — I'll just chat
        </Button>
        <BrandButton arrow onClick={() => onSubmit(text.trim())}>
          Extract brief
        </BrandButton>
      </Box>
    </GlassPanel>
  );
}
