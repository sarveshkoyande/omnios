import type { BrandKit, GuardrailEntry, JourneyDraft } from "../../types";
import { DraftField, DraftItem, type DraftActions } from "./DraftValue";
import { draftsFor, isUnbranded, type KitFlag } from "./journeyUtils";

function GuardrailView({ g }: { g: { dos?: GuardrailEntry[]; donts?: GuardrailEntry[] } | undefined }) {
  const list = (items: GuardrailEntry[] | undefined) =>
    items && items.length > 0
      ? <ul className="guardrail-list">{items.map((e, i) => <li key={i}>{e.category && <span className="guardrail-category">{e.category}: </span>}{e.text}</li>)}</ul>
      : <span className="jc-empty">None yet</span>;
  return (
    <div className="two-col">
      <div className="info-block"><div className="info-label-do">Do</div>{list(g?.dos)}</div>
      <div className="info-block"><div className="info-label-dont">Don't</div>{list(g?.donts)}</div>
    </div>
  );
}

/** Kit (R15): dos and don'ts, approved indication, safety reference, with flags. */
export function KitCanvas({ kit, drafts, actions, flags, dismissed, onDismiss }: {
  kit: BrandKit | null;
  drafts: JourneyDraft[];
  actions: DraftActions;
  flags: KitFlag[];
  dismissed: Set<string>;
  onDismiss: (key: string) => void;
}) {
  const flagFor = (prefix: string) => flags
    .filter((f) => f.key.startsWith(prefix) && !dismissed.has(f.key))
    .map((f) => (
      <div key={f.key} className="jc-flag jc-flag-row">
        <span>{f.label}. Supply it in the chat, or dismiss.</span>
        {!actions.locked && <button type="button" className="jc-btn" onClick={() => onDismiss(f.key)}>Dismiss</button>}
      </div>
    ));

  return (
    <div className="jc-card">
      {actions.locked && <div className="jc-locked">Kit is confirmed and locked.</div>}
      <div className="jc-field">
        <div className="jc-field-label">Dos and don'ts</div>
        <GuardrailView g={kit?.guardrails} />
        {flagFor("guardrails")}
        {draftsFor(drafts, "guardrails").map((d) => (
          <DraftItem key={d.id} draft={d} actions={actions}>
            <GuardrailView g={d.value as { dos?: GuardrailEntry[]; donts?: GuardrailEntry[] }} />
          </DraftItem>
        ))}
      </div>
      {!isUnbranded(kit) && (
        <>
          <DraftField label="Approved indication" value={kit?.approved_indication}
            drafts={draftsFor(drafts, "approved_indication")} actions={actions} flag={flagFor("approved_indication")} />
          <DraftField label="Safety reference" value={kit?.safety_reference}
            drafts={draftsFor(drafts, "safety_reference")} actions={actions} flag={flagFor("safety_reference")} />
        </>
      )}
    </div>
  );
}
