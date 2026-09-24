import { useState } from "react";
import type { BrandKit, JourneyStepId } from "../types";
import { inkSoft } from "../tokens";
// DispatchBoard / VoiceLinter / useMemo / Claim / RISK_TONE / STATUS_TONE: only used by
// the commented-out section block below (ClaimsLibrary needs useMemo/Claim/RISK_TONE/
// STATUS_TONE too).
// import { DispatchBoard } from "./DispatchBoard";
// import { VoiceLinter } from "./VoiceLinter";
import { StrategicOverview } from "./StrategicOverview";
import { BrandPersonaTable } from "./BrandPersonaTable";
import { HcpIntelligence } from "./HcpIntelligence";
import { NotPlanned, SectionMeta } from "./SectionMeta";
import { Icon } from "./Icon";

/** Top-level page section wrapper -- "Brand Intelligence" and "HCP Intelligence" are a
 *  step above the Panel/Expandable cards below them: they group several cards under one
 *  named section rather than being a card themselves. */
function PageSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="page-section">
      <div className="page-section-eyebrow">Section</div>
      <h2 className="page-section-title">{title}</h2>
      {children}
    </section>
  );
}

/** Honest empty state for a section this kit's data model doesn't cover yet -- same
 *  discipline as HcpIntelligence's Segmentation/Behaviours subsections: say plainly that
 *  nothing exists here rather than inventing channel/journey/budget/content data no kit
 *  field backs. */
function NotCaptured({ note }: { note: string }) {
  return <p className="hcp-unavailable">Not available. {note}</p>;
}

/** Section shell shared by every panel below -- gives the page one consistent rhythm
 *  instead of each section inventing its own card chrome. */
function Panel({ title, icon, kit, step, onUpdate, action, children }: {
  title: string;
  icon: React.ReactNode;
  kit?: BrandKit;
  step?: JourneyStepId;
  onUpdate?: (step: JourneyStepId) => void;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="panel">
      <div className="panel-head">
        <span className="panel-icon" aria-hidden>{icon}</span>
        <h2>{title}</h2>
        {kit && <SectionMeta kit={kit} step={step} onUpdate={onUpdate} />}
        {action && <div className="panel-action">{action}</div>}
      </div>
      <div className="panel-body">{children}</div>
    </section>
  );
}

/** Collapsible variant for the lower, denser sections (identity, guardrails, personas) --
 *  matches the reference UI's expandable-row pattern for the "brand-book" material that
 *  isn't needed at a glance the way proof points and safety are. Exported so
 *  HcpIntelligence.tsx uses the identical shell rather than a second copy. */
export function Expandable({ title, icon, subtitle, kit, step, onUpdate, children, defaultOpen = false }: {
  title: string;
  icon: React.ReactNode;
  subtitle: string;
  kit?: BrandKit;
  step?: JourneyStepId;
  onUpdate?: (step: JourneyStepId) => void;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="expandable">
      <button type="button" className="expandable-head" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <span className="panel-icon" aria-hidden>{icon}</span>
        <span className="expandable-title">
          <b>{title}</b>
          <span className="expandable-subtitle">{subtitle}</span>
        </span>
        {kit && <SectionMeta kit={kit} step={step} onUpdate={onUpdate} />}
        <span className={`chevron ${open ? "open" : ""}`}><Icon name="chevronDown" size={16} /></span>
      </button>
      {open && <div className="expandable-body">{children}</div>}
    </div>
  );
}

