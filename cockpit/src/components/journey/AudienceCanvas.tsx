import type { BrandKit, JourneyDraft, Persona } from "../../types";
import { DraftField, DraftItem, ValueView, type DraftActions } from "./DraftValue";
import { draftsFor } from "./journeyUtils";

export interface PersonaScope {
  group: string;
  name: string;
}

const GROUPS: { key: "hcp" | "patient" | "payer"; label: string }[] = [
  { key: "hcp", label: "HCP personas" },
  { key: "patient", label: "Patient personas" },
  { key: "payer", label: "Payer personas" },
];

function PersonaCardBody({ p }: { p: Partial<Persona> }) {
  return (
    <>
      <div className="persona-top"><strong>{p.name || "Unnamed persona"}</strong>{p.tier && <span className="pill pill-outline">{p.tier}</span>}</div>
      {p.who && <p className="persona-who">{p.who}</p>}
      {p.voice && <p className="persona-voice">{p.voice}</p>}
    </>
  );
}

/** Audience (R14): HCP and patient persona cards. Clicking a card scopes the next chat
 *  turn to it; clicking it again (or "back to Audience" in the chat strip) clears it. */
export function AudienceCanvas({ kit, drafts, actions, scope, onScope }: {
  kit: BrandKit | null;
  drafts: JourneyDraft[];
  actions: DraftActions;
  scope: PersonaScope | null;
  onScope: (s: PersonaScope | null) => void;
}) {
  const personaDrafts = draftsFor(drafts, "personas");

  return (
    <div className="jc-card">
      <DraftField label="Primary audience" value={kit?.primary_audience} drafts={draftsFor(drafts, "primary_audience")} actions={actions} />
      <div className="jc-field">
        <div className="jc-field-label">Persona cards</div>
        <div className="persona-groups">
          {GROUPS.map((g) => {
            const kept = kit?.personas?.[g.key] ?? [];
            const appended = personaDrafts.filter((d) => d.mode === "append" && d.path === g.key);
            if (kept.length === 0 && appended.length === 0) return null;
            return (
              <div key={g.key}>
                <div className="persona-group-label">{g.label}</div>
                <div className="jc-persona-grid">
                  {kept.map((p, i) => {
                    const active = scope?.group === g.key && scope.name === p.name;
                    return (
                      <button key={`${p.name}-${i}`} type="button" disabled={actions.locked}
                        className={`persona-card jc-persona ${active ? "active" : ""}`}
                        title={active ? "Back to Audience" : "Refine this card through chat"}
                        onClick={() => onScope(active ? null : { group: g.key, name: p.name })}>
                        <PersonaCardBody p={p} />
                      </button>
                    );
                  })}
                  {appended.map((d) => (
                    <DraftItem key={d.id} draft={d} actions={actions}>
                      <PersonaCardBody p={(d.value ?? {}) as Partial<Persona>} />
                    </DraftItem>
                  ))}
                </div>
              </div>
            );
          })}
          {!GROUPS.some((g) => (kit?.personas?.[g.key]?.length ?? 0) > 0) && personaDrafts.length === 0 && (
            <span className="jc-empty">No persona cards yet. Describe who you want to reach in the chat below.</span>
          )}
        </div>
        {personaDrafts.filter((d) => !(d.mode === "append" && d.path)).map((d) => (
          <DraftItem key={d.id} draft={d} actions={actions}>
            {GROUPS.map((g) => {
              const list = ((d.value ?? {}) as Record<string, Persona[]>)[g.key];
              if (d.mode === "append") return null; // un-pathed append: rendered raw below
              return Array.isArray(list) && list.length > 0 ? (
                <div key={g.key}>
                  <div className="persona-group-label">{g.label}</div>
                  <div className="jc-persona-grid">{list.map((p, i) => <div key={i} className="persona-card"><PersonaCardBody p={p} /></div>)}</div>
                </div>
              ) : null;
            })}
            {d.mode === "append" && <ValueView value={d.value} />}
          </DraftItem>
        ))}
      </div>
      <DraftField label="Competitors" value={kit?.competitors} drafts={draftsFor(drafts, "competitors")} actions={actions} />
    </div>
  );
}
