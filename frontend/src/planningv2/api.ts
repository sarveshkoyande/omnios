// Thin fetch wrapper for the v2 Strategic-to-Tactical Planning Engine, following the same
// pattern as ../api.ts: relative /api/... paths, FormData for uploads, thrown Error on !res.ok.

export interface Gap {
  field: string;
  tactical_section_blocked: string;
  why_needed: string;
  inferable: boolean;
  sources_attempted: string[];
  question: string | null;
  suggested_default: string | null;
  impact_rank: number;
}

export interface ComplianceFinding {
  rule: string;
  severity: "blocker" | "warning";
  location: string;
  message: string;
}

export interface TacticalSectionData {
  summary: string;
  items: Record<string, unknown>[];
  csf_mapping: string[];
  guardrails: string[];
}

export interface PlanningRunPayload {
  id: string;
  stage: "ingested" | "extracted" | "enriched" | "gaps_analyzed" | "awaiting_answers" | "synthesized" | "validated" | "handed_off";
  brand: string;
  questions: Gap[];
  deferred: Gap[];
  assumptions: Gap[];
  strategic_context: Record<string, unknown> | null;
  tactical_plan: (Record<string, unknown> & {
    strategic_recap?: string;
    investment_thesis?: string;
    omnichannel_strategy?: { channel: string; role: string; branded_or_unbranded: string; csf_mapping: string[] }[];
    measurement?: { csf_id: string; leading_indicators: string[]; lagging_indicators: string[]; targets: Record<string, { value: unknown; is_placeholder: boolean; note: string }> }[];
    patient_strategy?: { summary: string; items: unknown[]; gated: boolean; gating_logic: string };
    appendices?: { competitive_context: string; measurement: string; guardrails_recap: string[] };
  }) | null;
  brb: (Record<string, unknown> & {
    initiative_summary?: string;
    workstreams?: { name: string; tactical_sections: string[]; deliverables: string[]; proposed_owning_team: string; dependencies: string[]; parallelizable: boolean; suggested_sla: string }[];
    compliance_checkpoints?: { checkpoint_type: string; location: string; description: string }[];
  }) | null;
  compliance: { findings: ComplianceFinding[] } | null;
}

async function handle(res: Response): Promise<PlanningRunPayload> {
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function startPlanningRun(file: File): Promise<PlanningRunPayload> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/planning-v2/runs", { method: "POST", body: form });
  return handle(res);
}

export async function getPlanningRun(runId: string): Promise<PlanningRunPayload> {
  const res = await fetch(`/api/planning-v2/runs/${encodeURIComponent(runId)}`);
  return handle(res);
}

export async function answerPlanningQuestion(runId: string, field: string, value: string): Promise<PlanningRunPayload> {
  const res = await fetch(`/api/planning-v2/runs/${encodeURIComponent(runId)}/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ field, value }),
  });
  return handle(res);
}

export async function finishPlanningRun(runId: string): Promise<PlanningRunPayload> {
  const res = await fetch(`/api/planning-v2/runs/${encodeURIComponent(runId)}/finish`, { method: "POST" });
  return handle(res);
}

export async function handoffPlanningRun(runId: string): Promise<{ brb: Record<string, unknown> }> {
  const res = await fetch(`/api/planning-v2/runs/${encodeURIComponent(runId)}/handoff`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `${res.status} ${res.statusText}`);
  }
  return res.json();
}
