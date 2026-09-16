import { useState } from "react";
import type { BrandKit, KitUpdateSection } from "../types";
import { Icon } from "./Icon";

/** The brand-details section, leading the workspace -- everything below (claims, identity,
 *  guardrails) is detail; this is the "what is this brand, in one glance" answer, so it has
 *  to come first. Every field here is a direct read from the kit, nothing computed or
 *  guessed: no lifecycle-stage or market-share figure gets invented for a fact the kit
 *  doesn't carry. `key_objective` and `market_share` are genuinely absent from Oncomyra's
 *  kit (its own source document doesn't carry commercial-planning metadata) -- that fact
 *  row shows "Not captured" rather than a number pulled from nowhere. Cardiovex, being an
 *  openly fictional demo brand with no pretense of being sourced from a real document,
 *  carries illustrative values for both, clearly labelled as such in the JSON itself.
 *
 *  The four insight tiles deliberately do NOT use tone colours (info/success/warning/danger)
 *  the way claim-risk pills do elsewhere -- a claim's risk tier is a real severity signal,
 *  but "HCPs" vs "competitors" vs "needs" has no severity ordering, so tinting them red/
 *  green/amber/blue implied a meaning that wasn't there. One neutral card shape, no icons --
 *  differentiated by the title and content only.
 *
 *  "Unmet needs" is a DERIVED tile, not a new invented field: it reuses each message-
 *  hierarchy pillar's own `claim` text (every core message exists to answer some unmet
 *  need) -- same discipline as "Key message territories" reusing pillar `name`s. Zero new
 *  facts, just a second lens on data already in the kit. */
export function StrategicOverview({ brand, kit, onUpdate }: {
  brand: string;
  kit: BrandKit;
  onUpdate?: (section: KitUpdateSection) => void;
}) {
  const facts: { label: string; value: string | null }[] = [
    { label: "Indication", value: kit.indication },
    { label: "Lifecycle stage", value: kit.fiscal_frame },
    { label: "Market share (current -> target)", value: kit.market_share ? `${kit.market_share.current} -> ${kit.market_share.target}` : null },
    { label: "Key objective", value: kit.key_objective ?? null },
  ];

  const primaryHcps = kit.personas.hcp.filter((p) => p.tier === "Primary");
  const territories = kit.message_hierarchy.map((m) => m.pillar);
  const competitors = kit.competitors;
  const unmetNeeds = kit.message_hierarchy.map((m) => m.claim);

  return (
    <section className="overview">
      {kit.illustrative && (
        <div className="illustrative-banner">
          <span className="illustrative-tag">Illustrative</span>
          <span>{kit.note ?? `Placeholder content for ${kit.territory} -- not real regulatory data.`}</span>
        </div>
      )}
      <div className="overview-card">
        <div className="overview-top">
          <div className="overview-top-left">
            <div className="overview-label">Brand</div>
            <h1 className="overview-brand">{brand}</h1>
            <p className="overview-tagline">{kit.tagline}</p>
          </div>
          <BrandStatusBadges kit={kit} onUpdate={onUpdate} />
        </div>

        <div className="overview-facts">
          {facts.map((f) => (
            <div className="overview-fact" key={f.label}>
              <div className="overview-fact-label">{f.label}</div>
              <div className="overview-fact-value">
                {f.value ?? <span className="overview-fact-missing">Not captured in this kit yet</span>}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="insight-grid insight-grid-2x2">
        <div className="insight-tile">
          <div className="insight-title">Target HCPs</div>
          <div className="insight-body">
            {primaryHcps.length > 0 ? primaryHcps.map((p) => p.name.split(" (")[0]).join(", ") : "Not captured in this kit yet"}
          </div>
        </div>
        <div className="insight-tile">
          <div className="insight-title">Key message territories</div>
          <div className="insight-body">
            {territories.length > 0 ? territories.join(", ") : "Not captured in this kit yet"}
          </div>
        </div>
        <div className="insight-tile">
          <div className="insight-title">Key competitors</div>
          <div className="insight-body">
            {competitors.length > 0 ? competitors.map((c) => c.name).join(", ") : "Not captured in this kit yet"}
          </div>
        </div>
        <div className="insight-tile">
          <div className="insight-title">Unmet needs</div>
          <div className="insight-body">
            {unmetNeeds.length > 0 ? unmetNeeds.join(" · ") : "Not captured in this kit yet"}
          </div>
        </div>
      </div>
    </section>
  );
}

/** Top-right of the brand card: a real, honest status ("Brand plan ingested" -- true, since
 *  the page can only render this kit because it loaded successfully) plus the same
 *  alert-triangle "when / based on what" pattern used everywhere else, extended here with a
 *  View action alongside Update. View is a real action (expands + scrolls to the Brand
 *  Persona section, the closest thing on this page to "the brand plan"), not another stub --
 *  Update stays an honest stub since editing genuinely isn't wired up yet. */
function BrandStatusBadges({ kit, onUpdate }: {
  kit: BrandKit;
  onUpdate?: (section: KitUpdateSection) => void;
}) {
  const [open, setOpen] = useState(false);

  const formatWhen = (iso?: string) => {
    if (!iso) return "unknown";
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? "unknown" : d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  };

  const goToBrandPersona = () => {
    setOpen(false);
    const head = [...document.querySelectorAll(".expandable-head")].find((h) => h.textContent?.includes("Brand persona"));
    if (!head) return;
    if (head.getAttribute("aria-expanded") === "false") (head as HTMLButtonElement).click();
    head.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="overview-badges">
      <span className="pill tone-success overview-ingested">
        <Icon name="check" size={13} aria-hidden="true" /> Brand plan ingested
      </span>
      <div className="section-meta">
        <button
          type="button"
          className="section-meta-trigger"
          aria-label="When this was last updated"
          title="When this was last updated"
          onClick={() => setOpen((o) => !o)}
        >
          <Icon name="alertTriangle" size={15} />
        </button>
        {open && (
          <div className="section-meta-popover">
            <div className="section-meta-row">
              <span className="section-meta-label">Last updated</span>
              <span>{formatWhen(kit.updated_at)}</span>
            </div>
            <div className="section-meta-row">
              <span className="section-meta-label">Based on</span>
              <span>{kit.source_label}</span>
            </div>
            <p className="section-meta-caveat">
              This is the brand kit file's own timestamp -- every section shares it. There is no
              per-section change history yet.
            </p>
            <div className="section-meta-actions">
              <button type="button" className="section-meta-update" onClick={goToBrandPersona}>View</button>
              {onUpdate && (
                <button type="button" className="section-meta-update" onClick={() => onUpdate("kit-brand-details")}>Update</button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
