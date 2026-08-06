/** Campaign Ops (2) — the derivation that everything on the stage reads from.
 *
 * Two passes, in this order, because the order is the whole point:
 *   1. **Requirement** — explode the plan into every deliverable it implies.
 *   2. **Coverage** — check each one against what already exists, and only then decide
 *      whether it is work.
 *
 * The current Stage 2 checklist skips pass 2 entirely: `orchestration_tasks.generate_tasks()`
 * emits "Prepare content for message: X" without ever consulting the content library, so it
 * always reads as if everything must be built from scratch. Here the library, the flow's own
 * `content_ref.ready` flags and the approved-claim count decide the answer.
 */
import type { CategoryId, CategoryMeta, Coverage, Deliverable, LaunchVerdict, Risk, RunStep } from "./types";
import type { PlanResult } from "../../types";

export const CATEGORIES: CategoryMeta[] = [
  { id: "creative", name: "Creative & Content", icon: "palette", team: "Content & derivative assets team" },
  { id: "digital", name: "Digital Properties", icon: "language", team: "Web team" },
  { id: "systems", name: "Systems & Tools", icon: "settings_input_component", team: "Campaign operations team" },
  { id: "data", name: "Data", icon: "storage", team: "Data & data cloud team" },
  { id: "approvals", name: "Approvals & Compliance", icon: "verified_user", team: "Regulatory & legal" },
  { id: "measurement", name: "Measurement", icon: "insights", team: "Reporting & insights team" },
  { id: "field", name: "Field Sales Enablement", icon: "badge", team: "Field operations" },
  { id: "qa", name: "Quality Assurance", icon: "bug_report", team: "Campaign operations team" },
  { id: "fulfilment", name: "Fulfilment", icon: "local_shipping", team: "Vendor / print" },
  { id: "access", name: "Access & Governance", icon: "admin_panel_settings", team: "Campaign operations team" },
];

export const CATEGORY_BY_ID: Record<CategoryId, CategoryMeta> = Object.fromEntries(
  CATEGORIES.map((c) => [c.id, c]),
) as Record<CategoryId, CategoryMeta>;

/** Coverage state colours — a functional four-state legend, deliberately not brand-token
 *  driven (same reasoning as planDocSkinCss.ts's phase legend, per CLAUDE.md). */
export const COVERAGE_STYLE: Record<Coverage, { label: string; color: string; bg: string }> = {
  reuse: { label: "Reuse", color: "#1B7A34", bg: "#E7F4EA" },
  adapt: { label: "Adapt", color: "#B4552F", bg: "#FDF1EC" },
  build: { label: "Build new", color: "#2451C4", bg: "#E8EEFB" },
  blocked: { label: "Blocked", color: "#A11F35", bg: "#FBEAED" },
};

/** Baseline effort per category, in business days, before coverage is applied. */
const BASE_EFFORT: Record<CategoryId, number> = {
  creative: 8, digital: 6, systems: 5, data: 4, approvals: 10,
  measurement: 3, field: 6, qa: 4, fulfilment: 7, access: 1,
};

/** Coverage multiplies the baseline — reuse is nearly free, adapt is roughly a third. */
const COVERAGE_FACTOR: Record<Coverage, number> = { reuse: 0.1, adapt: 0.35, build: 1, blocked: 1 };

const WEB_CHANNEL_HINTS = ["web", "portal", "ehr", "point-of-care", "landing", "site"];
const FIELD_CHANNEL_HINTS = ["rep", "field", "detail", "f2f", "face"];
const PRINT_CHANNEL_HINTS = ["print", "mail", "leave", "sample"];

const hits = (s: string | undefined, hints: string[]) =>
  !!s && hints.some((h) => s.toLowerCase().includes(h));

function effort(category: CategoryId, coverage: Coverage): number {
  return Math.max(1, Math.round(BASE_EFFORT[category] * COVERAGE_FACTOR[coverage]));
}

function review(category: CategoryId, coverage: Coverage): Deliverable["review"] {
  // Only content that reaches an HCP carries claims, so only that needs medical/legal review.
  if (category !== "creative" && category !== "digital" && category !== "field") return "none";
  if (coverage === "reuse") return "none";
  if (coverage === "adapt") return "abbreviated";
  return "full";
}

let seq = 0;
function make(
  category: CategoryId,
  title: string,
  source: string,
  coverage: Coverage,
  coverageReason: string,
  channel?: string,
): Deliverable {
  seq += 1;
  return {
    id: `d${seq}`,
    category,
    title,
    source,
    channel,
    coverage,
    coverageReason,
    review: review(category, coverage),
    effortDays: effort(category, coverage),
    owner: CATEGORY_BY_ID[category].team,
  };
}