// Only used by the commented-out section block in BrandWorkspace() below -- kept, not
// deleted, so re-enabling that block doesn't also mean reconstructing these.
/*
function ProofPoints({ kit }: { kit: BrandKit }) {
  const pillars = kit.message_hierarchy.slice(0, 3);
  return (
    <div className="proof-grid">
      {pillars.map((p, i) => (
        <div className="proof-tile" key={p.pillar}>
          <div className="proof-eyebrow">PROOF POINT {i + 1}</div>
          <div className="proof-pillar">{p.pillar}</div>
          <div className="proof-claim">{p.claim}</div>
        </div>
      ))}
    </div>
  );
}

function IndicationAndSafety({ kit }: { kit: BrandKit }) {
  return (
    <div className="two-col">
      <div className="info-block info-primary">
        <div className="info-label">Approved indication (label)</div>
        <p>{kit.approved_indication}</p>
      </div>
      <div className="info-block info-warn">
        <div className="info-label">Safety reference</div>
        <p>{kit.safety_reference}</p>
      </div>
    </div>
  );
}

function ClinicalStats({ kit }: { kit: BrandKit }) {
  return (
    <div className="stat-grid">
      {kit.clinical_data.map((d) => (
        <div className="stat-tile" key={d.study + d.stat}>
          <div className="stat-study">{d.study}</div>
          <div className="stat-value">{d.stat}</div>
          <div className="stat-context">{d.context}</div>
        </div>
      ))}
    </div>
  );
}

// Claims library -- the axis the reference UI didn't cover at all, and per the brand
// workspace ideation the single richest entity in the kit. Grouped by status so the
// something-is-unapproved signal reads before any single claim's text does.
function ClaimsLibrary({ kit }: { kit: BrandKit }) {
  const [filter, setFilter] = useState<string>("all");
  const refById = useMemo(
    () => Object.fromEntries(kit.references.map((r) => [r.id, r])),
    [kit.references],
  );
  const counts = useMemo(() => {
    const c: Record<string, number> = { draft: 0, in_review: 0, approved: 0 };
    for (const cl of kit.claims) c[cl.status] = (c[cl.status] ?? 0) + 1;
    return c;
  }, [kit.claims]);
  const shown = filter === "all" ? kit.claims : kit.claims.filter((c) => c.status === filter);

  return (
    <div>
      <div className="filter-row">
        {(["all", "draft", "in_review", "approved"] as const).map((f) => (
          <button
            key={f}
            type="button"
            className={`filter-chip ${filter === f ? "active" : ""}`}
            onClick={() => setFilter(f)}
          >
            {f === "all" ? `All ${kit.claims.length}` : `${STATUS_TONE[f]?.label ?? f} ${counts[f] ?? 0}`}
          </button>
        ))}
      </div>
      <div className="claim-list">
        {shown.map((claim: Claim) => {
          const riskTone = RISK_TONE[claim.risk] ?? "warning";
          const status = STATUS_TONE[claim.status] ?? STATUS_TONE.draft;
          return (
            <div className="claim-row" key={claim.id}>
              <div className="claim-id">{claim.id}</div>
              <div className="claim-body">
                <p className="claim-text">{claim.text}</p>
                <div className="claim-meta">
                  <span className={`pill tone-${status.tone}`}>{status.label}</span>
                  <span className={`pill tone-${riskTone}`}>Risk: {claim.risk}</span>
                  <span className="pill pill-outline">{claim.category}</span>
                  {claim.references.map((rid) => (
                    <span className="pill pill-outline" key={rid} title={refById[rid]?.title}>{rid}</span>
                  ))}
                </div>
                {claim.note && <p className="claim-note">{claim.note}</p>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function IdentitySystem({ kit }: { kit: BrandKit }) {
  return (
    <div>
      <div className="swatch-row">
        {kit.identity.palette.map((c) => (
          <div className="swatch" key={c.hex}>
            <div className="swatch-color" style={{ background: c.hex }} />
            <div className="swatch-name">{c.name}</div>
            <div className="swatch-hex">{c.hex}</div>
            <div className="swatch-use">{c.use}</div>
          </div>
        ))}
      </div>
      <p className="typography-line"><b>Typography</b> &middot; {kit.identity.typography}</p>
    </div>
  );
}
*/

