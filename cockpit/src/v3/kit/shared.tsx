import { createContext, useContext, useEffect, useState } from "react";
import { getBrandKit, proposeKitContent, regenerateBigIdea, runBrandIqSkill } from "../../api";
import { Icon } from "../../components/Icon";
import "../iq.css";
import "./kit.css";

/** Shared pieces of the Brand Kit tabs (docs/redesign/brand-kit-reorg.md). Every tab is a context
 *  page: the brief and what it means for campaigns first, then the evidence, then one "Still needed"
 *  box. Sections are declared once in SECTIONS (title, icon, the kit keys they read, the Brand Compass skill
 *  that can draft them), which drives the section index, the source badges, "Still needed" and the
 *  completeness strip on the Brand Compass tab. */

export type Any = Record<string, unknown>;
export type IconName = Parameters<typeof Icon>[0]["name"];
export const txt = (v: unknown) => (v === null || v === undefined ? "" : String(v));
export const arr = (v: unknown) => (Array.isArray(v) ? (v as Any[]) : []);
export const needs = (v: unknown) => !v || (Array.isArray(v) && !v.length) || (typeof v === "string" && v.startsWith("Needs input"));
export const SI_TONE: Record<string, string> = { FIND: "find", TREAT: "treat", MAINTAIN: "maintain" };

/** A value at a dotted path ("personas.hcp"). */
export function at(kit: Any | null | undefined, path: string): unknown {
  let v: unknown = kit;
  for (const part of path.split(".")) v = v && typeof v === "object" ? (v as Any)[part] : undefined;
  return v;
}
/** Empty, a "Needs input" placeholder, or a container whose parts are all empty. */
export function emptyDeep(v: unknown): boolean {
  if (v && typeof v === "object" && !Array.isArray(v)) return Object.values(v as Any).every(emptyDeep);
  return needs(v);
}

/* ------------------------------------------------------------------ tabs and sections */
export type TabId = "brandiq" | "market" | "audiences" | "message" | "channels" | "product" | "compliance";
export const TABS: { id: TabId; route: string; title: string; question: string; icon: IconName }[] = [
  { id: "brandiq", route: "iq/kits", title: "Brand Compass", question: "The brand on a page", icon: "document" },
  { id: "market", route: "iq/market", title: "Market", question: "Where are we winning and losing, and where is the headroom?", icon: "radar" },
  { id: "audiences", route: "iq/personas", title: "Audiences", question: "Who are we talking to, and what moves them?", icon: "persona" },
  // REMOVED 2026-10-07 (kept for reference): Message & Voice tab.
  // { id: "message", route: "iq/message", title: "Message & Voice", question: "What do we say, and how?", icon: "message" },
  { id: "channels", route: "iq/channels", title: "Channels", question: "Where and when do we reach them?", icon: "mail" },
  { id: "product", route: "iq/product", title: "Product & Proof", question: "What can we claim, and what backs it?", icon: "flask" },
  { id: "compliance", route: "iq/guardrails", title: "Compliance", question: "What must every campaign respect?", icon: "shield" },
];

