import { useRef, useState } from "react";
import { useReactFlow } from "@xyflow/react";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import { useWorkflowStore } from "../store/useWorkflowStore";
import { downloadDocumentJSON, readDocumentFile } from "./json";
import { pageToMermaid } from "./mermaid/export";
import { mermaidToPage } from "./mermaid/import";
import { pageToCSV } from "./csv";
import { downloadText } from "./download";
import { exportCanvasImage } from "./image";
import { MermaidModal } from "./MermaidModal";

export function IOMenu({
  projectId,
  showFileButtons = true,
}: {
  projectId?: string | null;
  showFileButtons?: boolean;
}) {
  const document = useWorkflowStore((s) => s.document);
  const getActivePage = useWorkflowStore((s) => s.getActivePage);
  const loadDocument = useWorkflowStore((s) => s.loadDocument);
  const importPageCmd = useWorkflowStore((s) => s.importPageCmd);
  const runAutoLayoutCmd = useWorkflowStore((s) => s.runAutoLayoutCmd);
  const rf = useReactFlow();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [modal, setModal] = useState<{ mode: "export" | "import"; text: string; lossy?: string[] } | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [exportAnchor, setExportAnchor] = useState<HTMLElement | null>(null);
  const [importAnchor, setImportAnchor] = useState<HTMLElement | null>(null);

  const onSaveJSON = () => downloadDocumentJSON(document);

  const onLoadJSONFile = async (file: File) => {
    const result = await readDocumentFile(file);
    if (!result.ok) { setLoadError(result.errors.join("\n")); return; }
    setLoadError(null);
    loadDocument(result.document);
  };

  const onExportMermaid = () => {
    const { text, lossy } = pageToMermaid(getActivePage(), document.direction);
    setModal({ mode: "export", text, lossy });
  };

  const onImportMermaidConfirm = async (text: string) => {
    const { page, direction } = mermaidToPage(text, getActivePage().name);
    importPageCmd(page, direction);
    setModal(null);
    await runAutoLayoutCmd();
  };

  const onExportCSV = () => downloadText(`${document.name}.csv`, pageToCSV(getActivePage()), "text/csv");
  const onExportPNG = () => exportCanvasImage(rf, "png", `${document.name}.png`);
  const onExportSVG = () => exportCanvasImage(rf, "svg", `${document.name}.svg`);

  const sfmcExportHref = projectId ? `/api/projects/${encodeURIComponent(projectId)}/export.sfmc.json` : null;
  const onExportSfmc = () => {
    if (!sfmcExportHref) return;
    const a = window.document.createElement("a");
    a.href = sfmcExportHref;
    a.download = "";
    a.click();
  };

  return (
    <div className="wf-io-menu">
      {showFileButtons && (
        <>
          <button onClick={onSaveJSON} title="Download the native workflow JSON">Save JSON</button>
          <button onClick={() => fileInputRef.current?.click()} title="Load a workflow JSON file">Load JSON</button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".json,application/json"
            style={{ display: "none" }}
            onChange={(e) => { const f = e.target.files?.[0]; if (f) void onLoadJSONFile(f); e.target.value = ""; }}
          />
        </>
      )}
      <button onClick={(e) => setExportAnchor(e.currentTarget)}>Export ▾</button>
      <Menu anchorEl={exportAnchor} open={Boolean(exportAnchor)} onClose={() => setExportAnchor(null)}>
        {sfmcExportHref && (
          <MenuItem onClick={() => { setExportAnchor(null); onExportSfmc(); }}>SFMC</MenuItem>
        )}
        <MenuItem onClick={() => { setExportAnchor(null); onExportMermaid(); }}>Mermaid</MenuItem>
        <MenuItem onClick={() => { setExportAnchor(null); onExportSVG(); }}>SVG</MenuItem>
        <MenuItem onClick={() => { setExportAnchor(null); onExportPNG(); }}>PNG</MenuItem>
        <MenuItem onClick={() => { setExportAnchor(null); onExportCSV(); }}>CSV</MenuItem>
      </Menu>

      <button onClick={(e) => setImportAnchor(e.currentTarget)}>Import ▾</button>
      <Menu anchorEl={importAnchor} open={Boolean(importAnchor)} onClose={() => setImportAnchor(null)}>
        <MenuItem onClick={() => { setImportAnchor(null); setModal({ mode: "import", text: "" }); }}>Mermaid</MenuItem>
      </Menu>

      {loadError && (
        <div className="wf-load-error" onClick={() => setLoadError(null)} title="Click to dismiss">
          Load failed: {loadError}
        </div>
      )}

      {modal && (
        <MermaidModal
          mode={modal.mode}
          text={modal.text}
          lossy={modal.lossy}
          onTextChange={(text) => setModal({ ...modal, text })}
          onClose={() => setModal(null)}
          onConfirm={() => void onImportMermaidConfirm(modal.text)}
        />
      )}
    </div>
  );
}
