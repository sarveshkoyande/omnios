/** Contracts for the existing FastAPI project/chat/run-stream endpoints (server.py). */

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
  [k: string]: unknown;
}

export interface Stakeholder {
  id: string;
  name: string;
  role: string;
  team: string;
  email?: string;
}

export interface Vendor {
  id: string;
  name: string;
  type: string;
  contact?: string;
  status?: string;
}

export interface Confirmation {
  id: string;
  team: string;
  item: string;
  status: string;
  notes?: string;
}

export interface TimelineActivity {
  id: string;
  activity: string;
  start?: string;
  end?: string;
  duration_days?: number;
  status?: string;
  raci?: Record<string, "R" | "A" | "C" | "I" | undefined>;
}

export interface ResourcePlanRow {
  id: string;
  role: string;
  stakeholder_id?: string;
  stakeholder_name?: string;
  allocation_pct?: number;
  notes?: string;
}

export interface RaciRow {
  activity: string;
  assignments: { stakeholder_id: string; name: string; letter: string }[];
}

export interface CampaignSetup {
  jira: { space_key: string; project_id: string; board_url?: string };
  stakeholders: Stakeholder[];
  vendors: Vendor[];
  confirmations: Confirmation[];
  timeline: TimelineActivity[];
  resources: ResourcePlanRow[];
  raci: RaciRow[];
  brd: { markdown: string; generated_at: string } | null;
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
  meta?: { kind: "clarify"; clarify: ClarifyPayload | null } | null;
}

export interface ProjectSummary {
  id: string;
  name: string;
  phase: "collecting" | "running" | "done" | string;
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
  };
  messages: ChatMessage[];
  plan_markdown: string | null;
  plan_html: string | null;
  result: PlanResult | null;
}

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

/** Agent identity — mirrors AGENT_PEOPLE in the legacy index.html / orchestrator.py. */
export const AGENT_PEOPLE: Record<string, { name: string; c1: string; c2: string; initials: string; photo: string }> = {
  planner: { name: "Engagement Plan Composer", initials: "EP", c1: "#7B3FE4", c2: "#A277F0", photo: "/static/agent_avatars/agent-5-purple.png" },
  intel: { name: "Market & Competitive Intelligence Agent", initials: "MC", c1: "#E5323C", c2: "#FF6B72", photo: "/static/agent_avatars/agent-2-red.png" },
  strategy: { name: "Strategy & Positioning Agent", initials: "SP", c1: "#22B36B", c2: "#57DD97", photo: "/static/agent_avatars/agent-3-green.png" },
  inspiration: { name: "Creative Inspiration Agent", initials: "CI", c1: "#F5730A", c2: "#FFA333", photo: "/static/agent_avatars/agent-4-orange.png" },
  activation: { name: "Activation Planning Agent", initials: "AP", c1: "#7B3FE4", c2: "#A277F0", photo: "/static/agent_avatars/agent-5-purple.png" },
};

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
  | { type: "done"; last_phase?: boolean };

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
