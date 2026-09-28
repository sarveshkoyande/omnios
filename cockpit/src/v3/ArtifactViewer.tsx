import { useEffect, useState } from "react";
import type { ArtifactField, GuidelineIssue, V3Artifact } from "../api";
import { Icon } from "../components/Icon";

/** Phase 4 artifact viewer (C9-C11). The brief is a typed object: Overview summarises it,
 *  Detail shows every field with where it came from and lets you edit one field at a time
 *  (each save is a new version), Data is the raw machine-readable form. When `compareTo` is
 *  set (viewing an older version), fields that differ from it are highlighted. */

type Tab = "overview" | "detail" | "data";

export function ArtifactViewer({ art, readOnly, compareTo, onEdit, issues, focusField }: {
  art: V3Artifact;
  readOnly: boolean;
  compareTo: V3Artifact | null;
  onEdit: (fieldId: string, value: string) => Promise<void>;
  /** Check guidelines results (C12), highlighted on their fields. */
  issues?: GuidelineIssue[];
  /** A field to jump to (from a guideline issue): switches to Detail and scrolls to it. */
  focusField?: { id: string; nonce: number } | null;
}) {
  const [tab, setTab] = useState<Tab>("overview");
  const issueMap = new Map<string, GuidelineIssue[]>();
  for (const i of issues ?? []) issueMap.set(i.field_id, [...(issueMap.get(i.field_id) ?? []), i]);

  useEffect(() => {
    if (!focusField) return;
    setTab("detail");
    const t = setTimeout(() => document.getElementById(`v3-field-${focusField.id}`)?.scrollIntoView({ behavior: "smooth", block: "center" }), 60);
    return () => clearTimeout(t);
  }, [focusField]);
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
              {s.fields.map((f) => <FieldRow key={f.id} f={f} readOnly={readOnly} changed={changed(f)} onEdit={onEdit} issues={issueMap.get(f.id)} />)}
            </section>
          ))}
        </div>
      )}

      {tab === "data" && <pre className="v3-ws-json">{JSON.stringify(art.artifact, null, 2)}</pre>}

      {/* Print / PDF export (C14): the whole brief, every section, only visible when printing. */}
      <div className="v3-print">
        <h1>{art.title}</h1>
        <p>{art.brand} · version {art.version} · {new Date(art.version_created_at).toLocaleString()}</p>
        {sections.map((s) => (
          <section key={s.id}>
            <h2>{s.title}</h2>
            <table>
              <tbody>
                {s.fields.map((f) => (
                  <tr key={f.id}><th>{f.label}</th><td>{f.value}</td><td className="src">{f.source}</td></tr>
                ))}
              </tbody>
            </table>
          </section>
        ))}
      </div>
    </div>
  );
}

function FieldRow({ f, readOnly, changed, onEdit, issues }: {
  f: ArtifactField; readOnly: boolean; changed: boolean; onEdit: (fieldId: string, value: string) => Promise<void>;
  issues?: GuidelineIssue[];
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
    <div id={`v3-field-${f.id}`} className={`v3-av-field ${f.needs_input ? "missing" : ""} ${changed ? "changed" : ""} ${issues?.length ? `issue ${issues[0].severity}` : ""}`}>
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
      {issues?.map((i, n) => (
        <div key={n} className={`v3-av-issue ${i.severity}`}>
          <b>{i.severity === "high" ? "High risk" : i.severity === "medium" ? "Check" : "Minor"}: {i.issue}</b>
          {i.suggestion && <span>{i.suggestion}</span>}
        </div>
      ))}
    </div>
  );
}
