import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { ReactFlowProvider, useReactFlow } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import "./flowbuilder.css";

import { Canvas } from "./flowbuilder/canvas/Canvas";
import { Palette } from "./flowbuilder/palette/Palette";
import { Inspector } from "./flowbuilder/panels/Inspector";
import { IOMenu } from "./flowbuilder/io/IOMenu";
import { AgentWorkingOverlay } from "./flowbuilder/AgentWorkingOverlay";
import { exportCanvasImage } from "./flowbuilder/io/image";
import { useWorkflowStore } from "./flowbuilder/store/useWorkflowStore";
import { parseDocument } from "./flowbuilder/schema";
import { tokens, glassFallback, indigoTint } from "../../../theme/tokens";
import { getProject, pushSfmcJourney, regenerateCampaignFlowDocument, saveCampaignFlowDocument } from "../../../api";
import { campaignFlowToDocument } from "./campaignAdapter";
import type { CampaignFlow } from "../../types";

// Replaces the old CampaignFlowCanvas.tsx. Same public contract (projectId + base
// flow); internally it's the general-purpose Section-3 workflow builder (see
// workflow-diagram-reference.md) with a campaign-specific load/save adapter:
// - Load: campaign_plan_layout if it's already a WorkflowDocument (schemaVersion
//   present), else a one-time conversion of the base CampaignFlow (campaignAdapter.ts).
// - Save: the active page's WorkflowDocument, debounced, PATCHed back to
//   campaign-plan-layout as a full overwrite (see api.ts / server.py).

type SfmcFormState = {
  auth_base_uri: string;
  client_id: string;
  client_secret: string;
  account_id: string;
  scope: string;
  entry_data_extension_id: string;
  entry_event_definition_key: string;
  email_asset_id: string;
  sender_profile_id: string;
  delivery_profile_id: string;
  schema_version_id: string;
  contact_key: string;
  contact_key_value: string;
};

function defaultSfmcForm(projectId: string | null): SfmcFormState {
  return {
    auth_base_uri: "",
    client_id: "",
    client_secret: "",
    account_id: "",
    scope: "",
    entry_data_extension_id: "",
    entry_event_definition_key: projectId ? `omni-${projectId}-entry` : "",
    email_asset_id: "",
    sender_profile_id: "",
    delivery_profile_id: "",
    schema_version_id: "",
    contact_key: "ContactKey",
    contact_key_value: "",
  };
}

