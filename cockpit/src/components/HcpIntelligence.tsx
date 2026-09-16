import type { BrandKit, KitUpdateSection } from "../types";
import { Expandable } from "./BrandWorkspace";

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
      <Expandable title="HCP Personas" icon="&#128100;" kit={kit} section="kit-hcp-persona" onUpdate={onUpdate} subtitle={`${hcps.length} primary/secondary personas from the kit`}>
        <div className="persona-groups">
          {hcps.map((p) => (
            <div className="persona-card" key={p.name}>
              <div className="persona-top">
                <b>{p.name}</b>
                <span className="pill pill-outline">{p.tier}</span>
              </div>
              <p className="persona-who">{p.who}</p>
              <p className="persona-voice">&ldquo;{p.voice}&rdquo;</p>
            </div>
          ))}
        </div>
      </Expandable>

      <Expandable title="HCP Segmentation" icon="&#128202;" kit={kit} subtitle="Not available in this kit">
        <p className="hcp-unavailable">
          Not available. No segmentation data exists in this brand kit -- audience segments live in a
          separate part of the app (behavioural HCP-panel segments, not brand-specific) and aren't
          wired into this kit yet.
        </p>
      </Expandable>

      <Expandable title="HCP Behaviours" icon="&#128064;" kit={kit} subtitle="Not available in this kit">
        <p className="hcp-unavailable">
          Not available. The kit has no behavioural field on a persona -- only who they are and what
          they ask for (below).
        </p>
      </Expandable>

      <Expandable title="HCP Needs / Barriers" icon="&#128172;" kit={kit} subtitle="In each persona's own words">
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
