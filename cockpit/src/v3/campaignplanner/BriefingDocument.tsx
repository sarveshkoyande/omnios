import type { Briefing } from "./api";

/** "primaryAudience" -> "Primary Audience" (Camille's overview labels). */
function label(key: string): string {
  const spaced = key.replace(/([A-Z])/g, " $1").trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

const NS = "Not specified by user";

/** Camille's Campaign Briefing Document (CampaignBriefingDocument.js), in the Cockpit's look.
 *  Section numbers follow Camille's: Key Decisions is section 2 when present, and the later
 *  sections keep their numbers either way. */
export function BriefingDocument({ briefing, version, footer }: { briefing: Briefing; version?: number; footer?: string }) {
  const b = briefing;
  const ov = Object.entries(b.campaignOverview ?? {});
  const seg = b.audienceSegmentation ?? { rule: "", segments: [] };
  return (
    <article className="v3-cc-doc">
      <header className="v3-cc-doc-head">
        <div className="v3-cc-doc-label"><span>Campaign Briefing Document</span><em>Confidential</em></div>
        <h1>{b.campaignName || "Campaign Briefing"}</h1>
      </header>

      <section className="v3-cc-doc-sec">
        <h2>1. Campaign Overview</h2>
        <table className="v3-cc-table kv">
          <tbody>
            {ov.map(([k, v]) => <tr key={k}><th>{label(k)}</th><td>{v || NS}</td></tr>)}
          </tbody>
        </table>
      </section>

      {b.keyDecisions?.length > 0 && (
        <section className="v3-cc-doc-sec">
          <h2>2. Key Decisions &amp; Assumptions</h2>
          <table className="v3-cc-table">
            <thead><tr><th>Decision Point</th><th>User Decision</th><th>Impact on Campaign</th></tr></thead>
            <tbody>{b.keyDecisions.map((d, i) => <tr key={i}><th>{d.question}</th><td>{d.decision}</td><td>{d.impact}</td></tr>)}</tbody>
          </table>
        </section>
      )}

      <section className="v3-cc-doc-sec">
        <h2>3. Audience Segmentation</h2>
        <p className="v3-cc-doc-rule"><em>Rule: {seg.rule || NS}</em></p>
        {seg.segments.length > 0 && (
          <div className="v3-cc-segments">
            {seg.segments.map((s, i) => (
              <div key={i} className="v3-cc-segment">
                <b>{s.name || `Segment ${i + 1}`}</b>
                <div><strong>HCP Specialty:</strong> {s.hcpSpecialty || "—"}</div>
                <div><strong>Segment:</strong> {s.segmentType || "—"}</div>
                {s.details.length > 0 && <ul>{s.details.map((d, j) => <li key={j}>{d}</li>)}</ul>}
                {s.messageFocus && <div className="v3-cc-segment-focus"><strong>Message focus:</strong> {s.messageFocus}</div>}
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="v3-cc-doc-sec">
        <h2>4. SFMC Capabilities Used</h2>
        {b.sfmcCapabilities?.length ? (
          <table className="v3-cc-table">
            <thead><tr><th>Capability</th><th>Use</th></tr></thead>
            <tbody>{b.sfmcCapabilities.map((c, i) => <tr key={i}><th>{c.capability}</th><td>{c.use}</td></tr>)}</tbody>
          </table>
        ) : <p className="v3-cc-doc-empty">{NS}</p>}
      </section>

      <section className="v3-cc-doc-sec">
        <h2>5. Journey Entry Criteria</h2>
        {b.journeyEntryCriteria?.length ? <ol>{b.journeyEntryCriteria.map((c, i) => <li key={i}>{c}</li>)}</ol> : <p className="v3-cc-doc-empty">{NS}</p>}
      </section>

      <section className="v3-cc-doc-sec">
        <h2>6. Design Principles (incl. Consent Governance)</h2>
        {b.designPrinciples?.length ? (
          <table className="v3-cc-table">
            <thead><tr><th>Category</th><th>Principles</th></tr></thead>
            <tbody>
              {b.designPrinciples.map((p, i) => (
                <tr key={i}><th>{p.category || "—"}</th><td><ul>{p.principles.map((x, j) => <li key={j}>{x}</li>)}</ul></td></tr>
              ))}
            </tbody>
          </table>
        ) : <p className="v3-cc-doc-empty">{NS}</p>}
      </section>

      <section className="v3-cc-doc-sec">
        <h2>7. Journey Flow (Step-by-Step)</h2>
        {b.journeyFlow?.length ? (
          <table className="v3-cc-table">
            <thead><tr><th>Timing</th><th>Stage</th><th>Actions</th></tr></thead>
            <tbody>{b.journeyFlow.map((j, i) => <tr key={i}><th className="narrow">{j.timing}</th><th>{j.stage}</th><td>{j.actions}</td></tr>)}</tbody>
          </table>
        ) : <p className="v3-cc-doc-empty">{NS}</p>}
      </section>

      <section className="v3-cc-doc-sec">
        <h2>8. Decision Logic (Compact)</h2>
        <p className="v3-cc-doc-rule"><em>Key decision question: {b.decisionLogic?.keyQuestion || NS}</em></p>
        {b.decisionLogic?.rules?.length > 0 && <ol>{b.decisionLogic.rules.map((r, i) => <li key={i}>{r.rule}</li>)}</ol>}
      </section>

      <section className="v3-cc-doc-sec">
        <h2>9. Operational Rules &amp; Safeguards</h2>
        {b.operationalRules?.length ? <ul>{b.operationalRules.map((r, i) => <li key={i}>{r}</li>)}</ul> : <p className="v3-cc-doc-empty">{NS}</p>}
      </section>

      <section className="v3-cc-doc-sec">
        <h2>10. Measurement &amp; Reporting</h2>
        {b.measurementReporting?.length ? (
          <table className="v3-cc-table">
            <thead><tr><th>Tier</th><th>Metrics</th></tr></thead>
            <tbody>{b.measurementReporting.map((m, i) => <tr key={i}><th>{m.tier}</th><td>{m.metrics}</td></tr>)}</tbody>
          </table>
        ) : <p className="v3-cc-doc-empty">{NS}</p>}
      </section>

      <section className="v3-cc-doc-sec">
        <h2>11. Journey End Goals</h2>
        <p>{b.journeyEndGoals || NS}</p>
      </section>

      <footer className="v3-cc-doc-foot">
        <span>Omni Campaign Planner | {b.campaignName || "Campaign Briefing"}</span>
        <span>{footer ?? (version ? `Briefing v${version}` : "")}</span>
      </footer>
    </article>
  );
}
