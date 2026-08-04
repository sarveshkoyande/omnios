/** Contracts for the existing FastAPI project/chat/run-stream endpoints (server.py). */
import type { WorkflowDocument } from "./stages/operations/flowbuilder/schema/document";

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

/** Reporting & Insights tab payload (GET /api/projects/{pid}/reporting-insights). */
export interface ReportingSignal {
  label: string;
  kind: string;
  value_pct?: number;
  low_pct?: number;
  high_pct?: number;
  band?: string;
  note?: string;
  primary?: boolean;
}
export interface ReportingKpi extends ReportingSignal {
  value?: number;
  value_display?: string;
  sub?: string;
}
export interface SegmentRow {
  value: string;
  count: number;
}
export interface EmailMetricMonth {
  month: string;
  value_pct: number;
}
export interface EmailMetric {
  key: "delivery" | "open" | "ctr" | "ctor" | "bounce" | "unsubscribe";
  label: string;
  value_pct: number;
  monthly: EmailMetricMonth[];
}
export interface EmailMetrics {
  note: string;
  specialty: string;
  months: string[];
  metrics: EmailMetric[];
}
export interface OpensByTimeRow {
  day: string;
  cells: number[];
}
export interface StateCtrRow {
  state: string;
  ctr_pct: number;
}
export interface SegmentDeliveryRow {
  segment: string;
  pct: number;
}
export interface SubjectLineRow {
  asset_name: string;
  segment: string;
  subject_line: string;
  ab_testing: string;
  wave_type: string;
  emails_sent: number;
  deliveries: number;
  opens: number;
  clicks: number;
  open_rate_pct: number;
  ctr_pct: number;
}
export interface EmailDeepdive {
  opens_by_time: { hours: string[]; rows: OpensByTimeRow[] };
  ctr_by_state: StateCtrRow[];
  delivered_by_segment: SegmentDeliveryRow[];
  subject_lines: SubjectLineRow[];
  tiles: {
    unique_hcp_reached: number;
    unique_hcp_engaged: number;
    unique_hcp_deep_engaged: number;
    unique_subject_lines: number;
  };
}
export interface ReportingInsights {
  available: boolean;
  brand: string;
  therapy_area: string;
  lifecycle_label: string;
  lifecycle_key: string;
  stage_label: string;
  caveat: string;
  funnel: { stage: string; note: string; signals: ReportingSignal[] };
  kpis: ReportingKpi[];
  email_metrics: EmailMetrics;
  email_deepdive: EmailDeepdive;
  demographics: {
    available: boolean;
    total_hcps?: number;
    by_specialty?: SegmentRow[];
    by_preferred_channel?: SegmentRow[];
    by_segment?: SegmentRow[];
    by_state?: SegmentRow[];
  };
  tagging: { note: string; columns: string[]; rows: { parameter: string; convention: string; example: string }[] };
  test_design: { approach: string; note: string; rows: { test: string; variants: string; measure: string; primary: boolean }[] };
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
export const STAGE_AGENT_BY_INDEX: readonly StageAgentId[] = [
  "planning", "planning", "orchestration", "operations", "reporting",
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
