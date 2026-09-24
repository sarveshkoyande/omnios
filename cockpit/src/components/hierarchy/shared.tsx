import { useState, type ReactNode } from "react";

const STATUS: Record<string, { tone: string; label: string }> = {
  active: { tone: "success", label: "Active" },
  closed: { tone: "neutral", label: "Closed" },
  draft: { tone: "neutral", label: "Draft" },
  in_progress: { tone: "info", label: "In progress" },
  confirmed: { tone: "success", label: "Confirmed" },
  built: { tone: "info", label: "Built" },
};

export function StatusPill({ status }: { status: string }) {
  const s = STATUS[status] ?? { tone: "neutral", label: status };
  return <span className={`pill tone-${s.tone}`}>{s.label}</span>;
}

export function periodLabel(start: string | null, end: string | null): string | null {
  const f = (d: string) => new Date(`${d}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
  if (start && end) return `${f(start)} – ${f(end)}`;
  if (start) return `From ${f(start)}`;
  if (end) return `Until ${f(end)}`;
  return null;
}

export function when(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export const FLOW_ORIGIN: Record<string, string> = {
  journey: "From the brand journey",
  campaign_plan: "Campaign Plan diagram",
  manual: "Added here",
  legacy_layout: "Imported diagram",
};

/** A one-field "+ New …" form that opens in place. `extra` renders more fields. */
export function CreateForm({ label, placeholder, busy, error, onSubmit, children, submitLabel = "Create" }: {
  label: string;
  placeholder: string;
  busy: boolean;
  error: string | null;
  onSubmit: (name: string) => void;
  children?: ReactNode;
  submitLabel?: string;
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  if (!open) {
    return <button type="button" className="jc-btn jc-btn-keep" onClick={() => setOpen(true)}>+ {label}</button>;
  }
  return (
    <form className="hier-create" onSubmit={(e) => { e.preventDefault(); if (name.trim()) onSubmit(name.trim()); }}>
      <input className="jc-input" autoFocus placeholder={placeholder} value={name} disabled={busy}
        onChange={(e) => setName(e.target.value)} aria-label={placeholder} />
      {children}
      <div className="hier-create-actions">
        <button type="submit" className="jc-btn jc-btn-keep" disabled={busy || !name.trim()}>{busy ? "Working…" : submitLabel}</button>
        <button type="button" className="jc-btn jc-btn-ghost" disabled={busy} onClick={() => { setOpen(false); setName(""); }}>Cancel</button>
      </div>
      {error && <div className="step-chat-error" role="alert">{error}</div>}
    </form>
  );
}
