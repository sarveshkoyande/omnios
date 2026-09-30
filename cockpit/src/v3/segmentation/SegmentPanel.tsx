import { useState } from "react";
import { Icon } from "../../components/Icon";
import type { CountStatus, CreatedSegment, Dataset, Pending } from "./api";

const fmt = (n: number) => n.toLocaleString();

export function downloadText(name: string, text: string, type = "text/plain") {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

const fileName = (name: string) => (name.replace(/[^A-Za-z0-9]+/g, "-").replace(/^-|-$/g, "").toLowerCase() || "segment");

function SqlBlock({ sql, name }: { sql: string; name: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard?.writeText(sql).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500); }, () => undefined);
  };
  return (
    <div className="v3-seg-sqlblock">
      <div className="v3-cc-mermaid-bar">
        <button type="button" onClick={copy}>{copied ? "Copied" : "Copy SQL"}</button>
        <button type="button" onClick={() => downloadText(`${fileName(name)}.sql`, sql + "\n", "application/sql")}>Download .sql</button>
      </div>
      <pre className="v3-cc-code v3-seg-code big"><code>{sql}</code></pre>
    </div>
  );
}

function sizeText(count: number | null, status: CountStatus | null): string {
  if (status === "ok" || status === "zero") return `${fmt(count ?? 0)} records`;
  if (status === "unavailable") return "Not sized (Data Cloud isn't connected)";
  if (status === "unknown") return "Couldn't be estimated";
  return "Sized after you name it";
}

