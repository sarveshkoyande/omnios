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
