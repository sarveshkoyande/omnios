import { useState } from "react";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Typography from "@mui/material/Typography";
import { ConsolePanel } from "../components/ConsolePanel";
import { InsetTextField } from "../components/InsetTextField";
import { BRIEF_TEMPLATE } from "./types";

/**
 * IntakeCard — a printed fill-in-the-blanks form pad, the one place a plain
 * (non-mono) inset well makes sense: it's meant to be read/edited as prose.
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
    <ConsolePanel title="Start with a quick brief" sx={{ mb: 3 }}>
      <Typography variant="body2" sx={{ color: "text.secondary", mb: 2 }}>
        Fill in the blanks below — or paste your own brief in any wording. I'll read it and pull out
        brand, molecule, indication, lifecycle, audience, budget and the rest, then ask about anything
        important that's missing.
      </Typography>
      <InsetTextField
        multiline
        minRows={9}
        fullWidth
        value={text}
        onChange={(e) => setText(e.target.value)}
        slotProps={{ input: { sx: { fontFamily: "inherit" } } }}
      />
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mt: 2 }}>
        <Button variant="text" onClick={onSkip}>
          Skip — I'll just chat
        </Button>
        <Button variant="contained" color="primary" onClick={() => onSubmit(text.trim())}>
          Extract brief →
        </Button>
      </Box>
    </ConsolePanel>
  );
}
