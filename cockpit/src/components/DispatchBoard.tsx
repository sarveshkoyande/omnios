import { useState } from "react";
import type { BrandKit } from "../types";
import { deriveGates } from "../gate";
import { Icon } from "./Icon";

/** The dispatch board -- rendered first, above proof points, because idea 2's whole point
 *  is that a pre-PI brand's restrictions are the loudest thing worth knowing, not a footnote
 *  under the content. A gate here is a normal operating condition, not an error: it always
 *  states what you may still say, not just what you can't. */
export function DispatchBoard({ kit }: { kit: BrandKit }) {
  const gates = deriveGates(kit);
  const [open, setOpen] = useState(true);
  if (gates.length === 0) return null;

  return (
    <section className="dispatch-board">
      <button type="button" className="dispatch-head" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <span className="dispatch-icon" aria-hidden><Icon name="alertTriangle" size={18} /></span>
        <span className="dispatch-title">
          <b>{gates.length} claim{gates.length === 1 ? "" : "s"} currently gated</b>
          <span className="dispatch-subtitle">What you can't say, why, what clears it, and what you may say meanwhile</span>
        </span>
        <span className={`chevron ${open ? "open" : ""}`}><Icon name="chevronDown" size={16} /></span>
      </button>
      {open && (
        <div className="dispatch-rows">
          {gates.map((g) => (
            <div className="dispatch-row" key={g.claim.id}>
              <div className="dispatch-claim-id">{g.claim.id}</div>
              <div className="dispatch-fields">
                <p className="dispatch-claim-text">{g.claim.text}</p>
                <dl className="dispatch-dl">
                  <dt>Why blocked</dt>
                  <dd>{g.why}</dd>
                  <dt>What clears it</dt>
                  <dd>{g.unblocks}</dd>
                  <dt>What you may say meanwhile</dt>
                  <dd className="dispatch-may">{g.mayStillSay}</dd>
                </dl>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