function GuardrailsPanel({ kit, onOpen }: { kit: BrandKit; onOpen?: (step: JourneyStepId) => void }) {
  if (kit.guardrails.dos.length === 0 && kit.guardrails.donts.length === 0) {
    return <p className="hcp-unavailable"><NotPlanned step="kit" onOpen={onOpen} className="" /></p>;
  }
  return (
    <div className="two-col">
      <div>
        <div className="info-label info-label-do">Do</div>
        <ul className="guardrail-list">
          {kit.guardrails.dos.map((d, i) => (
            <li key={i}><span className="guardrail-category">{d.category}:</span> {d.text}</li>
          ))}
        </ul>
      </div>
      <div>
        <div className="info-label info-label-dont">Don't</div>
        <ul className="guardrail-list">
          {kit.guardrails.donts.map((d, i) => (
            <li key={i}><span className="guardrail-category">{d.category}:</span> {d.text}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}

// Only used by the commented-out section block in BrandWorkspace() below.
/*
function PersonasPanel({ kit }: { kit: BrandKit }) {
  const groups: { label: string; items: typeof kit.personas.hcp }[] = [
    { label: "Patient", items: kit.personas.patient },
    { label: "Payer", items: kit.personas.payer },
  ];
  return (
    <div className="persona-groups">
      {groups.map((g) => g.items?.length ? (
        <div key={g.label} className="persona-group">
          <div className="persona-group-label">{g.label}</div>
          {g.items.map((p) => (
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
      ) : null)}
    </div>
  );
}
*/

export function BrandWorkspace({ brand, kit, onUpdate }: {
  brand: string;
  kit: BrandKit;
  onUpdate?: (step: JourneyStepId) => void;
}) {
  return (
    <div className="workspace">
      {/* Generic page-level info -- brand facts + the insight tiles (including Active
          concepts). Everything below this belongs to a named section; this doesn't, so it
          sits outside any PageSection. */}
      <StrategicOverview brand={brand} kit={kit} onUpdate={onUpdate} />

      <PageSection title="Brand Intelligence">
        <div className="expandable-stack">
          <Expandable title="Brand persona" icon={<Icon name="persona" />} kit={kit} step="message" onUpdate={onUpdate} subtitle="Role, promise, tone, territories -- what's captured and what isn't">
            <BrandPersonaTable kit={kit} onOpen={onUpdate} />
          </Expandable>

          <Expandable title="Communication guardrails" icon={<Icon name="shield" />} kit={kit} step="kit" onUpdate={onUpdate} subtitle="Brand dos &amp; don'ts">
            <GuardrailsPanel kit={kit} onOpen={onUpdate} />
          </Expandable>
        </div>
      </PageSection>

      <PageSection title="HCP Intelligence">
        <HcpIntelligence kit={kit} onUpdate={onUpdate} />
      </PageSection>

      {/* Everything below HCP Intelligence down to the closing comment is on hold --
          replaced on-page by Channel Mix / Journeys & Flows / Budget / Content below.
          Left in place (not deleted) since the kit still carries this data and the
          Update flow's Patient & payer personas / Identity / Voice-check entry points
          live here; re-enable by uncommenting whenever these should return to the page.

      <DispatchBoard kit={kit} />

      <Panel title="Proof points" icon="&#9733;" kit={kit}>
        <ProofPoints kit={kit} />
      </Panel>

      <Panel title="Indication &amp; safety" icon="&#9888;" kit={kit}>
        <IndicationAndSafety kit={kit} />
      </Panel>

      <Panel title="Clinical data" icon="&#128202;" kit={kit}>
        <ClinicalStats kit={kit} />
      </Panel>

      <Panel
        title="Claims library"
        icon="&#128220;" kit={kit}
        action={<span className="panel-hint">{kit.claims.length} claims &middot; {kit.references.length} references</span>}
      >
        <ClaimsLibrary kit={kit} />
      </Panel>

      <div className="expandable-stack">
        <Expandable title="Brand identity system" icon="&#127912;" kit={kit} subtitle="Palette &middot; Typography">
          <IdentitySystem kit={kit} />
        </Expandable>
        <Expandable title="Voice check" icon="&#127908;" kit={kit} subtitle={`${kit.voice_dont.length} banned terms, checked live against your draft`}>
          <VoiceLinter kit={kit} />
        </Expandable>
        <Expandable title="Patient &amp; payer personas" icon="&#128100;" kit={kit} step="audience" onUpdate={onUpdate} subtitle="HCP personas now live in the HCP Intelligence section above">
          <PersonasPanel kit={kit} />
        </Expandable>
      </div>

      */}

      <PageSection title="Channel Mix">
        <div className="expandable-stack">
          <Expandable title="HCP channels" icon={<Icon name="mail" />} subtitle="Not available in this kit" kit={kit}>
            <NotCaptured note="Channel-mix planning (rep, email, web, paid media, congress) isn't part of this kit's data model yet." />
          </Expandable>
          <Expandable title="Patient channels" icon={<Icon name="smartphone" />} subtitle="Not available in this kit" kit={kit}>
            <NotCaptured note="Patient-facing channel mix isn't captured in this kit yet." />
          </Expandable>
          <Expandable title="Channel weighting" icon={<Icon name="scale" />} subtitle="Not available in this kit" kit={kit}>
            <NotCaptured note="Budget/effort weighting across channels isn't captured in this kit yet." />
          </Expandable>
        </div>
      </PageSection>

      <PageSection title="Journeys &amp; Flows">
        <div className="expandable-stack">
          <Expandable title="HCP journey" icon={<Icon name="map" />} subtitle="Not available in this kit" kit={kit}>
            <NotCaptured note="A defined HCP engagement journey isn't captured in this kit yet." />
          </Expandable>
          <Expandable title="Patient journey" icon={<Icon name="heartPulse" />} subtitle="Not available in this kit" kit={kit}>
            <NotCaptured note="A defined patient journey isn't captured in this kit yet." />
          </Expandable>
          <Expandable title="Trigger flows" icon={<Icon name="zap" />} subtitle="Not available in this kit" kit={kit}>
            <NotCaptured note="Automated trigger/response flows aren't captured in this kit yet." />
          </Expandable>
        </div>
      </PageSection>

      <Panel title="Budget" icon={<Icon name="wallet" />} kit={kit}>
        <NotCaptured note="No budget or spend allocation is captured in this kit yet." />
      </Panel>

      <PageSection title="Content">
        <div className="expandable-stack">
          <Expandable title="Content library" icon={<Icon name="document" />} subtitle="Not available in this kit" kit={kit}>
            <NotCaptured note="A structured content/asset library isn't captured in this kit yet." />
          </Expandable>
          <Expandable title="Content-to-channel mapping" icon={<Icon name="link" />} subtitle="Not available in this kit" kit={kit}>
            <NotCaptured note="Which content plays on which channel isn't captured in this kit yet." />
          </Expandable>
        </div>
      </PageSection>

      <p className="footnote" style={{ color: inkSoft }}>
        Source: {kit.source_label} &middot; {kit.source_note}
      </p>
    </div>
  );
}
