import { useState } from "react";
import type { ArtifactField, V3Artifact } from "../api";
import { Icon } from "../components/Icon";

/** Phase 4 artifact viewer (C9-C11). The brief is a typed object: Overview summarises it,
 *  Detail shows every field with where it came from and lets you edit one field at a time
 *  (each save is a new version), Data is the raw machine-readable form. When `compareTo` is
 *  set (viewing an older version), fields that differ from it are highlighted. */

type Tab = "overview" | "detail" | "data";

export function ArtifactViewer({ art, readOnly, compareTo, onEdit }: {
  art: V3Artifact;
  readOnly: boolean;
  compareTo: V3Artifact | null;
  onEdit: (fieldId: string, value: string) => Promise<void>;
}) {
  const [tab, setTab] = useState<Tab>("overview");
  const sections = art.artifact.sections;
  const fields = sections.flatMap((s) => s.fields);
  const missing = fields.filter((f) => f.needs_input);
  const compareMap = new Map((compareTo?.artifact.sections ?? []).flatMap((s) => s.fields).map((f) => [f.id, f.value]));
  const changed = (f: ArtifactField) => compareTo !== null && compareMap.get(f.id) !== f.value;
  const snapshot = sections.find((s) => s.id === "snapshot");

  return (
    <div className="v3-av">
      <div className="v3-av-tabs" role="tablist">
        {(["overview", "detail", "data"] as Tab[]).map((t) => (
          <button key={t} type="button" role="tab" aria-selected={tab === t} className={tab === t ? "active" : ""} onClick={() => setTab(t)}>
            {t === "overview" ? "Overview" : t === "detail" ? "Detail" : "Data"}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <div className="v3-av-overview">
          <div className="v3-av-complete">
            <div className="v3-av-bar"><span style={{ width: `${Math.round(((fields.length - missing.length) / Math.max(fields.length, 1)) * 100)}%` }} /></div>
            <span>{fields.length - missing.length} of {fields.length} fields decided</span>
          </div>
          <div className="v3-av-snap">
            {(snapshot?.fields ?? []).map((f) => (
              <div key={f.id} className={`v3-av-snap-card ${f.needs_input ? "missing" : ""} ${changed(f) ? "changed" : ""}`}>
                <span>{f.label}</span>
                <b>{f.value}</b>
              </div>
            ))}
          </div>
          {missing.length > 0 && (
            <div className="v3-av-missing">
              <b>Still needs input</b>
              <p>{missing.map((f) => f.label).join(" · ")}</p>
            </div>
          )}
          <div className="v3-av-sections">
            {sections.filter((s) => s.id !== "snapshot").map((s) => (
              <button key={s.id} type="button" className="v3-av-sec-card" onClick={() => setTab("detail")}>
                <b>{s.title}</b>
                <span>{s.fields.filter((f) => !f.needs_input).length} of {s.fields.length} decided</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {tab === "detail" && (
        <div className="v3-av-detail">
          {sections.map((s) => (
            <section key={s.id} className="v3-av-sec">
              <h3>{s.title}</h3>
              {s.fields.map((f) => <FieldRow key={f.id} f={f} readOnly={readOnly} changed={changed(f)} onEdit={onEdit} />)}
            </section>
          ))}
        </div>
      )}

      {tab === "data" && <pre className="v3-ws-json">{JSON.stringify(art.artifact, null, 2)}</pre>}
    </div>
  );
}

function FieldRow({ f, readOnly, changed, onEdit }: {
  f: ArtifactField; readOnly: boolean; changed: boolean; onEdit: (fieldId: string, value: string) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const start = () => { setDraft(f.needs_input ? "" : f.value); setError(null); setEditing(true); };
  const save = async () => {
    setBusy(true);
    try { await onEdit(f.id, draft); setEditing(false); } catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  };

  return (
    <div className={`v3-av-field ${f.needs_input ? "missing" : ""} ${changed ? "changed" : ""}`}>
      <div className="v3-av-field-head">
        <b>{f.label}</b>
        <em>{f.source}</em>
        {!readOnly && !editing && (
          <button type="button" className="v3-av-edit" onClick={start} aria-label={`Edit ${f.label}`}><Icon name="document" size={12} /> Edit</button>
        )}
      </div>
      {editing ? (
        <div className="v3-av-editor">
          <textarea rows={3} value={draft} autoFocus onChange={(e) => setDraft(e.target.value)} />
          <div className="v3-av-editor-actions">
            <button type="button" className="v3-av-cancel" onClick={() => setEditing(false)} disabled={busy}>Cancel</button>
            <button type="button" className="v3-av-save" onClick={save} disabled={busy}>{busy ? "Saving…" : "Save"}</button>
          </div>
          {error && <p className="v3-ask-error">{error}</p>}
        </div>
      ) : (
        <p className="v3-av-value">{f.value}</p>
      )}
    </div>
  );
}
