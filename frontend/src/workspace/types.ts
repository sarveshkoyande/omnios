/** Contracts for the existing FastAPI project/chat/run-stream endpoints (server.py). */
import type { WorkflowDocument } from "./stages/operations/flowbuilder/schema/document";
import type { DecisionRecord, StudioAsk, StudioSection } from "./studio/studioTypes";

export interface Slots {
  brand: string;
  therapy_area: string;
  lifecycle_key: string;
  budget: number;
  indication?: string;
  campaign_name?: string;
  molecule?: string;
  audience?: string;
  geography?: string;
  duration?: string;
  objective?: string;
  kpi?: string;
  preferred_channels?: string;
  existing_assets?: string;
  constraints?: string;
  reason?: string;
  notes?: string;
  maturity_notes?: string;
  /** Presentational ≤20-word summaries of the long brief fields (server-attached). */
  brief_summary?: Partial<Record<string, string>>;
  [k: string]: unknown;
}

/** One brief field pulled from an uploaded brand plan, ready to show back to the user. */
export interface BriefExtractItem {
  key: string;
  label: string;
  value: string;
}

export interface ClarifyPayload {
  text: string;
  group_index: number;
  group_total: number;
  title: string;
  source?: string;
}

export interface ChatMessage {
  role: "agent" | "user";
  text: string;
  meta?:
    | { kind: "clarify"; clarify: ClarifyPayload | null }
    // A studio ask, stored with the answer it was closed on, so reopening a plan replays the
    // question and not just the reply. `ask` is the StudioAsk payload (typed loosely here to
    // keep studioTypes out of this module's imports).
    | { kind: "studio_ask"; ask: unknown; answer?: string }
    | null;
}

export interface ProjectSummary {
  id: string;
  name: string;
  phase: "collecting" | "running" | "done" | string;
  // Enriched digest from strategy/projects.py::list_projects (optional for back-compat
  // with any caller/mocks that predate the enrichment).
  created_at?: string;
  updated_at?: string;
  brand?: string;
  therapy_area?: string;
  campaign_name?: string;
  lifecycle_key?: string;
  objective?: string;
  has_result?: boolean;
  /** Furthest workspace stage the plan sits in (strategy/projects.py::_plan_stage). */
  stage?: "planning" | "orchestration" | "operations" | "reporting";
  /** Sections completed in the Stage 1 studio run (strategy/projects.py::_planning_progress).
   *  PLANNING-stage progress only -- never render it as overall campaign completion.
   *  Absent on plans that have not started a studio run. */
  planning_progress?: { done: number; total: number; pct: number };
}

export interface ProjectDetail {
  id: string;
  name: string;
  phase: string;
  state: {
    slots: Slots;
    plan_frozen?: boolean;
    open_questions?: { id: string; title: string; phase: string }[];
    clarify_idx?: number;
    persona_reviews?: PersonaReview[] | null;
    revealed_phases?: string[];
    current_phase?: string;
    /** Persisted Stage 1 studio run. Every other slice of `state` was already rehydrated on
     *  open; this one was not, so reopening a finished plan showed an empty section list and
     *  "0/11 completed" while the sections sat in the database. Shape mirrors what
     *  studio_run.py writes -- `sections` is exactly StudioSection[]. */
    studio?: {
      idx?: number;
      sections?: StudioSection[];
      records?: DecisionRecord[];
      await_ask?: StudioAsk | null;
    };
  };
  messages: ChatMessage[];
  plan_markdown: string | null;
  plan_html: string | null;
  result: PlanResult | null;
  campaign_plan_layout: WorkflowDocument | null;
  orchestration_tasks: OrchestrationTask[] | null;
}

/** Structured SLA record (orchestration_sla.resolve) carried under `sla_meta`. */
export interface SlaMeta {
  activity_type: string;
  complexity: string;
  baseline_days: number;
  target_days: number;
  days_saved: number;
  definition_of_done: string;
  gating_input?: string | null;
  sla_label: string;
}

/** Governed multi-dimensional tags (orchestration_taxonomy.TAG_DIMENSIONS). */
export interface ActivityTags {
  team?: string | null;
  channel?: string | null;
  asset_type?: string | null;
  phase?: string | null;
  compliance_tier?: string | null;
  automation_class?: string | null;
  risk?: string | null;
}

export type GateKind = "MLR" | "CONSENT" | "ISI" | "AFU" | "AE_MIR";

