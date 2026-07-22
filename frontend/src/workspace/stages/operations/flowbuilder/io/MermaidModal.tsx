export function MermaidModal({
  mode,
  text,
  lossy,
  onTextChange,
  onClose,
  onConfirm,
}: {
  mode: "export" | "import";
  text: string;
  lossy?: string[];
  onTextChange?: (text: string) => void;
  onClose: () => void;
  onConfirm?: () => void;
}) {
  return (
    <div className="wf-modal-backdrop" onClick={onClose}>
      <div className="wf-modal" onClick={(e) => e.stopPropagation()}>
        <div className="wf-modal-header">
          <span>{mode === "export" ? "Export to Mermaid" : "Import from Mermaid"}</span>
          <button className="wf-field-delete" onClick={onClose}>×</button>
        </div>
        <textarea
          className="wf-modal-textarea"
          value={text}
          readOnly={mode === "export"}
          onChange={(e) => onTextChange?.(e.target.value)}
          placeholder={mode === "import" ? "Paste Mermaid flowchart text here…" : undefined}
        />
        {lossy && lossy.length > 0 && (
          <div className="wf-modal-lossy">
            <div className="wf-palette-heading">Lossy on export</div>
            <ul>{lossy.map((l, i) => <li key={i}>{l}</li>)}</ul>
          </div>
        )}
        <div className="wf-modal-actions">
          {mode === "export" ? (
            <button onClick={() => navigator.clipboard.writeText(text)}>Copy to clipboard</button>
          ) : (
            <button onClick={onConfirm}>Import (replaces current page + auto-layout)</button>
          )}
          <button onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
