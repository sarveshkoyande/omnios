import { useState } from "react";

export interface PickerItem<T> {
  id: string;
  title: string;
  subtitle: string;
  value: T;
}

/** A generic list+detail picker: left column is a searchable one-line list (BrandOverview's
 *  own master-detail pattern, `.hier-master`/`.hier-plan-row`), right column is the selected
 *  item's detail, a "Select" button confirms. Used by FlowPlannerPage for brand / engagement
 *  plan / campaign pickers -- same shell, different item type each time.
 *
 *  `variant="modal"` (the default) is a standalone overlay+card, used wherever else this
 *  component might be reused. `variant="inline"` drops that outer shell and just renders the
 *  master-detail body + actions, so the Flow Planner can embed it directly inside its own
 *  chat card instead of popping a second dialog on top of the first. */
export function PickerModal<T>({ title, items, renderDetail, onSelect, onClose, variant = "modal" }: {
  title: string;
  items: PickerItem<T>[];
  renderDetail: (value: T) => React.ReactNode;
  onSelect: (value: T) => void;
  onClose: () => void;
  variant?: "modal" | "inline";
}) {
  const [query, setQuery] = useState("");
  const [activeId, setActiveId] = useState<string | null>(items[0]?.id ?? null);
  const filtered = items.filter((it) => it.title.toLowerCase().includes(query.toLowerCase()));
  const active = items.find((it) => it.id === activeId) ?? filtered[0] ?? null;

  const body = (
    <>
      <div className="hier-master fp-modal-master">
        <div className="hier-master-list">
          <div className="hier-search">
            <input className="hier-search-input" placeholder="Search…" value={query}
              onChange={(e) => setQuery(e.target.value)} autoFocus />
          </div>
          <div className="hier-plan-list">
            {filtered.map((it) => (
              <button key={it.id} type="button"
                className={`hier-plan-row ${active?.id === it.id ? "active" : ""}`}
                onClick={() => setActiveId(it.id)}>
                <span className="hier-plan-row-name">{it.title}</span>
                <span className="hier-plan-row-sub">{it.subtitle}</span>
              </button>
            ))}
            {filtered.length === 0 && <p className="jc-empty">No matches.</p>}
          </div>
        </div>
        <div className="hier-master-divider" />
        <div className="hier-master-detail">
          {active ? renderDetail(active.value) : <div className="jc-empty">Nothing to show.</div>}
        </div>
      </div>
      <div className="fp-modal-actions">
        <button type="button" className="jc-btn jc-btn-ghost" onClick={onClose}>Cancel</button>
        <button type="button" className="jc-btn jc-btn-keep" disabled={!active}
          onClick={() => active && onSelect(active.value)}>Select</button>
      </div>
    </>
  );

  if (variant === "inline") {
    return <div className="fp-modal-inline">{body}</div>;
  }

  return (
    <div className="fp-modal-overlay" role="dialog" aria-modal="true" aria-label={title} onClick={onClose}>
      <div className="fp-modal" onClick={(e) => e.stopPropagation()}>
        <div className="fp-modal-head">
          <h2>{title}</h2>
          <button type="button" className="fp-modal-close" aria-label="Close" onClick={onClose}>&times;</button>
        </div>
        {body}
      </div>
    </div>
  );
}
