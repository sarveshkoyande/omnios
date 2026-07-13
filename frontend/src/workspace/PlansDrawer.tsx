import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Drawer from "@mui/material/Drawer";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import type { ProjectSummary } from "./types";
import { tokens, shade, insetShadow } from "../theme/tokens";

/**
 * PlansDrawer — the metaphor is literal: MUI's Drawer already reads as a
 * physical drawer, so the theme's raised/inset language does the rest (each
 * plan is a filed card you pull out).
 */
const PlanRow = styled("button")<{ active?: boolean }>(({ theme, active }) => ({
  display: "block",
  width: "100%",
  textAlign: "left",
  border: "none",
  cursor: "pointer",
  font: "inherit",
  padding: theme.spacing(2, 2.5),
  borderRadius: tokens.radius.sm,
  marginBottom: 4,
  background: active ? shade(0.08) : "transparent",
  boxShadow: active ? insetShadow : "none",
  "&:hover": { background: shade(0.05) },
  "&:focus-visible": { outline: `2px solid ${tokens.color.text}`, outlineOffset: -2 },
}));

export function PlansDrawer({
  open,
  onClose,
  projects,
  activeId,
  onOpenProject,
  onNewProject,
}: {
  open: boolean;
  onClose: () => void;
  projects: ProjectSummary[];
  activeId: string | null;
  onOpenProject: (id: string) => void;
  onNewProject: () => void;
}) {
  return (
    <Drawer open={open} onClose={onClose} anchor="left" slotProps={{ paper: { sx: { width: 280 } } }}>
      <Box sx={{ p: 3, display: "flex", flexDirection: "column", height: "100%" }}>
        <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 2 }}>
          <Typography variant="h3" sx={{ fontSize: tokens.fontSize.md }}>Plans</Typography>
          <Button size="small" variant="contained" onClick={onNewProject}>+ New</Button>
        </Box>
        <Box sx={{ flex: 1, overflowY: "auto" }}>
          {projects.length === 0 && (
            <Typography variant="body2" sx={{ color: "text.secondary", fontStyle: "italic", p: 1 }}>
              No plans yet.
            </Typography>
          )}
          {projects.map((p) => (
            <PlanRow key={p.id} active={p.id === activeId} onClick={() => onOpenProject(p.id)}>
              <Typography sx={{ fontWeight: 600, fontSize: tokens.fontSize.sm, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {p.name}
              </Typography>
              <Chip size="small" label={p.phase} sx={{ mt: 0.5, height: 18, fontSize: 10 }} />
            </PlanRow>
          ))}
        </Box>
        <Typography variant="caption" sx={{ color: "text.secondary", pt: 2, borderTop: `1px solid ${shade(0.14)}` }}>
          Each plan is a saved conversation + campaign document.
        </Typography>
      </Box>
    </Drawer>
  );
}