export interface OrchestrationTask {
  id: string;
  category: string;
  title: string;
  channel?: string | null;
  done: boolean;
  team: string;
  sla?: string | null;
  assigned_to?: string | null;
  source?: string | null;
  // --- Engagement Orchestration activity model (added M1; optional for back-compat) ---
  activity_type?: string;
  phase?: string;
  automation_class?: string;
  compliance_tier?: string;
  gate?: GateKind | null;
  risk?: string;
  definition_of_done?: string;
  gating_input?: string | null;
  sla_meta?: SlaMeta;
  tags?: ActivityTags;
  // --- schedule fields, populated on the timeline (not persisted on the task) ---
  planned_start?: string;
  planned_due?: string;
  slack_days?: number;
  is_critical?: boolean;
}

/** Response of POST /api/projects/{pid}/orchestration-schedule (orchestration_schedule.build_schedule). */
export interface OrchestrationSchedule {
  mode: "backward" | "forward";
  go_live: string;
  infeasible: boolean;
  infeasible_note?: string | null;
  activities: OrchestrationTask[];
  bands: {
    phase: string;
    start: string;
    end: string;
    duration_days: number;
    baseline_duration_days: number;
    is_post_launch: boolean;
  }[];
  critical_path_ids: string[];
  elapsed: {
    pre_launch_days: number;
    pre_launch_days_baseline: number;
    days_saved: number;
    reduction_pct: number;
    reference_baseline_simple_campaign_days: number;
    reference_target_days: number;
  };
  effort: {
    baseline_days_total: number;
    target_days_total: number;
    days_saved_total: number;
    reduction_pct: number;
    note: string;
  };
}

/** Internal activity <-> downstream record link (orchestration_store.external_binding). */
export interface ExternalBinding {
  project_id: string;
  activity_id: string;
  system: string;
  external_id?: string | null;
  external_url?: string | null;
  last_synced_hash?: string | null;
  sync_state: string;
  updated_at: string;
}

export interface PushResultRow {
  activity_id: string;
  title?: string;
  system: string;
  action: "created" | "updated" | "skipped" | "unconfigured" | "error";
  external_id?: string;
  external_url?: string;
  board?: string;
  detail?: string;
}

export interface PushResponse {
  results: PushResultRow[];
  counts: Record<string, number>;
  bindings: ExternalBinding[];
}

export interface BindingsResponse {
  bindings: ExternalBinding[];
  routing: { default_system?: string; routes?: Record<string, { system: string; board: string }> };
}

export interface SyncAppliedChange {
  activity_id: string;
  title?: string;
  field: string;
  value: unknown;
  system: string;
}
export interface SyncConflict {
  activity_id: string;
  title?: string;
  field: string;
  internal?: string;
  external?: string;
  resolution: string;
}
export interface SyncEvent {
  id: number;
  activity_id?: string;
  system?: string;
  direction: string;
  field?: string;
  old_value?: string;
  new_value?: string;
  result: string;
  created_at: string;
}
export interface SyncResponse {
  applied: SyncAppliedChange[];
  conflicts: SyncConflict[];
  changed: boolean;
  events: SyncEvent[];
}

export interface Notification {
  project_id: string;
  dedupe_key: string;
  activity_id?: string;
  trigger: string;
  severity: "urgent" | "high" | "warning" | "info";
  channel: string;
  recipient: string;
  title: string;
  body: string;
  gate?: string | null;
  fire_count: number;
  escalated: number;
  acked: number;
  created_at: string;
  updated_at: string;
}

export interface NudgeRunResponse {
  created: { dedupe_key: string; trigger: string; severity: string; escalated: boolean }[];
  escalated: { dedupe_key: string }[];
  open: Notification[];
}

export interface NotificationsResponse {
  notifications: Notification[];
  policy: { lead_time_days?: number; escalate_after_fires?: number; escalation_recipient?: string };
}

/** One node of the engagement journey, as the brief prints it (strategy/journey_brief.py). */
export interface JourneyStep {
  id: string;
  /** Raw node type: entry | send | wait | decision | branch | followup | exit | closure. */
  kind: string;
  /** That type in words — "Send", "Follow-up", "Decision". */
  kind_label: string;
  /** True for the steps that actually contact an HCP (send / follow-up). */
  is_comms: boolean;
  day?: number | null;
  label: string;
  channel?: string;
  detail?: string;
}

/** The engagement journey projected from the campaign-ops flow (strategy/journey_brief.py).
 *  Every touchpoint, wait window, split and branch — not a collapsed summary of the first one. */
