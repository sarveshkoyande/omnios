import { useState } from "react";
import { Icon } from "../../components/Icon";

/** Camille's assumptions checkpoint (AmbiguityCard): the impactful assumptions left after the
 *  clarifications. Accept them all, or override any of them; an untouched one is sent as
 *  "Accepted default assumption", exactly as Camille did. */
export function AssumptionCard({ assumptions, resolved, disabled, onAccept, onResolve }: {
  assumptions: string[];
  resolved: string | null;
  disabled: boolean;
  onAccept: () => void;
  onResolve: (text: string) => void;
}) {
  const [notes, setNotes] = useState<Record<number, string>>({});

  if (resolved !== null) {
    return (
      <div className="v3-cc-card done">
        <div className="v3-cc-card-head">
          <span className="v3-cc-card-icon"><Icon name="check" size={14} /></span>
          <div><b>Assumptions reviewed</b><span>{resolved === "Accepted all assumptions" ? "All accepted as stated" : "Clarified by you"}</span></div>
        </div>
      </div>
    );
  }

  const resolve = () => onResolve(assumptions.map((a, i) =>
    `Ambiguity: ${a}\nUser Clarification: ${(notes[i] ?? "").trim() || "Accepted default assumption"}`).join("\n\n"));

  return (
    <form className="v3-cc-card v3-cc-assume" onSubmit={(e) => { e.preventDefault(); if (!disabled) resolve(); }}>
      <div className="v3-cc-card-head">
        <span className="v3-cc-card-icon warn"><Icon name="alertTriangle" size={14} /></span>
        <div>
          <b>Ambiguities &amp; assumptions detected</b>
          <span>Clarify any of these, or accept the default assumptions to proceed.</span>
        </div>
      </div>
      {assumptions.map((a, i) => (
        <div key={i} className="v3-cc-assume-item">
          <div><em className="v3-cc-badge warn">Assumption #{i + 1}</em> <span>{a}</span></div>
          <input className="v3-cc-input" value={notes[i] ?? ""} disabled={disabled}
            placeholder="Optional: provide a clarification or override…"
            onChange={(e) => setNotes((n) => ({ ...n, [i]: e.target.value }))} />
        </div>
      ))}
      <div className="v3-cc-card-actions">
        <button type="button" className="v3-cc-btn" disabled={disabled} onClick={onAccept}>Accept all assumptions &amp; continue</button>
        <button type="submit" className="v3-cc-btn primary" disabled={disabled}>Submit clarifications</button>
      </div>
    </form>
  );
}
