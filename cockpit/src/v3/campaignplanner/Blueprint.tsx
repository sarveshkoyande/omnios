import { useState } from "react";
import { Icon } from "../../components/Icon";
import type { Blueprint as BlueprintT, Deployment, SalesforceStatus } from "./api";
import { MermaidView } from "./MermaidView";
import { list, txt } from "./util";

/** Camille's step line: "Step N: [If condition] action (delay)", where the action may come back
 *  as a string, a list, or an object. */
function stepLine(step: unknown, i: number): string {
  if (typeof step !== "object" || step === null) return `Step ${i + 1}: ${txt(step)}`;
  const s = step as Record<string, unknown>;
  const a = s.action;
  let action = "";
  if (typeof a === "string") action = a;
  else if (Array.isArray(a)) action = a.map((x) => (typeof x === "string" ? x : Object.values(x ?? {}).filter(Boolean).join(" | "))).join(", ");
  else if (a && typeof a === "object") action = Object.entries(a as Record<string, unknown>).filter(([, v]) => v).map(([k, v]) => `${k}: ${txt(v)}`).join(" | ");
  const cond = txt(s.condition);
  const delay = txt(s.delay);
  return `Step ${txt(s.sequence) || i + 1}: ${cond && !/^if applicable$/i.test(cond) ? `[If ${cond}] ` : ""}${action}${delay ? ` (${delay})` : ""}`;
}

function Source({ of, sources }: { of: string; sources: Record<string, string> }) {
  return sources[of] === "rules" ? <em className="v3-cc-src rules" title="Built by rules: the model wasn't available for this step">Rules</em> : null;
}

function Section({ icon, title, children, extra }: { icon: Parameters<typeof Icon>[0]["name"]; title: string; children: React.ReactNode; extra?: React.ReactNode }) {
  return (
    <section className="v3-cc-bp-sec">
      <div className="v3-cc-bp-sec-head"><span><Icon name={icon} size={14} /></span><b>{title}</b>{extra}</div>
      {children}
    </section>
  );
}

function Bullets({ items, tone }: { items: unknown[]; tone?: string }) {
  const clean = items.map(txt).filter(Boolean);
  if (!clean.length) return null;
  return <ul className={`v3-cc-bp-list ${tone ?? ""}`}>{clean.map((t, i) => <li key={i}>{t}</li>)}</ul>;
}

