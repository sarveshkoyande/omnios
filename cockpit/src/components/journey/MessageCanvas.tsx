import type { BrandKit, JourneyDraft, MessagePillar } from "../../types";
import { DraftField, DraftItem, type DraftActions } from "./DraftValue";
import { draftsFor, hasValue } from "./journeyUtils";

function PillarList({ pillars }: { pillars: Partial<MessagePillar>[] }) {
  if (pillars.length === 0) return <span className="jc-empty">Not set yet</span>;
  return (
    <div className="proof-grid">
      {pillars.map((p, i) => (
        <div key={i} className="proof-tile">
          <div className="proof-eyebrow">Pillar {i + 1}</div>
          <div className="proof-pillar">{p.pillar || "Untitled pillar"}</div>
          <div className="proof-claim">{p.claim}</div>
          {hasValue(p.evidence)
            ? <div className="jc-proof">Proof: {p.evidence}</div>
            : <div className="jc-flag">No supporting evidence for this claim</div>}
        </div>
      ))}
    </div>
  );
}

/** Message (R13): the message house -- core claim, pillars with proof points, and voice.
 *  A pillar claim with empty evidence is flagged, kept or drafted. */
export function MessageCanvas({ kit, drafts, actions }: {
  kit: BrandKit | null;
  drafts: JourneyDraft[];
  actions: DraftActions;
}) {
  const unbranded = String(kit?.branded ?? "").toLowerCase() === "unbranded";
  const f = (key: keyof BrandKit, label: string) => (
    <DraftField key={key} label={label} value={kit?.[key]} drafts={draftsFor(drafts, key)} actions={actions} />
  );
  const pillarDrafts = draftsFor(drafts, "message_hierarchy");

  return (
    <div className="jc-card">
      {!unbranded && f("core_claim", "Core claim")}
      {f("positioning_statement", "Positioning")}
      {f("tagline", "Tagline")}
      {!unbranded && (
        <div className="jc-field">
          <div className="jc-field-label">Pillars and proof points</div>
          <PillarList pillars={kit?.message_hierarchy ?? []} />
          {pillarDrafts.map((d) => (
            <DraftItem key={d.id} draft={d} actions={actions}>
              <PillarList pillars={(Array.isArray(d.value) ? d.value : [d.value]) as Partial<MessagePillar>[]} />
            </DraftItem>
          ))}
        </div>
      )}
      {f("tone_pillars", "Tone")}
      {f("voice_do", "Voice: use")}
      {f("voice_dont", "Voice: avoid")}
      {f("brand_personification", "If the brand were a person")}
    </div>
  );
}