/**
 * Pass 1 + 2. `result` is the Stage 1 plan; everything below reads from it and from the
 * content library it carries. Returns [] when there is no plan yet.
 */
export function deriveDeliverables(result: PlanResult | null): Deliverable[] {
  if (!result) return [];
  seq = 0;

  const plan = result.stage_3_campaign_plan;
  const lib = result.content_library;
  const assets = lib?.assets ?? [];
  const libraryFound = !!lib?.found && assets.length > 0;
  const approvedClaims = lib?.counts?.approved_claims ?? 0;
  const out: Deliverable[] = [];

  /** An asset in the library whose format plausibly serves this channel. */
  const assetFor = (channel?: string) => {
    if (!libraryFound || !channel) return undefined;
    const c = channel.toLowerCase();
    return assets.find((a) => {
      const f = (a.asset_format || "").toLowerCase();
      return f && (c.includes(f) || f.includes(c.split(" ")[0]));
    });
  };

  // ---- Touchpoints: the send/follow-up nodes of the finalised journey ----
  const nodes = (plan?.flow?.nodes ?? []).filter((n) => n.type === "send" || n.type === "followup");
  for (const node of nodes) {
    const channel = node.data.channel || plan?.overview?.primary_channel || "Email";
    const label = node.data.label || channel;
    const src = `Touchpoint · ${label}`;
    /** Nodes often carry the channel as their label too; don't say it twice. */
    const qualifier = label.toLowerCase() === channel.toLowerCase() ? "" : ` — ${label}`;

    // Creative — the flow already carries a readiness flag per touchpoint; use it.
    let coverage: Coverage;
    let reason: string;
    if (node.data.content_ref?.ready) {
      coverage = "reuse";
      reason = `The journey resolved this to an existing asset: "${node.data.content_ref.label}".`;
    } else if (assetFor(channel)) {
      coverage = "adapt";
      reason = `Library holds a ${assetFor(channel)!.asset_format} asset that can carry this message with a new rendition.`;
    } else if (!libraryFound) {
      coverage = "blocked";
      reason = "No content library is indexed for this brand, so nothing can be checked for reuse.";
    } else {
      coverage = "build";
      reason = `Nothing in the library serves ${channel} for this message.`;
    }
    out.push(make("creative", `${channel} asset${qualifier}`, src, coverage, reason, channel));

    // Systems — every touchpoint has to be built in the platform that sends it.
    out.push(make("systems", `Configure ${channel} send in the automation platform`, src, "build",
      "Journey configuration is campaign-specific; there is nothing to reuse.", channel));

    // Digital / field / fulfilment follow from the channel type.
    if (hits(channel, WEB_CHANNEL_HINTS)) {
      out.push(make("digital", `Landing page${qualifier || ` — ${channel}`}`, src, "build",
        "Web destinations are built per campaign.", channel));
    }
    if (hits(channel, FIELD_CHANNEL_HINTS)) {
      out.push(make("field", `CLM presentation${qualifier || ` — ${channel}`}`, src, "build",
        "Rep-facing material is built alongside the touchpoint it supports.", channel));
    }
    if (hits(channel, PRINT_CHANNEL_HINTS)) {
      out.push(make("fulfilment", `Print production & distribution${qualifier || ` — ${channel}`}`, src, "build",
        "Physical touchpoint: production and mail-house lead time applies.", channel));
    }

    // Measurement — one tagging line per touchpoint.
    out.push(make("measurement", `Link tagging & tracking — ${label}`, src, "build",
      "Tagging is unique per touchpoint and cannot be inherited.", channel));

    // Approvals — anything not reused has to clear review.
    if (coverage !== "reuse") {
      out.push(make("approvals", `MLR submission — ${label}`, src,
        approvedClaims > 0 ? "build" : "blocked",
        approvedClaims > 0
          ? `${approvedClaims} approved claims on record to draw from; the rendition still needs review.`
          : "No approved-claim records available, so the review path cannot be confirmed.",
        channel));
    }
  }

  // ---- Messages: each key message is copy that has to exist and be cleared ----
  for (const km of result.stage_2_4_message_flow?.key_messages ?? []) {
    if (!km.topic) continue;
    const src = `Key message · ${km.topic}`;
    out.push(make("creative", `Copy & claims — ${km.topic}`, src,
      approvedClaims > 0 ? "adapt" : "build",
      approvedClaims > 0
        ? "Approved claims exist for this brand; the copy is a new arrangement of them."
        : "No approved claims on record — copy is written from scratch and cleared in full.",
    ));
    out.push(make("approvals", `Claim approval & expiry check — ${km.topic}`, src,
      approvedClaims > 0 ? "adapt" : "blocked",
      approvedClaims > 0
        ? "Claim is on record; currency against the current label still has to be confirmed."
        : "No claim record to check against. This is the gap that blocks the whole coverage pass.",
    ));
  }

  // ---- Segments: each becomes a resolvable audience ----
  for (const seg of plan?.segments ?? []) {
    const src = `Segment · ${seg.name}`;
    const vol = seg.volume ? ` (~${seg.volume.toLocaleString()} HCPs)` : "";
    out.push(make("data", `Build audience list — ${seg.name}${vol}`, src,
      seg.volume_exact ? "adapt" : "build",
      seg.volume_exact
        ? "Counted against the real HCP panel, so the definition already resolves."
        : "Volume is an apportioned estimate — the segment has to be resolved against real records.",
    ));
  }

  // ---- Journey logic: entry criteria and decision splits ----
  for (const c of plan?.entry_criteria ?? []) {
    out.push(make("systems", `Implement entry criterion — ${c}`, "Journey logic", "build",
      "Entry rules are configured per campaign."));
  }
  for (const d of plan?.decision_logic_summary ?? []) {
    out.push(make("systems", `Configure decision split — ${d.condition}`, "Journey logic", "build",
      `Branches to: ${d.outcome}.`));
  }

  // ---- Channel platforms named by the plan ----
  for (const ch of result.stage_5_channel_selection?.channels ?? []) {
    out.push(make("systems", `Platform setup & connection — ${ch.channel}`, "Channel selection",
      ch.availability?.toLowerCase().includes("available") ? "reuse" : "build",
      ch.availability?.toLowerCase().includes("available")
        ? "Channel is already available to the brand; connection is a configuration check."
        : "Channel is not yet connected for this brand.",
      ch.channel));
  }

  // ---- Measurement from the KPI plan ----
  for (const ind of result.stage_7_kpi?.leading_indicators ?? []) {
    out.push(make("measurement", `Stand up tracking — ${ind}`, "KPI plan", "build",
      "Each leading indicator needs its own instrumentation."));
  }

  // ---- Campaign-wide lines that exist once regardless of journey shape ----
  const once: [CategoryId, string, Coverage, string][] = [
    ["data", "Opt-in / consent list verification", "adapt", "Consent records exist; they have to be re-verified for this campaign's channels."],
    ["data", "Exclusion & suppression list", "adapt", "Standing suppression rules exist and are extended for this campaign."],
    ["data", "HCP identity & NPI matching", "reuse", "Identity resolution is a standing capability, not campaign work."],
    ["data", "CRM sync & refresh schedule", "adapt", "Existing sync extended to cover this campaign's activity codes."],
    ["systems", "Project setup — TactPlan", "build", "One project record per campaign."],
    ["systems", "CRM configuration — D365", "adapt", "Existing CRM extended with this campaign's activities."],
    ["systems", "Work tracking setup — Jira", "build", "One board per campaign."],
    ["systems", "MLR routing configuration — VVPM", "reuse", "Standing routing rules apply unchanged."],
    ["measurement", "Dashboard wiring", "adapt", "Reporting stage reads a standard dashboard, extended per campaign."],
    ["measurement", "Attribution configuration", "adapt", "Existing model extended to this campaign's touchpoints."],
    ["qa", "Send testing with seed lists", "build", "Executed per campaign, against the real journey."],
    ["qa", "Link testing", "build", "Every destination verified before launch."],
    ["qa", "Journey logic UAT", "build", "Test records walked through every branch."],
    ["qa", "Render testing across clients", "build", "Per asset set, per campaign."],
    ["qa", "Deliverability & inbox placement", "build", "Verified against the sending domain for this campaign."],
    ["approvals", "Audit evidence pack", "build", "Approval records retained for inspection."],
    ["access", "Platform user roles", "reuse", "Standing role model; only membership changes."],
    ["access", "Dashboard permissions", "adapt", "Access extended to this campaign's stakeholders."],
  ];
  for (const [cat, title, cov, reason] of once) {
    out.push(make(cat, title, "Campaign-wide", cov, reason));
  }

  // Field enablement only where the journey actually has a field touchpoint.
  if (nodes.some((n) => hits(n.data.channel, FIELD_CHANNEL_HINTS))) {
    out.push(make("field", "Rep training material", "Campaign-wide", "build",
      "Reps are briefed per campaign before field touchpoints open."));
    out.push(make("field", "Talking points & field FAQ", "Campaign-wide", "adapt",
      "Adapted from the brand's standing field pack."));
  }

  return out;
}