/** "functionalRequirements" / "open_questions" -> "Functional requirements" / "Open questions". */
function heading(key: string): string {
  const words = key.replace(/[_-]+/g, " ").replace(/([a-z0-9])([A-Z])/g, "$1 $2").trim().toLowerCase();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** Whatever else an agent returned beyond the fields its prompt asks for (a model often adds
 *  sections, e.g. the Technical Writer's requirements and data model), so none of it is hidden. */
function ExtraFields({ data, shown }: { data: Record<string, unknown>; shown: string[] }) {
  const rest = Object.entries(data ?? {}).filter(([k, v]) => !shown.includes(k) && txt(v));
  return (
    <>
      {rest.map(([k, v]) => (
        <div key={k}>
          <h4>{heading(k)}</h4>
          {Array.isArray(v) ? <Bullets items={v} />
            : v && typeof v === "object" ? <Bullets items={Object.entries(v as Record<string, unknown>).map(([ik, iv]) => (txt(iv) ? `${heading(ik)}: ${txt(iv)}` : ""))} />
            : <p>{txt(v)}</p>}
        </div>
      ))}
    </>
  );
}

export function DeployPanel({ canDeploy, deploying, deployment, sf, packageUrl, onDeploy, onConnect, onDisconnect }: {
  canDeploy: boolean;
  deploying: boolean;
  deployment: Deployment | null;
  sf: SalesforceStatus | null;
  packageUrl: string;
  onDeploy: () => void;
  onConnect: () => void;
  onDisconnect: () => void;
}) {
  const connected = Boolean(sf?.connected);
  return (
    <section className="v3-cc-bp-sec v3-cc-deploy">
      <div className="v3-cc-bp-sec-head"><span><Icon name="zap" size={14} /></span><b>Deployment</b></div>
      <div className="v3-cc-sf">
        {connected ? (
          <>
            <span className="v3-cc-sf-dot on" />
            <span>Connected to Salesforce{sf?.user?.display_name ? ` as ${sf.user.display_name}` : ""}{sf?.instance_url ? ` · ${sf.instance_url.replace(/^https?:\/\//, "")}` : ""}</span>
            <button type="button" className="v3-link" onClick={onDisconnect}>Disconnect</button>
          </>
        ) : sf?.configured ? (
          <>
            <span className="v3-cc-sf-dot" />
            <span>No Salesforce org connected. Connect one to deploy the flow (the agents then map onto your org's own objects).</span>
            <button type="button" className="v3-cc-btn" onClick={onConnect}>Connect Salesforce org</button>
          </>
        ) : (
          <>
            <span className="v3-cc-sf-dot" />
            <span>Salesforce isn't configured on this server, so the flow can't be pushed from here. Download the Flow package and deploy it with the Salesforce CLI or Workbench.</span>
          </>
        )}
      </div>
      <div className="v3-cc-card-actions left">
        <button type="button" className="v3-cc-btn primary" disabled={!canDeploy || !connected || deploying} onClick={onDeploy}>
          {deploying ? "Deploying…" : "Approve & Deploy"}
        </button>
        <a className="v3-cc-btn" href={packageUrl}>Download Flow package (.zip)</a>
      </div>
      {deployment && (
        <div className="v3-cc-timeline">
          <b>Deployment progress</b>
          {deployment.steps.map((s, i) => (
            <div key={i} className={`v3-cc-tl-step ${s.status}`}>
              <span className="v3-cc-tl-dot">{s.status === "complete" ? <Icon name="check" size={10} /> : s.status === "error" ? "!" : ""}</span>
              <div><b>{s.title}</b><span>{s.details}</span></div>
            </div>
          ))}
          {deployment.flow_url && (
            <a className="v3-cc-btn" href={deployment.flow_url} target="_blank" rel="noopener noreferrer">
              <Icon name="link" size={13} /> View Flow in Salesforce
            </a>
          )}
        </div>
      )}
    </section>
  );
}

export function Blueprint({ bp, stale, onRegenerate, deploy }: {
  bp: BlueprintT;
  stale: boolean;
  onRegenerate: () => void;
  deploy: React.ReactNode;
}) {
  const [specOpen, setSpecOpen] = useState(false);
  const ps = bp.planningSummary ?? {};
  const td = bp.technicalDesign ?? {};
  const qa = bp.flowQaReport ?? {};
  const val = bp.validation ?? {};
  const docs = bp.documentation ?? {};
  const spec = bp.spec ?? {};
  const sources = bp.sources ?? {};
  const paths = list(spec.scheduledPaths) as Record<string, unknown>[];
  const valid = val.isValid === true || String(val.isValid).toLowerCase() === "true";

  return (
    <div className="v3-cc-bp">
      <header className="v3-cc-bp-head">
        <div><span className="v3-cc-eyebrow">Generated specification</span><h1>Campaign Blueprint</h1></div>
        <span className="v3-cc-chip ok">Ready for review</span>
      </header>
      <p className="v3-cc-bp-meta">
        {bp.engine} · {bp.metadataSource === "org" ? `mapped onto your org's objects (${bp.metadataObjects.length})` : "mapped onto the standard Salesforce objects"}
        {bp.tokenUsage?.totalTokens ? ` · ${bp.tokenUsage.totalTokens.toLocaleString()} tokens` : ""}
        {bp.briefingVersion ? ` · from briefing v${bp.briefingVersion}` : ""}
      </p>
      {stale && (
        <div className="v3-cc-banner warn">
          The Campaign Briefing Document changed after this journey was generated.
          <button type="button" className="v3-link" onClick={onRegenerate}>Regenerate the journey</button>
        </div>
      )}

      <Section icon="route" title="Solution Plan" extra={<Source of="Document Analyst" sources={sources} />}>
        {txt(ps.businessGoal) && <p>{txt(ps.businessGoal)}</p>}
        {txt(ps.targetAudience) && <><h4>Target Audience</h4><p>{txt(ps.targetAudience)}</p></>}
        {txt(ps.triggerConcept) && <><h4>Trigger Concept</h4><p>{txt(ps.triggerConcept)}</p></>}
        {list(ps.steps).length > 0 && <><h4>Expected Steps</h4><ul className="v3-cc-bp-list">{list(ps.steps).map((s, i) => <li key={i}>{stepLine(s, i)}</li>)}</ul></>}
        {list(ps.ambiguities).length > 0 && <><h4 className="warn">Noted Ambiguities</h4><Bullets items={list(ps.ambiguities)} tone="warn" /></>}
        <ExtraFields data={ps} shown={["businessGoal", "targetAudience", "triggerConcept", "steps", "ambiguities"]} />
      </Section>

      <Section icon="layers" title="Technical Solution Design" extra={<Source of="Salesforce Architect" sources={sources} />}>
        {txt(td.rationale) && <div className="v3-cc-callout"><b>Salesforce architecture rationale:</b> {txt(td.rationale)}</div>}
        <div className="v3-cc-facts">
          <span><b>Flow type</b>{txt(spec.flowType) || "RecordTriggered"}</span>
          <span><b>Trigger</b>{txt(spec.triggerEvent) || "CreateAndUpdate"} on {txt(spec.triggerObject) || "Contact"}</span>
          <span><b>Run immediately</b>{list(spec.immediateElements).length} element{list(spec.immediateElements).length === 1 ? "" : "s"}</span>
          <span><b>Scheduled paths</b>{paths.length}</span>
          {Object.entries(bp.specSummary?.elements ?? {}).map(([k, n]) => <span key={k}><b>{k}</b>{n}</span>)}
        </div>
        {paths.length > 0 && (
          <ul className="v3-cc-bp-list">
            {paths.map((p, i) => <li key={i}><b>{txt(p.label) || `Scheduled path ${i + 1}`}</b> — after {txt(p.duration)} {txt(p.unit)} · {list(p.elements).length} element(s)</li>)}
          </ul>
        )}
        <button type="button" className="v3-link" onClick={() => setSpecOpen((o) => !o)}>{specOpen ? "Hide" : "View"} the flow specification (JSON)</button>
        {specOpen && <pre className="v3-cc-code">{JSON.stringify(spec, null, 2)}</pre>}
      </Section>

      <Section icon="flask" title="Flow QA Report" extra={<Source of="Flow QA Tester" sources={sources} />}>
        <div className="v3-cc-facts">
          <span><b>Status</b>{txt(qa.status) || "—"}</span>
          {qa.journeyCoveragePercent !== undefined && <span><b>Journey coverage</b>{txt(qa.journeyCoveragePercent)}%</span>}
        </div>
        {list(qa.testsExecuted).length > 0 && <><h4>Tests executed</h4><Bullets items={list(qa.testsExecuted)} /></>}
        {list(qa.fixesApplied).length > 0 && <><h4>Fixes applied</h4><Bullets items={list(qa.fixesApplied)} /></>}
        <ExtraFields data={qa} shown={["status", "journeyCoveragePercent", "testsExecuted", "fixesApplied"]} />
      </Section>

      <Section icon="shield" title="Validation" extra={<Source of="Flow Validator" sources={sources} />}>
        <div className="v3-cc-facts"><span><b>Result</b>{valid ? "Passed" : "Warnings found"}</span></div>
        {list(val.warnings).length > 0 && <><h4 className="warn">Warnings</h4><Bullets items={list(val.warnings)} tone="warn" /></>}
        {list(val.recommendations).length > 0 && <><h4>Recommendations</h4><Bullets items={list(val.recommendations)} /></>}
        <ExtraFields data={val} shown={["isValid", "warnings", "recommendations"]} />
      </Section>

      <Section icon="document" title="Technical Design Documentation" extra={<Source of="Technical Writer" sources={sources} />}>
        {txt(docs.executiveSummary) && <><h4>Executive summary</h4><p>{txt(docs.executiveSummary)}</p></>}
        {txt(docs.architectureDecision) && <><h4>Architecture decision</h4><p>{txt(docs.architectureDecision)}</p></>}
        {list(docs.testingStrategy).length > 0 && <><h4>Testing strategy</h4><Bullets items={list(docs.testingStrategy)} /></>}
        <ExtraFields data={docs} shown={["executiveSummary", "architectureDecision", "testingStrategy"]} />
      </Section>

      <Section icon="branch" title="Journey Flow" extra={<Source of="Visual Designer" sources={sources} />}>
        {bp.mermaid ? <MermaidView code={bp.mermaid} /> : <p className="v3-muted">No diagram was produced.</p>}
      </Section>

      {deploy}
    </div>
  );
}
