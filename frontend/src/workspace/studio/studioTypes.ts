/** SSE protocol v2 — Sequential Plan Studio (docs/SEQUENTIAL_STUDIO_DESIGN.md). */

export interface GroundingItem {
  source: string;
  label: string;
  snippet: string;
  ref?: string;
}

export interface AskOption {
  label: string;
  source?: string;
  /** Evidence shown under the option: an addressable-population estimate and the criteria
   *  that define the segment. Present on the segmentation ask. */
  size?: string;
  criteria?: string;
  /** Per-channel budget split shown under the option. Present on the channel-posture ask,
   *  where the whole point of the choice is what it does to the mix. */
  distribution?: { channel: string; pct: number }[];
}

export interface LlmStatus {
  engine?: string;
  ok?: boolean | null;
  detail?: string;
  ts?: string;
  diagnostics?: Record<string, string | number | boolean | null>;
}

/** One landed step's reasoning: inputs used (with source class), framework applied,
 * the decision, rationale, and which brief sections it feeds (decision_spine.py). */
export interface DecisionRecord {
  stage_id: string;
  stage_name: string;
  section_id: string;
  decision: string;
  framework: string;
  rationale: string;
  inputs: { label: string; value: string; source_class: string; source: string }[];
  alternatives: { label: string; why_rejected: string }[];
  feeds: string[];
  answered_by_user: boolean;
  /** The decision as objects rather than a joined string — segments, channels, rungs — each
   *  with the measured evidence it was chosen on. All fields below are optional so records
   *  persisted before decision_spine started emitting them still parse. */
  decision_items?: DecisionItem[];
  /** What the agent proposed, kept even when the user overrode it — this is what lets the
   *  card show "agent said X, you chose Y" without storing revision history. */
  agent_recommendation?: { label: string; reason?: string };
  /** Both directions of the spine graph: what this rests on, and what rests on it. */
  dependencies?: { stage_id: string; stage_name: string; relation: "depends_on" | "feeds_stage" }[];
  /** S2 only: the HCP 360 sizing basis, so the trail and Reporting can be shown to count the
   *  same population. */
  panel_scope?: {
    headline?: string;
    confidence?: string;
    caveat?: string;
    segment_breakdown?: Record<string, number>;
    sources?: string[];
  };
  /** The stage posed an ask, so the decision can be revised in place. */
  editable?: boolean;
}

export interface DecisionItem {
  label: string;
  /** Absolute measure, e.g. "2,376 HCPs" or "35% of mix". */
  value?: string;
  /** Share of the sizing population; drives the bar. Null when the stage has no sizing. */
  share_pct?: number | null;
  /** The behavioural definition of the segment — why these HCPs are one group. */
  criteria?: string;
  source?: string;
  /** First item: the group the plan leads with. */
  lead?: boolean;
}

export interface StudioAsk {
  ask_id: string;
  section: number;
  text: string;
  source?: "ai" | "deterministic" | "deterministic-fallback";
  llm_status?: LlmStatus;
  evidence_basis?: string;
  framework?: string;
  blocked?: string;
  why: string;
  recommendation_reason?: string;
  recommendation: AskOption;
  options: AskOption[];
  free_text: boolean;
  /** When true the user can select more than one option; the answer is the joined labels. */
  multi_select?: boolean;
  /** Multi-select only: labels ticked on open. Falls back to the recommendation alone when
   *  absent, which is wrong whenever the sensible default is a set rather than one row. */
  preselected?: string[];
  /** Multi-select only: what is being counted in the confirm button ("segment", "rung"). */
  select_noun?: string;
  /** One-line summary of the data analysis behind the options (e.g. the sizing methodology). */
  evidence_note?: string;
  /** Auto-assume was on: the agent took `auto_answer` (its own recommendation) without
   *  waiting, and the stream kept running instead of stopping at this gate. */
  auto_assumed?: boolean;
  auto_answer?: string;
}

export type StudioEvent =
  | { type: "run_open"; total_sections: number }
  | { type: "phase_open"; idx: number; section_id: string; num: number; title: string; owner: string; owner_name: string }
  | { type: "grounding"; section_id: string; items: GroundingItem[] }
  | ({ type: "ask" } & StudioAsk)
  | { type: "drafting"; section_id: string; note: string }
  | { type: "section_html"; section_id: string; num: number; title: string; owner: string; html: string }
  | { type: "phase_done"; section_id: string; idx: number }
  | ({ type: "decision_record" } & DecisionRecord)
  | { type: "chat"; author: string; text: string; kind: "turn" | "banter"; reply_to?: string }
  | { type: "plan"; html: string; markdown: string; partial: boolean }
  | { type: "agents_init"; agents: { id: string; name: string; role: string }[] }
  | { type: "run_done" }
  | { type: "error"; message: string };

export interface StudioSection {
  section_id: string;
  num: number;
  title: string;
  owner: string;
  html: string;
}

export interface StudioSlot {
  idx: number;
  num: number;
  title: string;
  owner: string;
  ownerName: string;
  state: "ground" | "ask" | "draft";
  grounding: GroundingItem[];
  draftNote?: string;
}

export interface StudioState {
  active: boolean;
  total: number;
  sections: StudioSection[];
  slot: StudioSlot | null;
  done: boolean;
  records: DecisionRecord[];
  /** True right after a section lands, until the user clicks "Continue to next section" --
   * sections no longer auto-advance one into the next. */
  awaitingContinue: boolean;
}

export const STUDIO_IDLE: StudioState = { active: false, total: 0, sections: [], slot: null, done: false, records: [], awaitingContinue: false };