// ---------------------------------------------------------------------------

const BUSINESS_DAYS_PER_WEEK = 5;

/** Business days between now and the go-live date. */
function businessDaysUntil(goLive: string): number {
  const end = new Date(goLive + "T00:00:00").getTime();
  const now = new Date(new Date().toISOString().slice(0, 10) + "T00:00:00").getTime();
  const calendar = Math.round((end - now) / 86_400_000);
  if (calendar <= 0) return 0;
  return Math.round((calendar / 7) * BUSINESS_DAYS_PER_WEEK);
}

/**
 * The verdict. Capacity is the honest weak point: with no team-capacity source in the app,
 * `parallelTeams` stands in for how much work can genuinely run at once. It is exposed as a
 * control on the stage rather than hidden, so the number is never mistaken for a fact.
 */
export function computeVerdict(
  items: Deliverable[],
  goLive: string,
  parallelTeams: number,
): LaunchVerdict {
  const totals = {
    total: items.length,
    reuse: items.filter((i) => i.coverage === "reuse").length,
    adapt: items.filter((i) => i.coverage === "adapt").length,
    build: items.filter((i) => i.coverage === "build").length,
    blocked: items.filter((i) => i.coverage === "blocked").length,
  };

  const workDays = items
    .filter((i) => i.coverage !== "reuse")
    .reduce((sum, i) => sum + i.effortDays, 0);
  const remainingDays = Math.round(workDays / Math.max(1, parallelTeams));

  // What it would have cost if nothing were reused — the honest version of "time saved".
  const naiveDays = Math.round(
    items.reduce((sum, i) => sum + Math.round(BASE_EFFORT[i.category]), 0) / Math.max(1, parallelTeams),
  );
  const effortSaved = Math.max(0, naiveDays - remainingDays);

  const availableDays = businessDaysUntil(goLive);
  const projectedOverrunDays = Math.max(0, remainingDays - availableDays);

  const blockers: LaunchVerdict["blockers"] = [];
  if (totals.blocked > 0) {
    blockers.push({
      title: `${totals.blocked} deliverable${totals.blocked === 1 ? "" : "s"} blocked`,
      detail: "Coverage could not be resolved — most often because no approved-claim record exists to check against.",
    });
  }
  const inReview = items.filter((i) => i.review !== "none").length;
  if (inReview > 0) {
    blockers.push({
      title: `${inReview} items need medical/legal review`,
      detail: "Review is a queue with round-trips, not a single gate. Plan two to three rounds per item.",
    });
  }
  if (projectedOverrunDays > 0) {
    blockers.push({
      title: `Projected ${projectedOverrunDays} business days past go-live`,
      detail: `${remainingDays} days of work remain against ${availableDays} available at ${parallelTeams} parallel workstreams.`,
    });
  }

  const status: LaunchVerdict["status"] =
    totals.blocked > 0 || projectedOverrunDays > 10 ? "blocked"
      : projectedOverrunDays > 0 ? "at-risk"
        : "on-track";

  const headline =
    status === "blocked"
      ? "Not launchable on this date as things stand."
      : status === "at-risk"
        ? "Tight. The date holds only if nothing slips."
        : "On track for the current go-live date.";

  return { status, headline, goLive, remainingDays, availableDays, projectedOverrunDays, totals, effortSaved, blockers };
}

