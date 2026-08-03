import { useEffect, useMemo, useState } from "react";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Checkbox from "@mui/material/Checkbox";
import Chip from "@mui/material/Chip";
import Drawer from "@mui/material/Drawer";
import IconButton from "@mui/material/IconButton";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import type { ProjectSummary } from "./types";
import { tokens, indigoTint, motion, hoverOnly } from "../theme/tokens";

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
  background: active ? indigoTint(0.1) : "transparent",
  transition: [
    `background ${motion.duration.hover} ${motion.easeOut}`,
    `transform ${motion.duration.press} ${motion.easeOut}`,
  ].join(", "),
  [hoverOnly]: { "&:hover": { background: indigoTint(0.06) } },
  "&:active": { transform: "scale(0.98)" },
  "&:focus-visible": { outline: `2px solid ${tokens.color.primary}`, outlineOffset: -2 },
}));

export function PlansDrawer({
  open,
  onClose,
  projects,
  activeId,
  onOpenProject,
  onNewProject,
  onDeleteProject,
}: {
  open: boolean;
  onClose: () => void;
  projects: ProjectSummary[];
  activeId: string | null;
  onOpenProject: (id: string) => void;
  onNewProject: () => void;
  onDeleteProject: (id: string) => void | Promise<void>;
}) {
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [bulkConfirm, setBulkConfirm] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());
  const projectIds = useMemo(() => projects.map((p) => p.id), [projects]);
  const selectedCount = selectedIds.size;
  const allSelected = projectIds.length > 0 && projectIds.every((id) => selectedIds.has(id));
  const partiallySelected = selectedCount > 0 && !allSelected;

  useEffect(() => {
    setSelectedIds((prev) => {
      const valid = new Set(projectIds);
      const next = new Set([...prev].filter((id) => valid.has(id)));
      return next.size === prev.size ? prev : next;
    });
  }, [projectIds]);

  useEffect(() => {
    if (!open) {
      setConfirmId(null);
      setBulkConfirm(false);
    }
  }, [open]);

  const toggleSelected = (id: string) => {
    setBulkConfirm(false);
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    setBulkConfirm(false);
    setSelectedIds(allSelected ? new Set() : new Set(projectIds));
  };

  const deleteSelected = async () => {
    const ids = [...selectedIds];
    setBulkConfirm(false);
    setSelectedIds(new Set());
    await Promise.all(ids.map((id) => onDeleteProject(id)));
  };

  return (
    <Drawer open={open} onClose={onClose} anchor="left" slotProps={{ paper: { sx: { width: 420 } } }}>
      <Box sx={{ p: 3, display: "flex", flexDirection: "column", height: "100%" }}>
        <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 2 }}>
          <Typography variant="h3" sx={{ fontSize: tokens.fontSize.md }}>Plans</Typography>
          <Button size="small" variant="contained" onClick={onNewProject}>+ New</Button>
        </Box>
        {projects.length > 0 && (
          <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}>
            <Checkbox
              size="small"
              checked={allSelected}
              indeterminate={partiallySelected}
              onChange={toggleSelectAll}
              slotProps={{ input: { "aria-label": "Select all plans" } }}
              sx={{ p: 0.5 }}
            />
            <Typography sx={{ flex: 1, fontSize: tokens.fontSize.sm, fontWeight: 600 }}>Select all</Typography>
            {selectedCount > 0 && (
              bulkConfirm ? (
                <Box sx={{ display: "flex", gap: 0.5 }}>
                  <Button size="small" color="error" variant="contained" onClick={deleteSelected} sx={{ minWidth: 0, px: 1, fontSize: 10 }}>
                    Delete
                  </Button>
                  <Button size="small" variant="outlined" onClick={() => setBulkConfirm(false)} sx={{ minWidth: 0, px: 1, fontSize: 10 }}>
                    Cancel
                  </Button>
                </Box>
              ) : (
                <Button size="small" color="error" variant="outlined" onClick={() => setBulkConfirm(true)} sx={{ minWidth: 0, px: 1, fontSize: 10 }}>
                  Delete {selectedCount}
                </Button>
              )
            )}
          </Box>
        )}
        <Box sx={{ flex: 1, overflowY: "auto" }}>
          {projects.length === 0 && (
            <Typography variant="body2" sx={{ color: "text.secondary", fontStyle: "italic", p: 1 }}>
              No plans yet.
            </Typography>
          )}
          {projects.map((p) => (
            <Box key={p.id} sx={{ position: "relative" }}>
              <Box sx={{ display: "flex", alignItems: "flex-start" }}>
                <Checkbox
                  size="small"
                  checked={selectedIds.has(p.id)}
                  onChange={() => toggleSelected(p.id)}
                  slotProps={{ input: { "aria-label": `Select ${p.name}` } }}
                  sx={{ mt: 1.25, mr: 0.5, p: 0.5 }}
                />
                <PlanRow active={p.id === activeId} onClick={() => onOpenProject(p.id)} style={{ paddingRight: 40 }}>
                  <Typography sx={{ fontWeight: 600, fontSize: tokens.fontSize.sm, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {p.name}
                  </Typography>
                  <Chip size="small" label={p.phase} sx={{ mt: 0.5, height: 18, fontSize: 10 }} />
                </PlanRow>
              </Box>
              {confirmId === p.id ? (
                <Box sx={{ position: "absolute", top: 6, right: 6, display: "flex", gap: 0.5 }}>
                  <Button
                    size="small"
                    color="error"
                    variant="contained"
                    onClick={(e) => { e.stopPropagation(); setConfirmId(null); onDeleteProject(p.id); }}
                    sx={{ minWidth: 0, px: 1, fontSize: 10 }}
                  >
                    Delete
                  </Button>
                  <Button
                    size="small"
                    variant="outlined"
                    onClick={(e) => { e.stopPropagation(); setConfirmId(null); }}
                    sx={{ minWidth: 0, px: 1, fontSize: 10 }}
                  >
                    Cancel
                  </Button>
                </Box>
              ) : (
                <IconButton
                  size="small"
                  aria-label="Delete plan"
                  onClick={(e) => { e.stopPropagation(); setConfirmId(p.id); }}
                  sx={{ position: "absolute", top: 6, right: 6 }}
                >
                  <span className="material-symbols-outlined" style={{ fontSize: 16 }}>delete</span>
                </IconButton>
              )}
            </Box>
          ))}
        </Box>
        <Typography variant="caption" sx={{ color: "text.secondary", pt: 2, borderTop: `1px solid ${indigoTint(0.12)}` }}>
          Each plan is a saved conversation + campaign document.
        </Typography>
      </Box>
    </Drawer>
  );
}
