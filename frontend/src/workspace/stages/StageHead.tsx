import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import type { StageAgentId } from "../types";
import { tokens } from "../../theme/tokens";
import { stageMark } from "../../theme/stageTheme";

/** `agent` is accepted but no longer rendered here: the stage's agent identity moved to the
 *  chat pane header (Workspace.tsx), directly above that agent's own conversation, so it is
 *  stated once per window instead of twice. The prop stays so callers keep declaring which
 *  agent owns the stage.
 *
 *  The title itself is ink, closed by a hairline rule. Only the icon carries the stage colour
 *  (marker slot 1) — a fully coloured heading made the page read as a different application
 *  rather than a different section of the same one. */
export function StageHead({ icon, title, blurb }: { icon: string; title: string; blurb: string; agent?: StageAgentId }) {
  return (
    <Box sx={{ mb: 4, pb: 2, borderBottom: `1px solid ${tokens.color.outline}` }}>
      <Box sx={{ display: "flex", gap: 1.5, alignItems: "center" }}>
        <span className="material-symbols-outlined" style={{ fontSize: 24, color: stageMark.primary }}>{icon}</span>
        <Typography variant="h2" sx={{ fontSize: tokens.fontSize.lg }}>{title}</Typography>
      </Box>
      <Typography variant="body2" sx={{ color: "text.secondary", mt: 0.75 }}>{blurb}</Typography>
    </Box>
  );
}
