/** Step-level draft controls (R6): keep all, undo all, confirm. */
export function DraftBar({ draftCount, status, busy, confirmBlocked, error, onKeepAll, onUndoAll, onConfirm, onReopen }: {
  draftCount: number;
  status: string;
  busy: boolean;
  /** Reason confirm is unavailable (e.g. unresolved Kit flags); null when it can run. */
  confirmBlocked: string | null;
  error: string | null;
  onKeepAll: () => void;
  onUndoAll: () => void;
  onConfirm: () => void;
  onReopen: () => void;
}) {
  const confirmed = status === "confirmed";
  return (
    <div className="draft-bar">
      <span className="draft-bar-count">
        {draftCount > 0 ? `${draftCount} draft${draftCount === 1 ? "" : "s"} to review` : confirmed ? "Confirmed" : "No pending drafts"}
      </span>
      <div className="draft-bar-actions">
        <button type="button" className="jc-btn" disabled={busy || draftCount === 0} onClick={onUndoAll}>Undo all</button>
        <button type="button" className="jc-btn" disabled={busy || draftCount === 0} onClick={onKeepAll}>Keep all</button>
        {confirmed ? (
          <button type="button" className="jc-btn" disabled={busy} onClick={onReopen}>Reopen step</button>
        ) : (
          <button type="button" className="jc-btn jc-btn-keep" disabled={busy || confirmBlocked !== null}
            title={confirmBlocked ?? undefined} onClick={onConfirm}>Confirm step</button>
        )}
      </div>
      {confirmBlocked && !confirmed && <div className="draft-bar-note">{confirmBlocked}</div>}
      {error && <div className="step-chat-error" role="alert">{error}</div>}
    </div>
  );
}