type Spec = string[] | "sop" | "synthetic" | "framework";
type SectionDef = { tab: TabId; title: string; icon: IconName; keys: Spec; skill?: string };
export const SECTIONS: Record<string, SectionDef> = {
  unmet: { tab: "brandiq", title: "Unmet need", icon: "alertTriangle", keys: ["unmet_need"], skill: "voice" },
  // REMOVED 2026-10-07 (kept for reference): Key objectives and Current plan on the Brand Compass tab.
  // objectives: { tab: "brandiq", title: "Key objectives", icon: "target", keys: ["key_objectives", "key_objective"] },
  // plan: { tab: "brandiq", title: "Current plan", icon: "map", keys: ["strategic_imperatives"] },

  situation: { tab: "market", title: "Brand situation", icon: "radar", keys: ["brand_situation"] },
  flow: { tab: "market", title: "Where patients drop off", icon: "route", keys: ["patient_flow"] },
  geo: { tab: "market", title: "Where to focus in the US", icon: "map", keys: ["us_geography.layers"], skill: "us_geography" },
  competition: { tab: "market", title: "Competition", icon: "scale", keys: ["competitors", "competition_self"], skill: "competition" },
  access: { tab: "market", title: "Market access", icon: "wallet", keys: ["market_access"] },
  forecast: { tab: "market", title: "Sales forecast", icon: "barChart", keys: ["forecast.sales_meur"] },
  growth: { tab: "market", title: "Where growth comes from", icon: "layers", keys: ["growth_opportunities"] },
  kpis: { tab: "market", title: "KPIs", icon: "target", keys: ["kpis", "market_share", "success_measure"] },
  clientdata: { tab: "market", title: "Client data", icon: "users", keys: "synthetic" },
  proof: { tab: "market", title: "What has worked", icon: "star", keys: ["proof_points"] },

  segments: { tab: "audiences", title: "Audience segments", icon: "users", keys: ["audience_segments"] },
  hcp: { tab: "audiences", title: "Healthcare professionals", icon: "users", keys: ["personas.hcp"], skill: "personas" },
  patients: { tab: "audiences", title: "Patients and caregivers", icon: "heartPulse", keys: ["personas.patient", "personas.caregiver"], skill: "personas" },
  journey: { tab: "audiences", title: "Patient journey", icon: "route", keys: ["care_continuum.stages"], skill: "personas" },
  kols: { tab: "audiences", title: "Who shapes opinion", icon: "star", keys: ["audience_intel.kol_publications.value.authors"], skill: "audience_intel" },
  treaters: { tab: "audiences", title: "Where the treaters are", icon: "map", keys: ["audience_intel.trial_footprint.value"], skill: "audience_intel" },
  education: { tab: "audiences", title: "Patient education", icon: "document", keys: ["audience_intel.patient_resources.value"], skill: "audience_intel" },

  // REMOVED 2026-10-07 (kept for reference): Message & Voice sections.
  // positioning: { tab: "message", title: "Positioning", icon: "sparkles", keys: ["positioning_statement", "core_claim"], skill: "evidence" },
  // bigidea: { tab: "message", title: "Big Idea", icon: "sparkles", keys: ["tagline"], skill: "big_idea" },
  // matrix: { tab: "message", title: "Message matrix", icon: "layers", keys: ["message_hierarchy"], skill: "evidence" },
  // bypersona: { tab: "message", title: "Messages by audience", icon: "message", keys: ["messages_by_persona"], skill: "personas" },
  // voice: { tab: "message", title: "Voice & tone", icon: "mic", keys: ["voice", "tone_pillars"], skill: "voice" },
  // words: { tab: "message", title: "Words to use and avoid", icon: "message", keys: ["voice.vocabulary", "voice.avoid", "voice_do", "voice_dont"], skill: "voice" },

  chstrategy: { tab: "channels", title: "Channel strategy", icon: "route", keys: ["channels.brief"], skill: "channels" },
  chladder: { tab: "channels", title: "Channel jobs by adoption stage", icon: "trendUp", keys: "framework" },
  chmix: { tab: "channels", title: "Channel mix by audience", icon: "layers", keys: ["channels.mix"], skill: "channels" },
  chplaybook: { tab: "channels", title: "Channel playbook", icon: "megaphone", keys: "framework" },
  chlife: { tab: "channels", title: "Mix by lifecycle stage", icon: "barChart", keys: "framework" },
  chjourney: { tab: "channels", title: "Journey × channel", icon: "route", keys: ["channels.journey"], skill: "channels" },
  moments: { tab: "channels", title: "Key moments", icon: "calendar", keys: ["channels.moments"], skill: "channels" },
  activities: { tab: "channels", title: "What the plan commits to", icon: "check", keys: ["activities"] },
  chorch: { tab: "channels", title: "Orchestration rules", icon: "branch", keys: "framework" },
  chmeasure: { tab: "channels", title: "How to measure", icon: "target", keys: "framework" },

  profile: { tab: "product", title: "Product profile", icon: "flask", keys: ["product_profile"], skill: "label" },
  indications: { tab: "product", title: "Indications", icon: "document", keys: ["indications"] },
  label: { tab: "product", title: "Label & safety", icon: "shield", keys: ["approved_indication", "safety_reference", "product_profile.warnings.value"], skill: "label" },
  clinical: { tab: "product", title: "Clinical evidence", icon: "flask", keys: ["clinical_data"], skill: "evidence" },
  references: { tab: "product", title: "References", icon: "link", keys: ["references"], skill: "evidence" },

  dodont: { tab: "compliance", title: "Do and don't", icon: "check", keys: ["guardrails.dos", "guardrails.donts"], skill: "voice" },
  claimcheck: { tab: "compliance", title: "Claim check", icon: "shield", keys: ["compliance_check.claim_checks"], skill: "compliance" },
  cmpclaims: { tab: "compliance", title: "Claims & fair balance", icon: "scale", keys: "framework" },
  cmpchannels: { tab: "compliance", title: "Rules by channel", icon: "megaphone", keys: "framework" },
  cmpcycle: { tab: "compliance", title: "Review cycle", icon: "branch", keys: "framework" },
  approval: { tab: "compliance", title: "Approval workflow", icon: "branch", keys: "sop" },
  prelaunch: { tab: "compliance", title: "Pre-launch checklist", icon: "check", keys: "sop" },
  sops: { tab: "compliance", title: "Campaign SOPs", icon: "document", keys: "sop" },
  eligibility: { tab: "compliance", title: "Eligibility & suppressions", icon: "users", keys: "sop" },
  chrules: { tab: "compliance", title: "Channel rules", icon: "mail", keys: "sop" },
  cmpdata: { tab: "compliance", title: "Data, privacy & consent", icon: "eye", keys: "framework" },
  cmpae: { tab: "compliance", title: "Adverse events", icon: "alertTriangle", keys: "framework" },
  regs: { tab: "compliance", title: "Regulations", icon: "scale", keys: "framework" },
};
export const sectionsOf = (tab: TabId) => Object.entries(SECTIONS).filter(([, d]) => d.tab === tab);
export function filled(kit: Any | null, keys: Spec): boolean {
  if (typeof keys === "string") return true;
  return keys.some((k) => !emptyDeep(at(kit, k)));
}