export interface JourneyMap {
  summary?: string;
  duration_days?: number;
  entry?: string[];
  touchpoint_count?: number;
  steps?: JourneyStep[];
  comms_steps?: JourneyStep[];
  gates?: JourneyStep[];
  decision_logic?: { condition: string; outcome: string }[];
  operational_rules?: string[];
}

/** The journey picture: Mermaid source + the mermaid.ink URL that renders it. */
export interface JourneyDiagramPayload {
  ok: boolean;
  detail: string;
  mermaid: string;
  image_url: string;
}

/** Campaign Strategy + Brief payload (strategy/campaign_artifacts.py). */
export interface CampaignArtifactsPayload {
  strategy: {
    title: string;
    brand: string;
    generated_at: string;
    source_summary?: StrategicSourceSummary;
    note: string;
    records: import("./studio/studioTypes").DecisionRecord[];
  };
  brief: {
    title: string;
    version: string;
    generated_at: string;
    header: { brand: string; therapy_area: string; lifecycle: string; owner: string };
    /** The five lines a brand manager reads first. Rendered above everything else. */
    snapshot?: {
      objective: string;
      brand: string;
      therapy_area: string;
      target_audience: string;
      reason: string;
    };
    source_summary?: StrategicSourceSummary;
    journey_diagram?: JourneyDiagramPayload;
    purpose: { program_context: string; trigger_logic: string[]; summary: string };
    objective: { pillar: string; statement: string; leading_indicators: string[] };
    audience: {
      segment: string;
      eligibility_rules: string[];
      segments: { name: string; profile: string; volume: number | null; volume_note: string | null; volume_exact?: boolean; key_characteristics: string[] }[];
      consent_note: string;
    };
    comms_strategy: {
      belief_shift: string;
      message_ladder: string[];
      message_detail: { topic: string; supporting: string[] }[];
      tone_guardrails: string[];
      core_claim: string;
    };
    deliverables: { asset: string; variants: string; notes: string }[];
    channel_journey: { anchor: string; mix: { channel: string; pct: number }[]; cadence_note: string; journey: JourneyMap };
    measurement_plan: { kpis: string[]; link_matrix_note: string; test_design: string };
    scope_review: { ladder: string; rounds_note: string; change_control: string };
    risk_register: { risk: string; severity: string; mitigation: string }[];
    assumptions: string[];
    timeline: { window: string; note: string };
    approvals: { role: string; name: string }[];
    traceability: { brief_section: string; stage_id: string; stage_name: string; framework: string }[];
    /** Audit detail: needed to check the brief, not to read it. Rendered last. */
    technical_appendix?: {
      review_and_pv: string[];
      technical_decisions: { stage_id: string; stage_name: string; decision: string; framework: string }[];
    };
  };
}

export interface StrategicSourceSummary {
  basis: string;
  source_name: string;
  has_strategic_source: boolean;
  captured_fields: { label: string; value: string }[];
  csfs: string[];
  positioning: string;
  evidence: string[];
  guardrails: string[];
}

/** Fixed team roster + display order -- kept in sync with strategy/orchestration_tasks.py. */
/** Also the left-to-right order of the team tabs in Engagement Orchestration. */
export const ORCHESTRATION_TEAMS = [
  "Web team",
  "Content & derivative assets team",
  "Data & data cloud team",
  "Campaign operations team",
  "Reporting & insights team",
] as const;

/** Default team for a manually added task. Named rather than indexed so reordering the
 *  tabs above cannot silently change which team new tasks land in. */
export const DEFAULT_TASK_TEAM = "Campaign operations team";

export interface ChannelSelectionRow {
  channel: string;
  brand_priority?: string;
  availability?: string;
  preference_affinity?: number;
}

export interface BudgetAllocationRow {
  pct: number;
  amount?: number;
}

export interface ContentAssetLite {
  asset_format: string;
  title: string;
  branded: boolean;
}

export interface ExecutionBand {
  category: string;
  start_week: number;
  end_week: number;
  tasks: string[];
}

export interface TmlRow {
  test: string;
  measure: string;
  channels: string;
  frequency: string;
  what_good_looks_like: string;
}

/** Stage 3 — Campaign Operations: the synthesized journey diagram + planning summary. */
export interface CampaignSegment {
  key: string;
  name: string;
  profile: string;
  key_characteristics: string[];
  volume: number | null;
  volume_note?: string | null;
  /** True when `volume` is a counted panel headcount rather than an apportioned estimate. */
  volume_exact?: boolean;
}