function Toolbar({
  projectId,
  saving,
  paletteOpen,
  editMode,
  onTogglePalette,
  onEnableEdit,
  onOpenSfmc,
  onRegenerateDiagram,
  regenerating,
}: {
  projectId: string | null;
  saving: boolean;
  paletteOpen: boolean;
  editMode: boolean;
  onTogglePalette: () => void;
  onEnableEdit: () => void;
  onOpenSfmc: () => void;
  onRegenerateDiagram: () => void;
  regenerating: boolean;
}) {
  const undo = useWorkflowStore((s) => s.undo);
  const redo = useWorkflowStore((s) => s.redo);
  const canUndo = useWorkflowStore((s) => s.canUndo());
  const canRedo = useWorkflowStore((s) => s.canRedo());
  const runAutoLayoutCmd = useWorkflowStore((s) => s.runAutoLayoutCmd);
  const rf = useReactFlow();

  const downloadHighRes = useCallback(() => {
    void exportCanvasImage(rf, "png", "campaign-journey.png");
  }, [rf]);

  return (
    <Box
      sx={{
        flex: "none",
        zIndex: 6,
        px: 1.25,
        py: 0.75,
        borderBottom: `1px solid ${indigoTint(0.15)}`,
        background: glassFallback,
        display: "flex",
        flexDirection: "row",
        alignItems: "center",
        flexWrap: "wrap",
        gap: 0.75,
        position: "relative",
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center", gap: 0.75, flexWrap: "wrap", minWidth: 0 }}>
        {projectId && (
          <Box sx={{ fontSize: 11, color: "text.secondary", px: 0.5, minWidth: 46, textAlign: "center" }}>
            {saving ? "Savingâ€¦" : "Saved"}
          </Box>
        )}
        {!editMode ? (
          <Button size="small" variant="outlined" onClick={onEnableEdit}>
            Edit manually
          </Button>
        ) : (
          <>
            <Button size="small" variant="text" onClick={() => void runAutoLayoutCmd()}>Auto-layout</Button>
            <Button size="small" variant="text" onClick={undo} disabled={!canUndo}>Undo</Button>
            <Button size="small" variant="text" onClick={redo} disabled={!canRedo}>Redo</Button>
            <Button size="small" variant="text" onClick={onTogglePalette}>
              {paletteOpen ? "Hide shapes" : "Show shapes"}
            </Button>
          </>
        )}
        <IOMenu projectId={projectId} showFileButtons={editMode} />
      </Box>

      <Box sx={{ flex: 1 }} />

      <Box sx={{ display: "flex", alignItems: "center", gap: 0.75, flexWrap: "wrap" }}>
        {projectId && (
          <Button
            size="small"
            variant="outlined"
            onClick={onRegenerateDiagram}
            disabled={regenerating}
            startIcon={<span className="material-symbols-outlined" style={{ fontSize: 16 }}>autorenew</span>}
          >
            {regenerating ? "Regenerating..." : "Regenerate diagram"}
          </Button>
        )}
        {projectId && (
          <Button
            size="small"
            variant="contained"
            onClick={onOpenSfmc}
            sx={{ borderRadius: tokens.radius.pill }}
          >
            Push to SFMC
          </Button>
        )}
        <Button
          size="small"
          variant="contained"
          onClick={downloadHighRes}
          sx={{ borderRadius: tokens.radius.pill }}
          startIcon={<span className="material-symbols-outlined" style={{ fontSize: 16 }}>download</span>}
        >
          Download High-Res
        </Button>
      </Box>
    </Box>
  );
}

function SfmcExportDialog({
  open,
  projectId,
  onClose,
}: {
  open: boolean;
  projectId: string | null;
  onClose: () => void;
}) {
  const [form, setForm] = useState<SfmcFormState>(() => defaultSfmcForm(projectId));
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setForm(defaultSfmcForm(projectId));
    setMessage(null);
  }, [open, projectId]);

  const submit = async () => {
    if (!projectId) return;
    setLoading(true);
    setMessage(null);
    try {
      const result = await pushSfmcJourney(projectId, {
        ...form,
        account_id: form.account_id || undefined,
        scope: form.scope || undefined,
        entry_data_extension_id: form.entry_data_extension_id || undefined,
        entry_event_definition_key: form.entry_event_definition_key || undefined,
        email_asset_id: form.email_asset_id || undefined,
        sender_profile_id: form.sender_profile_id || undefined,
        delivery_profile_id: form.delivery_profile_id || undefined,
        schema_version_id: form.schema_version_id || undefined,
        contact_key: form.contact_key || undefined,
        contact_key_value: form.contact_key_value || undefined,
      });
      setMessage(`Pushed successfully. Journey id: ${result.journeyId || result.journey?.id || "unknown"}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to push to SFMC.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>SFMC Export and Push</DialogTitle>
      <DialogContent dividers sx={{ background: "rgba(245,246,253,0.35)" }}>
        <Stack spacing={1.25} sx={{ pt: 1 }}>
          <Stack direction={{ xs: "column", md: "row" }} spacing={1.25}>
            <TextField
              size="small"
              label="Auth Base URI"
              placeholder="https://YOUR_SUBDOMAIN.auth.marketingcloudapis.com"
              value={form.auth_base_uri}
              onChange={(e) => setForm((prev) => ({ ...prev, auth_base_uri: e.target.value }))}
              fullWidth
            />
            <TextField
              size="small"
              label="Client ID"
              value={form.client_id}
              onChange={(e) => setForm((prev) => ({ ...prev, client_id: e.target.value }))}
              fullWidth
            />
          </Stack>
          <Stack direction={{ xs: "column", md: "row" }} spacing={1.25}>
            <TextField
              size="small"
              label="Client Secret"
              type="password"
              value={form.client_secret}
              onChange={(e) => setForm((prev) => ({ ...prev, client_secret: e.target.value }))}
              fullWidth
            />
            <TextField
              size="small"
              label="Account ID"
              placeholder="Optional business unit MID"
              value={form.account_id}
              onChange={(e) => setForm((prev) => ({ ...prev, account_id: e.target.value }))}
              fullWidth
            />
          </Stack>
          <Stack direction={{ xs: "column", md: "row" }} spacing={1.25}>
            <TextField
              size="small"
              label="Entry Data Extension ID"
              value={form.entry_data_extension_id}
              onChange={(e) => setForm((prev) => ({ ...prev, entry_data_extension_id: e.target.value }))}
              fullWidth
            />
            <TextField
              size="small"
              label="Entry Event Key"
              value={form.entry_event_definition_key}
              onChange={(e) => setForm((prev) => ({ ...prev, entry_event_definition_key: e.target.value }))}
              fullWidth
            />
          </Stack>
          <Stack direction={{ xs: "column", md: "row" }} spacing={1.25}>
            <TextField
              size="small"
              label="Email Asset ID"
              value={form.email_asset_id}
              onChange={(e) => setForm((prev) => ({ ...prev, email_asset_id: e.target.value }))}
              fullWidth
            />
            <TextField
              size="small"
              label="Sender Profile ID"
              value={form.sender_profile_id}
              onChange={(e) => setForm((prev) => ({ ...prev, sender_profile_id: e.target.value }))}
              fullWidth
            />
            <TextField
              size="small"
              label="Delivery Profile ID"
              value={form.delivery_profile_id}
              onChange={(e) => setForm((prev) => ({ ...prev, delivery_profile_id: e.target.value }))}
              fullWidth
            />
          </Stack>
          <Stack direction={{ xs: "column", md: "row" }} spacing={1.25}>
            <TextField
              size="small"
              label="Schema Version ID"
              value={form.schema_version_id}
              onChange={(e) => setForm((prev) => ({ ...prev, schema_version_id: e.target.value }))}
              fullWidth
            />
            <TextField
              size="small"
              label="Contact Key"
              value={form.contact_key}
              onChange={(e) => setForm((prev) => ({ ...prev, contact_key: e.target.value }))}
              fullWidth
            />
            <TextField
              size="small"
              label="Test Contact Key Value"
              value={form.contact_key_value}
              onChange={(e) => setForm((prev) => ({ ...prev, contact_key_value: e.target.value }))}
              fullWidth
            />
          </Stack>
          {message && (
            <Typography variant="caption" sx={{ color: "text.secondary", overflowWrap: "anywhere" }}>
              {message}
            </Typography>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
        <Button size="small" variant="contained" onClick={submit} disabled={loading || !projectId}>
          {loading ? "Pushing..." : "Push to SFMC"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function BuilderShell({
  projectId,
  flow,
  agentBusy = false,
}: {
  projectId: string | null;
  flow: CampaignFlow;
  agentBusy?: boolean;
}) {
  const [saving, setSaving] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(true);
  const [sfmcOpen, setSfmcOpen] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [regenerationMessage, setRegenerationMessage] = useState<string | null>(null);
  const document = useWorkflowStore((s) => s.document);
  const loadDocument = useWorkflowStore((s) => s.loadDocument);
  const loadedRef = useRef(false);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Seed from the base CampaignFlow synchronously before paint (useLayoutEffect, not
  // useEffect) so there's no empty-canvas flash, then async-fetch and override with a
  // previously-saved WorkflowDocument if one exists for this project.
  useLayoutEffect(() => {
    loadedRef.current = false;
    loadDocument(campaignFlowToDocument(flow));
    if (!projectId) { loadedRef.current = true; return; }
    getProject(projectId).then((proj) => {
      const saved = proj.campaign_plan_layout;
      const result = saved && parseDocument(saved);
      if (result && result.ok) {
        loadDocument(result.document);
      }
      loadedRef.current = true;
    }).catch(() => { loadedRef.current = true; });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  useEffect(() => {
    if (!projectId || !loadedRef.current) return;
    if (saveTimer.current) clearTimeout(saveTimer.current);
    setSaving(true);
    saveTimer.current = setTimeout(() => {
      saveCampaignFlowDocument(projectId, document).catch(() => {}).finally(() => setSaving(false));
    }, 800);
    return () => { if (saveTimer.current) clearTimeout(saveTimer.current); };
  }, [document, projectId]);

  const regenerateDiagram = useCallback(async () => {
    if (!projectId || regenerating) return;
    setRegenerating(true);
    setRegenerationMessage(null);
    try {
      const data = await regenerateCampaignFlowDocument(projectId, document);
      let applied = false;
      if (data.document) {
        const parsed = parseDocument(data.document);
        if (parsed.ok) {
          loadDocument(parsed.document);
          await saveCampaignFlowDocument(projectId, parsed.document);
          applied = true;
        }
      }
      if (!applied && data.flow) {
        // The backend always supplies this complete plan-derived fallback when the AI
        // redraw cannot return a valid WorkflowDocument. Convert it through the same
        // adapter used by the initial Stage 3 generation, then persist the result now.
        const regenerated = campaignFlowToDocument(data.flow);
        loadDocument(regenerated);
        await saveCampaignFlowDocument(projectId, regenerated);
        applied = true;
      }
      if (!applied) {
        throw new Error(data.reply || "No regenerated diagram was returned.");
      }
      setRegenerationMessage(data.source === "deterministic-fallback"
        ? "Diagram rebuilt from the campaign brief and saved plan."
        : "Diagram regenerated from the campaign brief and conversation.");
    } catch (error) {
      setRegenerationMessage(error instanceof Error ? error.message : "Regeneration failed.");
    } finally {
      setRegenerating(false);
    }
  }, [document, loadDocument, projectId, regenerating]);

  return (
    <Box
      className="wf-campaign-shell"
      sx={{
        // Fixed viewport-relative height, not "100%": this component sits inside a
        // normal scrolling page, and percentage heights only resolve reliably against
        // an ancestor chain of *definite* heights â€” one auto-height link anywhere above
        // (very possible for a fixed, in a plain content page) collapses '100%' back to
        // content-size, which silently blows out the Palette's full unclipped item list
        // instead of clipping it to scroll, and leaves React Flow's canvas near-zero
        // width with nodes rendered far outside the visible frame.
        position: "relative",
        display: "flex", flexDirection: "column", height: "72vh", minHeight: 560, maxHeight: 900,
        borderRadius: tokens.radius.md, overflow: "hidden", border: `1px solid ${indigoTint(0.12)}`,
      }}
    >
      {(agentBusy || regenerating) && <AgentWorkingOverlay />}
      <Toolbar
        projectId={projectId}
        saving={saving}
        paletteOpen={paletteOpen}
        editMode={editMode}
        onTogglePalette={() => setPaletteOpen((v) => !v)}
        onEnableEdit={() => setEditMode(true)}
        onOpenSfmc={() => setSfmcOpen(true)}
        onRegenerateDiagram={() => void regenerateDiagram()}
        regenerating={regenerating}
      />
      {regenerationMessage && (
        <Typography variant="caption" sx={{ px: 1.5, py: 0.5, color: "text.secondary", background: "rgba(255,255,255,0.72)" }}>
          {regenerationMessage}
        </Typography>
      )}
      <Box sx={{ display: "flex", flex: 1, minHeight: 0 }}>
        {editMode && (paletteOpen ? <Palette /> : <Box className="wf-palette-collapsed" onClick={() => setPaletteOpen(true)} title="Show shapes" />)}
        <Canvas />
        <Inspector />
      </Box>
      <SfmcExportDialog open={sfmcOpen} projectId={projectId} onClose={() => setSfmcOpen(false)} />
    </Box>
  );
}

export function CampaignFlowBuilder({
  projectId,
  flow,
  agentBusy = false,
}: {
  projectId: string | null;
  flow: CampaignFlow;
  agentBusy?: boolean;
}) {
  return (
    <ReactFlowProvider>
      <BuilderShell projectId={projectId} flow={flow} agentBusy={agentBusy} />
    </ReactFlowProvider>
  );
}