/** Risks read off the same derivation, so the register is never an empty template. */
export function deriveRisks(items: Deliverable[], verdict: LaunchVerdict): Risk[] {
  const risks: Risk[] = [];

  if (verdict.totals.blocked > 0) {
    risks.push({
      id: "r-claims", severity: "high", owner: "Regulatory & legal",
      title: "Approval records are not readable by the tool",
      detail: `${verdict.totals.blocked} items cannot be coverage-checked. Until claim approval and expiry data is available, reuse is guesswork and the review plan is unverifiable.`,
    });
  }

  const fullReview = items.filter((i) => i.review === "full").length;
  if (fullReview > 2) {
    risks.push({
      id: "r-mlr", severity: "high", owner: "Regulatory & legal",
      title: "Review queue is the critical path",
      detail: `${fullReview} items need full review. At two to three rounds each, this queue governs the launch date more than any build task.`,
    });
  }

  const buildHeavy = CATEGORIES
    .map((c) => ({ c, n: items.filter((i) => i.category === c.id && i.coverage === "build").length }))
    .sort((a, b) => b.n - a.n)[0];
  if (buildHeavy && buildHeavy.n > 3) {
    risks.push({
      id: "r-load", severity: "medium", owner: buildHeavy.c.team,
      title: `${buildHeavy.c.name} carries the heaviest build load`,
      detail: `${buildHeavy.n} items built from scratch by one team. No capacity data exists to confirm they can absorb it.`,
    });
  }

  if (verdict.projectedOverrunDays > 0) {
    risks.push({
      id: "r-date", severity: verdict.projectedOverrunDays > 10 ? "high" : "medium", owner: "Delivery Lead",
      title: "Go-live date is not currently achievable",
      detail: `Projected ${verdict.projectedOverrunDays} business days beyond the date. Options are cut scope, stagger the review submissions, or move go-live.`,
    });
  }

  risks.push({
    id: "r-capacity", severity: "medium", owner: "Delivery Lead",
    title: "Capacity is assumed, not known",
    detail: "The projection divides remaining work by a parallel-workstream setting. Without real team capacity data this is an estimate, not a forecast.",
  });

  return risks;
}