/** `entry` is the journey's trigger (ad-hoc / API / website sign-up) and `branch` is the
 *  behavioural split on what the HCP clicked — both added with the Journey Builder-shaped
 *  flow in strategy/journey_design.py. */
export type CampaignFlowNodeType =
  | "entry"
  | "send"
  | "wait"
  | "decision"
  | "branch"
  | "exit"
  | "followup"
  | "closure";

export interface CampaignFlowNode {
  id: string;
  type: CampaignFlowNodeType;
  position: { x: number; y: number };
  data: {
    label: string;
    day?: number;
    segment_key?: string;
    channel?: string;
    detail?: string;
    content_ref?: { label: string; ready: boolean; branded?: boolean };
  };
}

export interface CampaignFlowEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
}

export interface CampaignFlow {
  nodes: CampaignFlowNode[];
  edges: CampaignFlowEdge[];
}

export interface CampaignPlan {
  overview: {
    objective: string;
    duration_days: number;
    max_communications: number;
    primary_channel: string;
    secondary_automation: string;
  };
  segments: CampaignSegment[];
  entry_criteria: string[];
  flow: CampaignFlow;
  decision_logic_summary: { condition: string; outcome: string }[];
  operational_rules: string[];
  kpis: PlanResult["stage_7_kpi"];
  summary: string;
}

export interface PlanResult {
  inferred_inputs: {
    persona: string;
    stage_label: string;
    lifecycle_label: string;
    discovered_competitors: string[];
  };
  cx_maturity?: { level?: string };
  open_questions?: { id: string; title: string; phase: string }[];

  stage_2_4_micro_journeys?: {
    journeys: { name: string; trigger: string; primary_touchpoint: string; content_readiness: string }[];
    interim_check?: string;
  };
  stage_2_4_bam_chart?: { a_to_b_shift?: string };
  stage_2_4_strategy?: {
    messaging_architecture?: { current_belief?: string; desired_belief?: string };
    recommended_touchpoints?: Record<string, string[]>;
  };
  stage_2_4_message_flow?: { key_messages: { topic: string; supporting_messages: string[] }[] };
  stage_2_4_pp_npp?: { channel: string; pct: number; bucket: string }[];
  stage_5_channel_selection?: { channels: ChannelSelectionRow[] };
  stage_5_budget?: { allocation: Record<string, BudgetAllocationRow> };
  stage_3_campaign_plan?: CampaignPlan;
  stage_9_execution_plan?: { bands: ExecutionBand[]; mlr_delay_note?: string };
  stage_7_kpi?: {
    leading_indicators: string[];
    lagging_indicators: string[];
    operational_kpis: string[];
    cadence_note?: string;
  };
  stage_9_test_measure_learn?: { rows: TmlRow[] };
  content_library?: {
    found: boolean;
    assets: ContentAssetLite[];
    counts?: { assets?: number; approved_claims?: number };
  };
}

/** Reporting & Insights tab payload (GET /api/projects/{pid}/reporting-insights).
 *
 *  Every number below is counted out of the HCP 360 panel for the *current filter
 *  combination* (strategy/hcp_panel_metrics.py) and scaled by the cited benchmarks
 *  (strategy/reporting_metrics.py) — so changing a filter refetches and genuinely changes
 *  the population behind the chart, rather than relabelling a fixed series. */

/** The dimensions the filter bar can drill on — 1:1 with hcp_panel_metrics.DIMENSIONS. */
export type ReportingFilterKey = "specialty" | "state" | "segment" | "channel" | "brand";
export type ReportingFilters = Partial<Record<ReportingFilterKey, string>>;

export type MetricStatus = "good" | "watch" | "risk" | "neutral";

export interface MetricPoint {
  month: string;
  value: number;
}

/** One selectable metric. Drives both a KPI card and (when selected) the trend chart. */
export interface ReportingMetric {
  key: string;
  label: string;
  unit: "%" | "count" | "index";
  value: number;
  benchmark: number | null;
  band: [number, number] | null;
  delta: number;
  delta_unit: string;
  direction: "up" | "down" | "flat";
  higher_is_better: boolean;
  status: MetricStatus;
  description: string;
  monthly: MetricPoint[];
}

export interface FunnelStep {
  stage: string;
  count: number;
  pct_of_audience: number;
  pct_of_prior: number;
}

