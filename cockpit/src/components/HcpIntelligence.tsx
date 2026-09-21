import type { BrandKit, KitUpdateSection, Persona } from "../types";
import { Expandable } from "./BrandWorkspace";
import { Icon } from "./Icon";

function joinField(v: string | string[] | undefined): string | null {
  if (!v) return null;
  return Array.isArray(v) ? v.join(", ") : v;
}

/** The marketer-depth fields (U1) -- all optional, rendered only when a field is
 *  actually present so a persona that hasn't been through the generation flow yet
 *  looks exactly like it did before this feature existed. */
function PersonaDetail({ p }: { p: Persona }) {
  const rows: [string, string | null][] = [
    ["Practice", p.practice_setting ?? null],
    ["Goals", joinField(p.goals)],
    ["Barriers", joinField(p.barriers)],
    ["Prefers", p.channel_preference ?? null],
    ["Objections", joinField(p.objections)],
    ["Message that lands", p.message_resonance ?? null],
  ].filter(([, v]) => v !== null) as [string, string][];

  if (!p.narrative && rows.length === 0) return null;

  return (
    <div className="persona-detail">
      {p.narrative && <p className="persona-narrative">{p.narrative}</p>}
      {rows.length > 0 && (
        <dl className="persona-detail-grid">
          {rows.map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}

/** HCP Intelligence -- four subsections. Only two are groundable from this kit today:
 *  Personas (kit.personas.hcp, real) and Needs (each persona's own `voice` quote, which
 *  IS the closest real signal to a stated need/ask this kit carries). Segmentation and
 *  Behaviours have no source anywhere in the kit -- confirmed by extensive grounding
 *  earlier: segment data lives in a completely separate config the cockpit doesn't even
 *  fetch, and there is no behavioural field on a persona at all. Both say so plainly
 *  rather than repurposing persona text to fake a structured framework that doesn't exist
 *  yet. Collapsible, reusing BrandWorkspace's Expandable shell -- the two "not available"
 *  subsections default closed so the page isn't led with empty-state text. */
export function HcpIntelligence({ kit, onUpdate }: {
  kit: BrandKit;
  onUpdate?: (section: KitUpdateSection) => void;
}) {
  const hcps = kit.personas.hcp;

  return (
    <div className="expandable-stack">
      <Expandable title="HCP Personas" icon={<Icon name="persona" />} kit={kit} section="kit-hcp-persona" onUpdate={onUpdate} subtitle={`${hcps.length} primary/secondary personas from the kit`}>
        <div className="persona-groups">
          {hcps.map((p) => (
            <div className="persona-card" key={p.name}>
              <div className="persona-top">
                <b>{p.name}</b>
                <span className="pill pill-outline">{p.tier}</span>
              </div>
              <p className="persona-who">{p.who}</p>
              <p className="persona-voice">&ldquo;{p.voice}&rdquo;</p>
              <PersonaDetail p={p} />
            </div>
          ))}
        </div>
      </Expandable>

      <Expandable title="HCP Segmentation" icon={<Icon name="barChart" />} kit={kit} subtitle="Not available in this kit">
        <p className="hcp-unavailable">
          Not available. No segmentation data exists in this brand kit -- audience segments live in a
          separate part of the app (behavioural HCP-panel segments, not brand-specific) and aren't
          wired into this kit yet.
        </p>
      </Expandable>

      <Expandable title="HCP Behaviours" icon={<Icon name="eye" />} kit={kit} subtitle="Not available in this kit">
        <p className="hcp-unavailable">
          Not available. The kit has no behavioural field on a persona -- only who they are and what
          they ask for (below).
        </p>
      </Expandable>

      <Expandable title="HCP Needs / Barriers" icon={<Icon name="message" />} kit={kit} subtitle="In each persona's own words">
        <div className="persona-groups">
          {hcps.map((p) => (
            <div className="persona-card" key={p.name}>
              <div className="persona-top"><b>{p.name.split(" (")[0]}</b></div>
              <p className="persona-who">In their own words, from the kit:</p>
              <p className="persona-voice">&ldquo;{p.voice}&rdquo;</p>
            </div>
          ))}
        </div>
      </Expandable>
    </div>
  );
}