/* ------------------------------------------------------------------ kit loading */
const planKey = (brand: string) => `omni-v3-plan-${brand}`;

export function useKit(activeBrand: string | null, brands: { brand: string }[]) {
  const brand = activeBrand ?? brands[0]?.brand ?? null;
  const [raw, setRaw] = useState<Any | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [planId, setPlanIdState] = useState<string | null>(null);
  useEffect(() => {
    if (!brand) return;
    setRaw(null); setError(null);
    try { setPlanIdState(localStorage.getItem(planKey(brand))); } catch { setPlanIdState(null); }
    getBrandKit(brand).then((r) => setRaw(r.kit as unknown as Any)).catch((e) => setError(String(e)));
  }, [brand]);
  const setPlanId = (id: string) => {
    setPlanIdState(id);
    try { if (brand) localStorage.setItem(planKey(brand), id); } catch { /* storage unavailable */ }
  };
  const plans = arr(raw?.plans);
  const plan = plans.find((x) => x.id === planId) ?? plans.find((x) => x.id === raw?.active_plan) ?? plans[0] ?? null;
  // Pages read plan content as if it were on the kit; kits without plans keep their flat fields.
  const kit = raw ? ({ ...raw, ...(plan ?? {}), plan_meta: plan } as Any) : null;
  return { brand, kit, error, plans, plan, setPlanId, setRaw };
}
export type KitState = ReturnType<typeof useKit>;
export type PageProps = { activeBrand: string | null; brands: { brand: string }[] };

export const KitCtx = createContext<Any | null>(null);
const StateCtx = createContext<KitState | null>(null);
export const useKitState = () => useContext(StateCtx);

