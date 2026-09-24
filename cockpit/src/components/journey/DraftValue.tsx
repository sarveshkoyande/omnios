import type { ReactNode } from "react";
import type { JourneyDraft } from "../../types";
import { hasValue } from "./journeyUtils";

/** Shared canvas pieces: a readable rendering of any kit value, and the highlighted draft
 *  row. Drafts are kept or undone from the step's agent dock, not per row. */

export interface DraftActions {
  locked: boolean;
  busy: boolean;
}

function humanKey(k: string): string {
  return k.replace(/_/g, " ");
}

export function ValueView({ value }: { value: unknown }): ReactNode {
  if (!hasValue(value)) return <span className="jc-empty">Not set yet</span>;
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return <span>{String(value)}</span>;
  }
  if (Array.isArray(value)) {
    if (value.every((x) => typeof x !== "object" || x === null)) {
      return (
        <span className="jc-chiplist">
          {value.map((x, i) => <span key={i} className="pill pill-outline">{String(x)}</span>)}
        </span>
      );
    }
    return (
      <ul className="jc-list">
        {value.map((x, i) => <li key={i}><ValueView value={x} /></li>)}
      </ul>
    );
  }
  const entries = Object.entries(value as Record<string, unknown>).filter(([, v]) => hasValue(v));
  return (
    <dl className="jc-dl">
      {entries.map(([k, v]) => (
        <div key={k} className="jc-dl-row">
          <dt>{humanKey(k)}</dt>
          <dd><ValueView value={v} /></dd>
        </div>
      ))}
    </dl>
  );
}

/** One pending draft, highlighted as proposed by the agent. */
export function DraftItem({ draft, children }: { draft: JourneyDraft; actions?: DraftActions; children?: ReactNode }) {
  return (
    <div className="jc-draft">
      <div className="jc-draft-body">
        <span className="jc-draft-tag">{draft.mode === "append" ? "Proposed addition" : "Proposed"}</span>
        {children ?? <ValueView value={draft.value} />}
      </div>
    </div>
  );
}

/** A labelled field: the kept value from the kit, then any pending drafts for it. */
export function DraftField({ label, value, drafts, actions, flag, children }: {
  label: string;
  value: unknown;
  drafts: JourneyDraft[];
  actions: DraftActions;
  flag?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="jc-field">
      <div className="jc-field-label">{label}</div>
      <div className="jc-field-value">{children ?? <ValueView value={value} />}</div>
      {flag}
      {drafts.map((d) => <DraftItem key={d.id} draft={d} actions={actions} />)}
    </div>
  );
}
