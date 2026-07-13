import { useRef, useState } from "react";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Typography from "@mui/material/Typography";
import { ConsolePanel } from "../components/ConsolePanel";
import { tokens } from "../theme/tokens";
import { PlanDocument } from "./PlanDocument";
import type { PlanDocumentHandle } from "./PlanDocument";

export function PlanSummaryCard({
  projectId,
  planHtml,
  planMarkdown,
  planFrozen,
  planEditing,
  sectionsProgress,
  onBeginEdit,
  onCancelEdit,
  onSaveEdit,
  onCloseUpdates,
}: {
  projectId: string;
  planHtml: string;
  planMarkdown: string | null;
  planFrozen: boolean;
  planEditing: boolean;
  sectionsProgress: { done: number; total: number } | null;
  onBeginEdit: () => void;
  onCancelEdit: (doc: PlanDocumentHandle | null) => void;
  onSaveEdit: (html: string, markdown: string) => Promise<void>;
  onCloseUpdates: () => Promise<void>;
}) {
  const [copied, setCopied] = useState(false);
  const [saving, setSaving] = useState(false);
  const docRef = useRef<PlanDocumentHandle>(null);

  const handleSave = async () => {
    const content = docRef.current?.getEditedContent();
    if (!content) return;
    setSaving(true);
    await onSaveEdit(content.html, content.markdown);
    setSaving(false);
  };

  return (
    <ConsolePanel
      title="Brand Engagement Plan"
      action={
        sectionsProgress ? (
          <Typography variant="caption" sx={{ color: "secondary.dark", fontWeight: 700 }}>
            {sectionsProgress.done}/{sectionsProgress.total} sections live
          </Typography>
        ) : (
          <Typography variant="caption" sx={{ color: "success.main", fontWeight: 700 }}>
            Plan ready
          </Typography>
        )
      }
      sx={{ mt: 3 }}
    >
      <Box sx={{ display: "flex", gap: 1.5, flexWrap: "wrap", alignItems: "center", mb: 2 }}>
        {planEditing ? (
          <>
            <Button variant="contained" color="primary" disabled={saving} onClick={handleSave}>
              {saving ? "Saving…" : "Save changes"}
            </Button>
            <Button variant="outlined" disabled={saving} onClick={() => onCancelEdit(docRef.current)}>
              Cancel
            </Button>
            <Typography variant="caption" sx={{ color: "text.secondary" }}>
              Click any text to edit it — headings, paragraphs, list items and simple table cells.
            </Typography>
          </>
        ) : (
          <>
            <Button variant="outlined" href={`/api/projects/${encodeURIComponent(projectId)}/export.docx`}>Word</Button>
            <Button variant="outlined" href={`/api/projects/${encodeURIComponent(projectId)}/export.pdf`}>PDF</Button>
            <Button
              variant="outlined"
              onClick={() => {
                if (planMarkdown) navigator.clipboard.writeText(planMarkdown);
                setCopied(true);
                setTimeout(() => setCopied(false), 1500);
              }}
            >
              {copied ? "Copied ✓" : "Copy"}
            </Button>
            <Button variant="outlined" onClick={onBeginEdit}>Edit plan</Button>
            {planFrozen ? (
              <Typography
                variant="caption"
                sx={{ display: "inline-flex", alignItems: "center", gap: 0.5, color: "text.secondary", ml: "auto" }}
              >
                <span className="material-symbols-outlined" style={{ fontSize: 16 }}>lock</span>
                Updates closed
              </Typography>
            ) : (
              <Button
                variant="text"
                onClick={onCloseUpdates}
                sx={{ ml: "auto", color: tokens.color.danger }}
              >
                Close updates
              </Button>
            )}
          </>
        )}
      </Box>
      <PlanDocument ref={docRef} html={planHtml} editing={planEditing} />
    </ConsolePanel>
  );
}