/** Runs one Brand Compass skill and swaps in the updated kit. */
function useSkill() {
  const p = useKitState();
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const run = (skill: string) => {
    if (!p?.brand) return;
    setBusy(skill); setErr(null);
    runBrandIqSkill(p.brand, skill).then((r) => p.setRaw(r.kit as unknown as Any))
      .catch((e) => setErr(e instanceof Error ? e.message : String(e))).finally(() => setBusy(null));
  };
  return { busy, err, run };
}

/* ------------------------------------------------------------------ source badges */
/* In priority order: 1 brand plan, 2 public data, 3 AI draft. When they disagree the brand plan wins
 * (AI drafts never overwrite brand-plan fields; public refreshes only write their own blocks). */
type Tier = "plan" | "public" | "ai" | "sop" | "synthetic" | "framework";
const PUBLIC_LABEL: Record<string, string> = {
  product_profile: "FDA · NIH", indications: "FDA label", patient_flow: "PubMed", us_geography: "CDC",
  audience_intel: "PubMed · ClinicalTrials.gov · MedlinePlus", competitors: "PubMed",
};
const PLAN_KEYS = new Set(["strategic_imperatives", "kpis", "forecast", "growth_opportunities", "activities", "proof_points", "market_share"]);
const TIER_RANK: Tier[] = ["plan", "sop", "public", "framework", "ai", "synthetic"];
const TIER_ICON: Record<Tier, IconName> = { plan: "document", sop: "shield", public: "search", ai: "sparkles", synthetic: "flask", framework: "lightbulb" };

function sectionSource(kit: Any | null, spec: Spec): { tier: Tier; label: string; title: string } | null {
  if (!kit) return null;
  if (spec === "sop") return { tier: "sop", label: "Company SOPs", title: "From the company's compliance profile" };
  if (spec === "synthetic") return { tier: "synthetic", label: "Synthetic", title: "A stand-in until real client data is connected" };
  if (spec === "framework") return { tier: "framework", label: "Best practice", title: "Omni's best-practice framework: guidance, not brand data. The brand plan wins." };
  const proposals = (kit.proposals ?? {}) as Record<string, Any>;
  const hasPlan = Boolean(kit.plan_meta) || arr(kit.plans).length > 0;
  const found: { tier: Tier; key: string }[] = [];
  for (const path of spec) {
    if (emptyDeep(at(kit, path))) continue;
    const k = path.split(".")[0];
    const pr = proposals[k];
    const own = kit[k] as Any | undefined;
    if (pr) found.push({ tier: txt(pr.engine).includes("brand_plan") ? "plan" : "ai", key: k });
    else if (own && typeof own === "object" && ["to_confirm", "proposed", "ai_generated"].includes(txt(own.status))) found.push({ tier: "ai", key: k });
    else if (PLAN_KEYS.has(k)) { if (hasPlan) found.push({ tier: "plan", key: k }); }
    else if (k in PUBLIC_LABEL) found.push({ tier: "public", key: k });
    else if (k === "tagline") found.push({ tier: "ai", key: k });
    else if (hasPlan) found.push({ tier: "plan", key: k });
  }
  if (!found.length) return null;
  const best = TIER_RANK.find((t) => found.some((f) => f.tier === t)) as Tier;
  const others = Array.from(new Set(found.map((f) => f.tier).filter((t) => t !== best)));
  const label = best === "plan" ? "Brand plan" : best === "ai" ? "AI draft · confirm"
    : Array.from(new Set(found.filter((f) => f.tier === "public").map((f) => PUBLIC_LABEL[f.key]))).join(" · ");
  const why = best === "plan" ? "From the brand plan (priority 1)" : best === "public" ? "From public sources (priority 2)" : "Drafted by Omni (priority 3) — confirm before use";
  return { tier: best, label, title: others.length ? `${why}. Also: ${others.map((t) => (t === "ai" ? "AI draft" : t === "public" ? "public data" : t)).join(", ")}.` : why };
}

function SourceBadge({ spec }: { spec: Spec }) {
  const src = sectionSource(useContext(KitCtx), spec);
  if (!src) return null;
  return <span className={`v3-iq-srcbadge ${src.tier}`} title={src.title}><Icon name={TIER_ICON[src.tier]} size={11} />{src.label}</span>;
}