/** One node of the reporting journey view — distinct from the brief's JourneyStep above. */
export interface ReportingJourneyStep {
  id: string;
  label: string;
  count: number;
  pct: number;
  kind: "send" | "step" | "decision" | "outcome";
  branch?: { label: string; count: number; pct: number };
}

export interface ChannelRow {
  channel: string;
  label: string;
  icon: string;
  hcps: number;
  preferred_pct: number;
  affinity: number;
  engagement_pct: number;
}

export interface GeoRow {
  state_code: string;
  state: string;
  hcps: number;
  open_pct: number;
  ctr_pct: number;
  index: number;
}

export interface AssetRow {
  name: string;
  tag: string;
  type: string;
  audience: number;
  open_pct: number;
  ctr_pct: number;
  conversion_pct: number;
}

export interface SendWindows {
  sessions: string[];
  total: number;
  rows: { day: string; cells: number[]; counts: number[] }[];
}

export interface ReportingInsight {
  id: string;
  kind: "recommendation" | "anomaly" | "win";
  severity: "info" | "positive" | "warning" | "critical";
  title: string;
  detail: string;
  action: string;
  evidence: string;
  metric_key?: string;
}

export interface FacetValue {
  value: string;
  count: number;
}

/** A dimension breakdown row (segment / specialty / channel), with its own measured affinity. */
export interface BreakdownRow {
  value: string;
  count: number;
  email_affinity: number;
  digital_affinity: number;
}

export interface ReportingInsights {
  available: boolean;
  brand: string;
  therapy_area: string;
  lifecycle_label?: string;
  lifecycle_key?: string;
  stage_label?: string;
  caveat?: string;
  message?: string;
  grounding?: {
    panel_size: number;
    cohort_size: number;
    cohort_share_pct: number;
    deliverable_pct: number;
    trx_total: number;
    writers: number;
    lifecycle_index: number;
    sources: string[];
  };
  filters: {
    applied: ReportingFilters;
    facets: Record<ReportingFilterKey, FacetValue[]>;
    months: number;
    month_labels: string[];
  };
  headline_keys?: string[];
  metrics?: ReportingMetric[];
  funnel?: { steps: FunnelStep[]; volumes: Record<string, number> };
  journey?: ReportingJourneyStep[];
  channels?: ChannelRow[];
  geo?: GeoRow[];
  assets?: AssetRow[];
  send_windows?: SendWindows;
  breakdowns?: {
    segment: BreakdownRow[];
    specialty: BreakdownRow[];
    channel: BreakdownRow[];
    state: GeoRow[];
  };
  insights?: ReportingInsight[];
  optimizations?: { title: string; impact: string; metric: string; detail: string }[];
  scorecard?: {
    on_track: number;
    tracked: number;
    rows: { label: string; value: number; unit: string; benchmark: number | null; status: MetricStatus; key: string }[];
  };
  framework?: {
    rows: { area: string; source: string; status: string; detail: string }[];
    coverage_pct: number;
    live: number;
    total: number;
    note: string;
  };
  learnings?: { title: string; detail: string }[];
  tagging?: { note: string; columns: string[]; rows: { parameter: string; convention: string; example: string }[] };
  test_design?: {
    approach: string;
    note: string;
    active: number;
    rows: { test: string; variants: string; measure: string; cell_size: number; primary: boolean }[];
  };
}

export interface ChatResponse {
  reply: string;
  slots: Slots;
  phase: string;
  action: "run" | "update_plan" | "freeze" | null | string;
  name: string;
  llm_status: unknown;
  clarify: ClarifyPayload | null;
  clarify_just_completed: boolean;
  next_phase: string | null;
  plan_updated: boolean;
  plan_html: string | null;
  plan_markdown: string | null;
  updated_sections: string[];
  plan_frozen: boolean;
}

export interface PersonaReview {
  persona_id: string;
  persona_name: string;
  who: string;
  segment_name: string;
  sentiment: "enthusiastic" | "interested" | "skeptical" | "resistant";
  engagement_likelihood: number;
  quote?: string;
  narrative: string;
  resonates: string[];
  gaps: string[];
  asks: string[];
  channel_reactions?: { bucket: string; pct: number; reaction: string }[];
}

/**
 * Agent identity — one agent per workflow stage, not one per internal work-step.
 * Each stage's agent still does its work as several internal steps server-side
 * (Planning & Strategy: market intel, positioning, creative inspiration, activation
 * planning, plan composition) but presents as a single conversational identity — no
 * per-step avatars, no agents shown conversing with each other as peers. Backend
 * events that still tag individual work-steps (studio_run.py's AGENT_ROSTER ids) are
 * normalized down to the owning stage's persona in useWorkspace.ts before they ever
 * reach state, so every consumer here only ever sees one of these four ids.
 */
