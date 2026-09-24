import { useState } from "react";
import type { BrandKit, JourneyDraft } from "../../types";
import { DraftField, type DraftActions } from "./DraftValue";
import { draftsFor } from "./journeyUtils";

const TERRITORY_CHIPS = ["US", "EU", "UK", "Japan", "Canada"];

/** Brief (R12): one field card. Territory is a chip question with an "other" option. */
export function BriefCanvas({ brand, kit, drafts, actions, onSend }: {
  brand: string;
  kit: BrandKit | null;
  drafts: JourneyDraft[];
  actions: DraftActions;
  onSend: (message: string) => void;
}) {
  const [otherOpen, setOtherOpen] = useState(false);
  const [other, setOther] = useState("");
  const territories = kit?.territories ?? [];
  const chipsDisabled = actions.locked || actions.busy;
  const pickTerritory = (t: string) => onSend(`Territory: ${t}`);

  const field = (key: keyof BrandKit, label: string) => (
    <DraftField key={key} label={label} value={kit?.[key]} drafts={draftsFor(drafts, key)} actions={actions} />
  );

  return (
    <div className="jc-card">
      <DraftField label="Brand name" value={brand} drafts={draftsFor(drafts, "brand_name")} actions={actions} />
      {field("indication", "Indication")}
      <DraftField label="Territory" value={territories} drafts={draftsFor(drafts, "territories")} actions={actions}>
        <div className="jc-chiplist">
          {TERRITORY_CHIPS.map((t) => (
            <button key={t} type="button" disabled={chipsDisabled}
              className={`filter-chip ${territories.includes(t) ? "active" : ""}`}
              onClick={() => pickTerritory(t)}>{t}</button>
          ))}
          {territories.filter((t) => !TERRITORY_CHIPS.includes(t)).map((t) => (
            <button key={t} type="button" className="filter-chip active" disabled>{t}</button>
          ))}
          <button type="button" disabled={chipsDisabled} className={`filter-chip ${otherOpen ? "active" : ""}`}
            onClick={() => setOtherOpen((o) => !o)}>Other</button>
        </div>
        {otherOpen && (
          <form className="jc-inline-form" onSubmit={(e) => {
            e.preventDefault();
            if (other.trim()) { pickTerritory(other.trim()); setOther(""); setOtherOpen(false); }
          }}>
            <input className="jc-input" value={other} placeholder="Another territory" disabled={chipsDisabled}
              onChange={(e) => setOther(e.target.value)} />
            <button type="submit" className="jc-btn" disabled={chipsDisabled || !other.trim()}>Use</button>
          </form>
        )}
      </DraftField>
      {field("lifecycle_stage", "Lifecycle stage")}
      {field("key_objective", "Objective")}
      {field("success_measure", "Success measure")}
      {field("branded", "Branded or unbranded")}
    </div>
  );
}
