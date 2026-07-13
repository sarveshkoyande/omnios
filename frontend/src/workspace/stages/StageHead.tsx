import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { tokens } from "../../theme/tokens";

export function StageHead({ icon, title, blurb }: { icon: string; title: string; blurb: string }) {
  return (
    <Box sx={{ display: "flex", gap: 2, alignItems: "flex-start", mb: 4 }}>
      <span className="material-symbols-outlined" style={{ fontSize: 26, color: tokens.color.primary }}>{icon}</span>
      <Box>
        <Typography variant="h2" sx={{ fontSize: tokens.fontSize.lg }}>{title}</Typography>
        <Typography variant="body2" sx={{ color: "text.secondary", mt: 0.5 }}>{blurb}</Typography>
      </Box>
    </Box>
  );
}