export interface AgentPersona { id: string; name: string; initials: string; c1: string; c2: string; photo: string }

export const STAGE_AGENTS = {
  planning: { id: "planning", name: "Campaign Planning & Strategy Agent", initials: "PS", c1: "#1768D1", c2: "#4AA6F2", photo: "/static/agent_avatars/agent-1-blue.png" },
  orchestration: { id: "orchestration", name: "Engagement Orchestration Agent", initials: "EO", c1: "#047857", c2: "#10B981", photo: "/static/agent_avatars/agent-3-green.png" },
  operations: { id: "operations", name: "Campaign Operations Agent", initials: "CO", c1: "#cc0047", c2: "#E85B8A", photo: "/static/agent_avatars/agent-2-red.png" },
  reporting: { id: "reporting", name: "Reporting & Insights Agent", initials: "RI", c1: "#e14b1e", c2: "#F0764A", photo: "/static/agent_avatars/agent-4-orange.png" },
} as const satisfies Record<string, AgentPersona>;

export type StageAgentId = keyof typeof STAGE_AGENTS;

/** Workspace stage number -> owning agent. The stage tabs are 1-based, so index 0 is unused.
 *  Single source of truth for "whose window am I looking at" — the chat header identity and
 *  the per-stage accent colour both resolve through this. */
/** Index is the stage id, not tab position — id 5 is the Campaign Ops (2) sandbox, which
 *  renders between ids 3 and 4 in the stepper but keeps its own id here. */
export const STAGE_AGENT_BY_INDEX: readonly StageAgentId[] = [
  "planning", "planning", "orchestration", "operations", "reporting", "operations",
] as const;

export function agentForStage(stage: number): StageAgentId {
  return STAGE_AGENT_BY_INDEX[stage] ?? "planning";
}

/** Keyed lookup for AgentAvatar / ChatMessages, which only ever address agents by id. */
export const AGENT_PEOPLE: Record<string, AgentPersona> = STAGE_AGENTS;

export type RunEvent =
  | { type: "agents_init"; agents: { id: string; name: string; role?: string }[] }
  | { type: "agent"; id: string; status: "running" | "done"; say?: string; summary?: string; final?: boolean; detail?: { bullets: string[] } }
  | { type: "inferred"; persona?: string; stage_label?: string; lifecycle_label?: string; competitors?: string[]; cx_maturity?: string }
  | { type: "narration"; text: string }
  | { type: "banter"; id: string; to: string; text: string }
  | { type: "clarify"; text: string; clarify: ClarifyPayload }
  | { type: "plan"; html: string; markdown: string; partial: boolean; sections_done?: number; sections_total?: number }
  | { type: "result"; result: PlanResult }
  | { type: "error"; message: string }
  | { type: "done"; last_phase?: boolean; revealed_phases?: string[] };

export interface PersonaSummary {
  id: string;
  name: string;
  who: string;
  age?: number;
  segment_name: string;
}

export interface PersonaOffer {
  matched: PersonaSummary[];
  others: PersonaSummary[];
}

export interface PersonaDetail {
  id: string;
  name: string;
  specialty?: string;
  age?: number;
  gender?: string;
  ethnicity?: string;
  location?: string;
  years_in_practice?: number;
  tagline?: string;
  bio?: string;
  voice_sample?: string;
  decision_drivers?: string[];
  frustrations?: string[];
  prescribing?: { monthly_trx?: number; monthly_nrx?: number; adoption_curve?: string };
  digital?: { affinity?: string; affinity_score?: number; rep_access?: string };
  channels?: { preferred?: string[]; avoided?: string[]; f2f_stance?: string; email_stance?: string };
}

export interface PersonaApplyChange {
  note: string;
  from_pct: number;
  to_pct: number;
}

export const BRIEF_TEMPLATE =
  "[Campaign name] is an omnichannel campaign for [Brand], a [molecule] indicated for " +
  "[indication], currently in the [lifecycle stage: launching / growing / mature / facing loss of exclusivity]. " +
  "We are planning to engage [audience] in [country / region] over [duration] with a budget of [budget]. " +
  "Our goal is to [business objective] by driving [desired outcome / KPI]. " +
  "We already have [existing assets] available and plan to use [preferred channels], " +
  "while considering [constraints]. Additional context or known challenges include [optional notes].";
