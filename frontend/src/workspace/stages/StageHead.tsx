import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import type { StageAgentId } from "../types";
import { tokens } from "../../theme/tokens";
import { accent } from "../../theme/stageTheme";

/** `agent` is accepted but no longer rendered here: the stage's agent identity moved to the
 *  chat pane header (Workspace.tsx), directly above that agent's own conversation, so it is
 *  stated once per window instead of twice. The prop stays so callers keep declaring which
 *  agent owns the stage. */
export function StageHead({ icon, title, blurb }: { icon: string; title: string; blurb: string; agent?: StageAgentId }) {
  return (
    <Box sx={{ display: "flex", gap: 2, alignItems: "flex-start", mb: 4 }}>
      <span className="material-symbols-outlined" style={{ fontSize: 26, color: accent.primary }}>{icon}</span>
      <Box sx={{ flex: 1 }}>
        <Typography variant="h2" sx={{ fontSize: tokens.fontSize.lg }}>{title}</Typography>
        <Typography variant="body2" sx={{ color: "text.secondary", mt: 0.5 }}>{blurb}</Typography>
      </Box>
    </Box>
  );
}