function SourceLegend() {
  return (
    <div className="v3-iq-legend">
      <span className="v3-iq-srcbadge plan"><Icon name="document" size={11} />1 · Brand plan</span>
      <span className="v3-iq-srcbadge public"><Icon name="search" size={11} />2 · Public data</span>
      <span className="v3-iq-srcbadge ai"><Icon name="sparkles" size={11} />3 · AI draft</span>
      <small>The brand plan wins when sources disagree</small>
    </div>
  );
}

/* ------------------------------------------------------------------ small pieces */
/** A value that isn't captured yet, inside a filled section (whole empty sections go to "Still needed"). */
export const Needs = ({ what }: { what?: string }) => <span className="v3-iq-none" title={what ? `Not captured yet: ${what}` : "Not captured yet"}>Not captured</span>;
export const Src = ({ s }: { s: unknown }) => (s ? <small className="v3-iq-src">{txt(s)}</small> : null);
export const SiTag = ({ id }: { id: unknown }) => <span className={`v3-iq-si v3-iq-si-${SI_TONE[txt(id)] ?? "other"}`}>{txt(id)}</span>;

/** A field label with its icon, so every template reads the same way. */
export const Lbl = ({ icon, children }: { icon: IconName; children: React.ReactNode }) => (
  <em className="v3-iq-lbl"><Icon name={icon} size={12} />{children}</em>
);

/** The sources of a list's rows, once, for the section footer. */
export function sourcesOf(rows: Any[], key = "source"): string {
  const all = Array.from(new Set(rows.map((r) => txt(r[key])).filter(Boolean)));
  return all.length > 3 ? `${all.slice(0, 3).join(" · ")} · +${all.length - 3} more` : all.join(" · ");
}

/** Bullets: strings, or {lead, text} with the lead in bold. */
export function Bul({ items, max }: { items: unknown[]; max?: number }) {
  const [all, setAll] = useState(false);
  const list = items.filter(Boolean);
  if (!list.length) return null;
  const shown = max && !all ? list.slice(0, max) : list;
  return (<>
    <ul className="v3-iq-bul">
      {shown.map((b, i) => typeof b === "object"
        ? <li key={i}>{txt((b as Any).lead) && <b>{txt((b as Any).lead)}</b>} {txt((b as Any).text)}</li>
        : <li key={i}>{txt(b)}</li>)}
    </ul>
    {max && list.length > max && <button type="button" className="v3-iq-more" onClick={() => setAll((a) => !a)}>{all ? "Show fewer" : `+${list.length - max} more`}</button>}
  </>);
}

/** Long text as key-point bullets (the `digest` skill, kit.bullets[path]); the original one click away. */
export function Digest({ path, text, source }: { path: string; text: unknown; source?: React.ReactNode }) {
  const kit = useContext(KitCtx);
  const [open, setOpen] = useState(false);
  const s = txt(text);
  if (!s) return <Needs />;
  const b = arr(((kit?.bullets ?? {}) as Any)[path]);
  if (b.length) return (<>
    <Bul items={b} />
    <button type="button" className="v3-iq-more" onClick={() => setOpen((o) => !o)}>{open ? "Hide full text" : "Full text"}</button>
    {open && <p className="v3-iq-label-text v3-iq-fulltext">{s}</p>}
    {source}
  </>);
  const long = s.length > 320;
  return (<>
    <p className="v3-iq-label-text">{long && !open ? `${s.slice(0, 320)}…` : s}</p>
    {long && <button type="button" className="v3-iq-more" onClick={() => setOpen((o) => !o)}>{open ? "Show less" : "Show more"}</button>}
    {source}
  </>);
}

/** An FDA label section, digested, with its link. */
export function LabelText({ k, field }: { k: Any; field: string }) {
  const f = ((k.product_profile ?? {}) as Record<string, Any>)[field];
  if (!f || !f.value) return <Needs />;
  return <Digest path={`product_profile.${field}.value`} text={f.value}
    source={<a className="v3-iq-src" href={txt(f.url)} target="_blank" rel="noreferrer">{txt(f.source)} · fetched {txt(f.fetched_at)} ↗</a>} />;
}