/** The 14-step setup run. `state` marks which steps this build can genuinely compute today. */
export const RUN_STEPS: RunStep[] = [
  { n: 1, title: "Confirm what we're launching", agent: "Delivery Lead", state: "needs",
    question: "What exactly are we building, and by when?",
    needsNote: "Needs a freeze/version concept on the journey from the previous stage." },
  { n: 2, title: "Build the deliverables list", agent: "Content & Claims", state: "ready",
    question: "What has to exist for this campaign to run?" },
  { n: 3, title: "Check what we already have", agent: "Content & Claims", state: "ready",
    question: "What can we reuse, and what genuinely needs building?" },
  { n: 4, title: "Map the approval path", agent: "Approvals & Compliance", state: "needs",
    question: "What review does each item need, and how long will it really take?",
    needsNote: "Needs claim approval and expiry records. Nothing in the app holds these today." },
  { n: 5, title: "Write the requirements", agent: "Requirements Writer", state: "needs",
    question: "What does each team need in order to build their piece?",
    needsNote: "Needs a spec generator — no FRD/TRD drafting exists anywhere in the codebase." },
  { n: 6, title: "Check we have the people", agent: "Resourcing & Budget", state: "needs",
    question: "Can our teams deliver this inside the window?",
    needsNote: "Needs team capacity data. The projection below assumes it instead." },
  { n: 7, title: "Check we have the money", agent: "Resourcing & Budget", state: "needs",
    question: "Does this cost what we have?",
    needsNote: "Needs a rate card and budget envelope." },
  { n: 8, title: "Build the timeline", agent: "Planning & Risk", state: "ready",
    question: "When does this realistically land?" },
  { n: 9, title: "Decide the launch sequence", agent: "Delivery Lead", state: "ready",
    question: "What goes live on day one, and what follows?" },
  { n: 10, title: "Log the risks", agent: "Planning & Risk", state: "ready",
    question: "What could go wrong that hasn't yet?" },
  { n: 11, title: "Plan the testing", agent: "Testing & Tracking", state: "ready",
    question: "How do we prove this works before real people receive it?" },
  { n: 12, title: "Set the approvals", agent: "Approvals & Compliance", state: "needs",
    question: "Who signs off before we go live, and what proof do we keep?",
    needsNote: "Needs an approver roster per market." },
  { n: 13, title: "Wire up tracking", agent: "Testing & Tracking", state: "ready",
    question: "Will we actually be able to measure this?" },
  { n: 14, title: "Hand out the work", agent: "Delivery Lead", state: "needs",
    question: "How does this become real work people are doing?",
    needsNote: "Would reuse the existing push-to-work-system binding, carrying the spec." },
];

/** Launch waves, split by what the coverage pass says is closest to ready. */
export function deriveWaves(items: Deliverable[]): { name: string; note: string; items: Deliverable[] }[] {
  const ready = items.filter((i) => i.coverage === "reuse" || i.coverage === "adapt");
  const build = items.filter((i) => i.coverage === "build");
  const blocked = items.filter((i) => i.coverage === "blocked");
  return [
    { name: "Wave 1 — day one", note: "Reuse and light adaptation only. Nothing here waits on a full review round.", items: ready },
    { name: "Wave 2 — follow-on", note: "Built from scratch and cleared through full review.", items: build },
    { name: "Held back", note: "Cannot be scheduled until coverage resolves.", items: blocked },
  ].filter((w) => w.items.length > 0);
}