/** The segment being defined: what it selects, the SQL Data Cloud will run, and its size. */
export function PendingSegment({ p, engine }: { p: Pending; engine: string }) {
  const name = p.name || p.segmentName;
  return (
    <div className="v3-cc-bp">
      <header className="v3-cc-bp-head">
        <div><span className="v3-cc-eyebrow">Segment definition</span><h1>{name}</h1></div>
        <span className={`v3-cc-chip ${p.count_status === "ok" ? "ok" : ""}`}>{p.count_status ? "Sized · awaiting confirmation" : p.name ? "Named" : "Draft"}</span>
      </header>
      <p className="v3-cc-bp-meta">
        {p.source === "rules" ? "Built by rules" : engine} · values from {p.profile_source === "data_cloud" ? "the live Data Cloud dataset" : "the dataset snapshot"}
        {p.name && p.name !== p.segmentName ? ` · suggested name "${p.segmentName}"` : ""}
      </p>
      {p.note && <p className="v3-cc-banner warn">{p.note}</p>}
      <section className="v3-cc-bp-sec">
        <div className="v3-cc-bp-sec-head"><span><Icon name="target" size={14} /></span><b>Audience</b></div>
        {p.segmentDescription && <p>{p.segmentDescription}</p>}
        <div className="v3-cc-facts">
          <span><b>Size</b>{sizeText(p.count, p.count_status)}</span>
          <span><b>Segment type</b>Data Cloud DBT (SQL)</span>
        </div>
        {p.count_note && (p.count_status === "unknown" || p.count_status === "zero") && <p className="v3-seg-note">{p.count_note}</p>}
      </section>
      <section className="v3-cc-bp-sec">
        <div className="v3-cc-bp-sec-head"><span><Icon name="document" size={14} /></span><b>Data Cloud SQL</b></div>
        {p.explanation && <p>{p.explanation}</p>}
        <SqlBlock sql={p.sql} name={name} />
        {p.healed.length > 0 && <><h4>Fixed by the Tester Agent</h4><ul className="v3-cc-bp-list">{p.healed.map((h, i) => <li key={i}>{h}</li>)}</ul></>}
        {p.problems.length > 0 && <><h4 className="warn">Still to fix</h4><ul className="v3-cc-bp-list warn">{p.problems.map((h, i) => <li key={i}>{h}</li>)}</ul></>}
        {(p.warnings ?? []).length > 0 && <><h4 className="warn">Values the dataset doesn't have</h4><ul className="v3-cc-bp-list warn">{(p.warnings ?? []).map((h, i) => <li key={i}>{h}</li>)}</ul></>}
      </section>
    </div>
  );
}

export function CreatedSegmentCard({ seg, open, onToggle }: { seg: CreatedSegment; open: boolean; onToggle: () => void }) {
  return (
    <section className="v3-cc-bp-sec v3-seg-created">
      <div className="v3-cc-bp-sec-head">
        <span><Icon name="check" size={14} /></span><b>{seg.segmentName}</b>
        <em className={`v3-cc-badge ${seg.published ? "" : "warn"}`}>{seg.published ? "Published" : "Not published"}</em>
      </div>
      {seg.segmentDescription && <p>{seg.segmentDescription}</p>}
      <div className="v3-cc-facts">
        <span><b>Segment ID</b><code>{seg.segmentId}</code></span>
        <span><b>Developer name</b><code>{seg.developerName}</code></span>
        {seg.count !== null && <span><b>Records when created</b>{fmt(seg.count)}</span>}
        <span><b>Created</b>{new Date(seg.created_at).toLocaleString()}</span>
      </div>
      {seg.publishError && <p className="v3-seg-note">Publish: {seg.publishError}</p>}
      <div className="v3-cc-card-actions left">
        {seg.segmentUrl && (
          <a className="v3-cc-btn" href={seg.segmentUrl} target="_blank" rel="noopener noreferrer"><Icon name="link" size={13} /> View Segment in Salesforce</a>
        )}
        <button type="button" className="v3-cc-btn" onClick={onToggle}>{open ? "Hide SQL" : "Show SQL"}</button>
      </div>
      {open && <SqlBlock sql={seg.sql} name={seg.segmentName} />}
    </section>
  );
}

export function CreatedList({ segments }: { segments: CreatedSegment[] }) {
  const [openId, setOpenId] = useState<string | null>(null);
  if (!segments.length) {
    return <div className="v3-ws-empty"><b>No segments created yet</b><p>Segments you create in Data Cloud from this workspace are listed here.</p></div>;
  }
  return (
    <div className="v3-cc-bp">
      {segments.map((s) => (
        <CreatedSegmentCard key={s.segmentId} seg={s} open={openId === s.segmentId} onToggle={() => setOpenId((o) => (o === s.segmentId ? null : s.segmentId))} />
      ))}
    </div>
  );
}

/** What can be segmented on: the data model object's columns with their real values. */
export function DatasetView({ dataset, busy, canRefresh, onRefresh, onPick }: {
  dataset: Dataset | null; busy: boolean; canRefresh: boolean; onRefresh: () => void; onPick: (text: string) => void;
}) {
  if (!dataset) return <p className="v3-muted">{busy ? "Reading the dataset…" : "The dataset couldn't be loaded."}</p>;
  const texts = dataset.columns.filter((c) => c.kind === "text");
  const ranged = dataset.columns.filter((c) => c.kind === "number" || c.kind === "date");
  return (
    <div className="v3-cc-bp">
      <header className="v3-cc-bp-head">
        <div><span className="v3-cc-eyebrow">Data model object</span><h1 className="v3-seg-dmo">{dataset.dmo}</h1></div>
        <button type="button" className="v3-cc-btn" disabled={busy || !canRefresh} title={canRefresh ? undefined : "Data Cloud isn't connected on this server"} onClick={onRefresh}>
          {busy ? <><span className="v3-cc-spinner small" /> Reading…</> : <><Icon name="refresh" size={13} /> Refresh from Data Cloud</>}
        </button>
      </header>
      <p className="v3-cc-bp-meta">
        {dataset.row_count !== null ? `${fmt(dataset.row_count)} HCPs · ` : ""}
        {dataset.source === "data_cloud" ? "values read live from Data Cloud" : "values from the saved snapshot"}
        {dataset.profiled_at ? ` · ${new Date(dataset.profiled_at).toLocaleString()}` : ""}. Click a value to add it to your request.
      </p>
      <section className="v3-cc-bp-sec">
        <div className="v3-cc-bp-sec-head"><span><Icon name="layers" size={14} /></span><b>Categories</b></div>
        {texts.map((c) => (
          <div key={c.name} className="v3-seg-col">
            <div className="v3-seg-col-name"><code>{c.name}</code><span>{c.description}</span></div>
            <div className="v3-seg-chips">
              {(c.values ?? []).map((v) => <button key={v} type="button" className="v3-seg-chip small" onClick={() => onPick(v)}>{v}</button>)}
              {!c.values && <span className="v3-muted">Too many values to list</span>}
            </div>
          </div>
        ))}
      </section>
      <section className="v3-cc-bp-sec">
        <div className="v3-cc-bp-sec-head"><span><Icon name="barChart" size={14} /></span><b>Numbers and dates</b></div>
        <table className="v3-cc-table">
          <thead><tr><th>Field</th><th>Meaning</th><th>Range</th></tr></thead>
          <tbody>
            {ranged.map((c) => (
              <tr key={c.name}><th><code>{c.name}</code></th><td>{c.description}</td><td>{c.range ? `${c.range[0]} – ${c.range[1]}` : "—"}</td></tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