/** A plain table over records. Long cells read as bullets when they hold a list. */
export function Tbl({ rows, cols }: { rows: Any[]; cols: [string, string][] }) {
  if (!rows.length) return <Needs />;
  return (
    <div className="v3-iq-tablewrap">
      <table className="v3-iq-table">
        <thead><tr>{cols.map(([, l]) => <th key={l}>{l}</th>)}</tr></thead>
        <tbody>{rows.map((r, i) => (
          <tr key={i}>{cols.map(([c]) => (
            <td key={c}>{Array.isArray(r[c]) ? <Bul items={r[c] as unknown[]} /> : txt(r[c]) || <Needs />}</td>
          ))}</tr>
        ))}</tbody>
      </table>
    </div>
  );
}

/** One section of a tab. Renders only when the kit has content for it (empty ones are listed in
 *  "Still needed"); `children` is a function so nothing is computed for an empty section. */
export function Sec({ id, sub, action, foot, children, wide }: {
  id: string; sub?: string; action?: React.ReactNode; foot?: React.ReactNode; children: () => React.ReactNode; wide?: boolean;
}) {
  const kit = useContext(KitCtx);
  const def = SECTIONS[id];
  if (!def || !filled(kit, def.keys)) return null;
  return (
    <section id={`iq-sec-${id}`} className={`v3-iq-block${wide === false ? " half" : ""}`}>
      <h2><span className="v3-iq-h-icon"><Icon name={def.icon} size={15} /></span>{def.title}<SourceBadge spec={def.keys} />
        {sub && <span className="v3-iq-h-sub">{sub}</span>}{action && <div className="v3-iq-block-act">{action}</div>}</h2>
      {children()}
      {foot ? <footer className="v3-iq-foot">{foot}</footer> : null}
    </section>
  );
}

/* ------------------------------------------------------------------ the tab frame */
function PlanSwitcher({ p }: { p: KitState }) {
  if (!p.plans.length) return null;
  return (
    <label className="v3-iq-plan">
      <span>Plan</span>
      <select value={txt(p.plan?.id)} onChange={(e) => p.setPlanId(e.target.value)}>
        {p.plans.map((x) => <option key={txt(x.id)} value={txt(x.id)}>{txt(x.name)}</option>)}
      </select>
    </label>
  );
}

/** Says how many sections are AI drafts (brands without an uploaded plan), and drafts the rest. */
function ProposalBar({ p }: { p: KitState }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const proposals = (p.kit?.proposals ?? {}) as Record<string, unknown>;
  const ai = Object.values(proposals).filter((v) => !txt((v as Any)?.engine).includes("brand_plan")).length;
  const hasPlan = arr(p.kit?.plans).length > 0;
  if (hasPlan && !ai) return null;
  const run = () => {
    if (!p.brand) return;
    setBusy(true); setErr(null);
    proposeKitContent(p.brand).then((r) => p.setRaw(r.kit as unknown as Any)).catch((e) => setErr(String(e))).finally(() => setBusy(false));
  };
  return (
    <div className="v3-iq-banner warn v3-iq-propbar">
      <span>{ai ? <><b>{ai} AI-drafted sections</b> to confirm — marked ✨ AI draft.</> : <><b>No brand plan yet.</b> Omni can draft the empty sections from public evidence.</>}</span>
      <button type="button" className="v3-iq-btn" disabled={busy} onClick={run}>{busy ? "Drafting…" : ai ? "Fill remaining gaps" : "Propose missing content"}</button>
      {err && <small>{err}</small>}
    </div>
  );
}

/** The brief and what it means for campaigns (the `context` skill, kit.context.tabs[tab]). */
/** REMOVED 2026-10-07 (kept for reference): not shown anywhere now; the `context` skill still feeds the on-a-page tiles. */
export function ContextBrief({ tab }: { tab: TabId }) {
  const kit = useContext(KitCtx);
  const sk = useSkill();
  const ctx = (kit?.context ?? {}) as Any;
  const c = ((ctx.tabs ?? {}) as Record<string, Any>)[tab];
  if (!c) return (
    <div className="v3-iq-brief empty">
      <span><Icon name="sparkles" size={13} /> No brief yet. Omni can write one from what the kit holds.</span>
      <button type="button" className="v3-iq-btn" disabled={Boolean(sk.busy)} onClick={() => sk.run("context")}>{sk.busy ? "Writing…" : "Write the brief"}</button>
      {sk.err && <small className="v3-iq-err">{sk.err}</small>}
    </div>
  );
  const impl = arr(c.implications);
  return (
    <section className="v3-iq-brief">
      <div className="v3-iq-brief-col">
        <em>The brief</em>
        <Bul items={arr(c.brief)} />
      </div>
      {impl.length > 0 && (
        <div className="v3-iq-brief-col">
          <em>What it means for campaigns</em>
          <ul className="v3-iq-impl">
            {impl.map((x, i) => (
              <li key={i} className={txt(x.kind) === "watch" ? "watch" : "do"}>
                <span className="k">{txt(x.kind) === "watch" ? "Watch" : "Do"}</span>
                <span>{txt(x.text)}{txt(x.cites) && <small> · {txt(x.cites)}</small>}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <footer>
        <span className="v3-iq-srcbadge ai" title="Written by Omni from this kit; the brand plan wins where sources disagree"><Icon name="sparkles" size={11} />AI summary</span>
        <span>{txt(ctx.generated_at)}</span>
        <button type="button" className="v3-iq-more" disabled={Boolean(sk.busy)} onClick={() => sk.run("context")}>{sk.busy ? "Rewriting…" : "Rewrite"}</button>
        {sk.err && <small className="v3-iq-err">{sk.err}</small>}
      </footer>
    </section>
  );
}

function SectionIndex({ tab }: { tab: TabId }) {
  const kit = useContext(KitCtx);
  const secs = sectionsOf(tab).filter(([, d]) => filled(kit, d.keys));
  if (secs.length < 3) return null;
  return (
    <nav className="v3-iq-secidx" aria-label="Sections on this tab">
      {secs.map(([id, d]) => (
        <button key={id} type="button" onClick={() => document.getElementById(`iq-sec-${id}`)?.scrollIntoView({ behavior: "smooth", block: "start" })}>{d.title}</button>
      ))}
    </nav>
  );
}

function StillNeeded({ tab }: { tab: TabId }) {
  const kit = useContext(KitCtx);
  const sk = useSkill();
  const missing = sectionsOf(tab).filter(([, d]) => !filled(kit, d.keys));
  if (!missing.length) return null;
  return (
    <section className="v3-iq-still">
      <h3>Still needed on this tab</h3>
      <ul>
        {missing.map(([id, d]) => (
          <li key={id}>
            <span>{d.title}</span>
            {d.skill
              ? <button type="button" className="v3-iq-more" disabled={Boolean(sk.busy)} onClick={() => sk.run(d.skill!)}>{sk.busy === d.skill ? "Drafting…" : "Draft it"}</button>
              : <a className="v3-iq-more" href="#/v3/agent/brand-iq">From the brand plan · Brand Compass Agent</a>}
          </li>
        ))}
      </ul>
      {sk.err && <small className="v3-iq-err">{sk.err}</small>}
    </section>
  );
}

export function Shell({ tab, p, children, extraHead }: { tab: TabId; p: KitState; children: (k: Any) => React.ReactNode; extraHead?: React.ReactNode }) {
  if (!p.brand) return <p className="v3-empty">No brands yet.</p>;
  const t = TABS.find((x) => x.id === tab)!;
  return (
    <div className="v3-iq">
      <header className="v3-iq-head">
        <span className="v3-iq-head-icon"><Icon name={t.icon} size={20} /></span>
        <div className="v3-iq-head-text">
          <h1 className="v3-page-title">{t.title}</h1>
          <p className="v3-page-sub">{t.question} · <b>{p.brand}</b></p>
        </div>
        {extraHead}
        <PlanSwitcher p={p} />
      </header>
      {p.error ? <p className="v3-empty">Couldn't load {p.brand}: {p.error}</p>
        : !p.kit ? <p className="v3-empty">Loading…</p> : (
          <StateCtx.Provider value={p}>
            <KitCtx.Provider value={p.kit}>
              {tab === "brandiq" && <SourceLegend />}
              {tab === "brandiq" && <ProposalBar p={p} />}
              {/* REMOVED 2026-10-07 (kept for reference): the brief at the top of the Brand Compass tab.
              {tab === "brandiq" && <ContextBrief tab={tab} />} */}
              <SectionIndex tab={tab} />
              {children(p.kit)}
              <StillNeeded tab={tab} />
            </KitCtx.Provider>
          </StateCtx.Provider>
        )}
    </div>
  );
}

/** The Big Idea: AI-generated by design, with its full reasoning and a Regenerate button. */
export function BigIdeaTile({ kit, p }: { kit: Any; p: KitState }) {
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const bi = (kit.big_idea ?? null) as Any | null;
  const regen = () => {
    if (!p.brand) return;
    setBusy(true); setErr(null);
    regenerateBigIdea(p.brand).then((r) => { p.setRaw(r.kit as unknown as Any); setOpen(true); }).catch((e) => setErr(String(e))).finally(() => setBusy(false));
  };
  return (
    <div className="v3-iq-bigidea">
      <div className="v3-iq-bigidea-top">
        <button type="button" className="v3-iq-more" disabled={busy} onClick={regen}>{busy ? "Generating…" : "Regenerate"}</button>
        {bi && <button type="button" className="v3-iq-more" onClick={() => setOpen((o) => !o)}>{open ? "Hide reasoning" : "Why this idea"}</button>}
      </div>
      <p className="v3-iq-bigidea-text">{txt(kit.tagline) || <Needs />}</p>
      {err && <small className="v3-iq-err">{err}</small>}
      {bi && open && (
        <div className="v3-iq-bigidea-why">
          {Boolean(bi.insight) && <p><b>Insight.</b> {txt(bi.insight)}</p>}
          {Boolean(bi.reasoning) && <p><b>Reasoning.</b> {txt(bi.reasoning)}</p>}
          {arr(bi.draws_on).length > 0 && (<><b>Draws on</b><ul>{arr(bi.draws_on).map((d, i) => <li key={i}>{txt(d.what)} <small className="v3-iq-src" style={{ display: "inline" }}>({txt(d.source)})</small></li>)}</ul></>)}
          {Boolean(bi.why_not_competitors) && <p><b>Versus competitors.</b> {txt(bi.why_not_competitors)}</p>}
          {arr(bi.alternatives).length > 0 && (<><b>Alternatives considered</b><ul>{arr(bi.alternatives).map((a, i) => <li key={i}>“{txt(a.idea)}” — {txt(a.why_not_chosen)}</li>)}</ul></>)}
          {Boolean((bi.fit_check as Any | undefined)?.notes) && <p><b>On-label check.</b> {txt((bi.fit_check as Any).notes)}</p>}
          {arr(bi.history).length > 0 && (<><b>Earlier versions</b><ul>{arr(bi.history).map((h, i) => <li key={i}>“{txt(h.text)}” <small className="v3-muted">{txt(h.generated_at)}</small></li>)}</ul></>)}
          <small className="v3-iq-src">Generated {txt(bi.generated_at)} by Omni from the positioning, personas, voice and evidence in this kit.</small>
        </div>
      )}
    </div>
  );
}

/** Two-segment control used by the Compliance tab. */
export function Seg({ options, value, onChange }: { options: string[]; value: string; onChange: (v: string) => void }) {
  return (
    <div className="v3-seg v3-iq-seg" role="tablist">
      {options.map((o) => <button key={o} type="button" role="tab" aria-selected={o === value} className={`v3-seg-tab ${o === value ? "active" : ""}`} onClick={() => onChange(o)}>{o}</button>)}
    </div>
  );
}
