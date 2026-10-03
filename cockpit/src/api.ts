import type { AnyFlow, BrandKit, BrandTree, CampaignArtifactsPayload, CampaignDrift, HierCampaign, HierPlan, HierarchySummary, BrandSummary, JourneyFlow, JourneyFlowOp, JourneyFlowTurnResult, JourneyQuestion, JourneyState, JourneyStepId, JourneyTurnResult } from "./types";

async function getJSON<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`GET ${url} -> ${res.status}`);
  return res.json();
}

async function postJSON<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  if (!res.ok) {
    // FastAPI's HTTPException body is {"detail": "<message>"} -- surface that directly
    // when present (e.g. createBrand's "already exists") instead of a bare status code.
    const detail = await res.json().catch(() => null);
    throw new Error(typeof detail?.detail === "string" ? detail.detail : `POST ${url} -> ${res.status}`);
  }
  return res.json();
}

export function listBrands(): Promise<{ brands: BrandSummary[]; known_territories: string[] }> {
  return getJSON("/api/brand-kits");
}

/** `territory` is the real gate, not a display filter -- the server 404s if this brand
 *  isn't configured for the requested market rather than silently returning a different
 *  territory's content. */
export function refreshPublicSources(brand: string): Promise<{ brand: string; kit: BrandKit }> {
  return postJSON(`/api/brand-kits/${encodeURIComponent(brand)}/public-sources/refresh`, {});
}
export function getCompliance(brand: string): Promise<{ brand: string; profile: Record<string, unknown> | null }> {
  return getJSON(`/api/brand-kits/${encodeURIComponent(brand)}/compliance`);
}
export function proposeKitContent(brand: string, force = false): Promise<{ brand: string; kit: BrandKit }> {
  return postJSON(`/api/brand-kits/${encodeURIComponent(brand)}/propose${force ? "?force=true" : ""}`, {});
}
export function regenerateBigIdea(brand: string): Promise<{ brand: string; kit: BrandKit }> {
  return postJSON(`/api/brand-kits/${encodeURIComponent(brand)}/big-idea`, {});
}
export interface BrandIqSkill { id: string; name: string; does: string; llm: boolean }
export function listBrandIqSkills(): Promise<{ skills: BrandIqSkill[] }> {
  return getJSON(`/api/brand-iq/skills`);
}
export function uploadBrandPlan(brand: string, files: File[], notes: string): Promise<{ filename: string | null; chars: number; has_notes: boolean }> {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  form.append("notes", notes);
  return postForm(`/api/brand-kits/${encodeURIComponent(brand)}/brand-plan`, form);
}
/** Any step-by-step agent's intake: dropped documents + typed notes (strategy/agent_intake.py). */
export function uploadAgentIntake(agent: string, key: string, files: File[], notes: string): Promise<{ files: { name: string; chars: number }[]; has_notes: boolean }> {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  form.append("notes", notes);
  return postForm(`/api/agent-intake/${encodeURIComponent(agent)}/${encodeURIComponent(key)}`, form);
}
export function runBrandIqSkill(brand: string, skill: string): Promise<{ brand: string; skill: string; kit: BrandKit; reasoning: string[] }> {
  return postJSON(`/api/brand-kits/${encodeURIComponent(brand)}/skills/${encodeURIComponent(skill)}`, {});
}
export interface ScoutSkill { id: string; name: string; does: string; view: "market" | "competitive" | "synthesis" }
export interface ScoutReadout { focus: string; started: string; updated?: string; sections: Record<string, Record<string, unknown>>; reasoning: Record<string, string[]>; worklist: number[] }
export function listScoutSkills(): Promise<{ skills: ScoutSkill[] }> {
  return getJSON(`/api/signal-scout/skills`);
}
export function getScout(brand: string): Promise<{ current: ScoutReadout | null; previous: ScoutReadout | null }> {
  return getJSON(`/api/brands/${encodeURIComponent(brand)}/signal-scout`);
}
export function startScout(brand: string, focus: string): Promise<{ current: ScoutReadout; previous: ScoutReadout | null }> {
  return postJSON(`/api/brands/${encodeURIComponent(brand)}/signal-scout/start`, { focus });
}
export function runScoutSkill(brand: string, skill: string): Promise<{ readout: ScoutReadout; reasoning: string[] }> {
  return postJSON(`/api/brands/${encodeURIComponent(brand)}/signal-scout/skills/${encodeURIComponent(skill)}`, {});
}
export function toggleScoutWorklist(brand: string, index: number): Promise<ScoutReadout> {
  return postJSON(`/api/brands/${encodeURIComponent(brand)}/signal-scout/worklist/${index}`, {});
}
export interface AgentStepDef { id: string; name: string; skills: string[] }
export interface AgentAck { mode?: string; understood?: string; question?: string; have?: { what: string; detail?: string }[]; missing?: { what: string; impact?: string }[]; approach?: string[] }
export function getBrandIqSteps(): Promise<{ steps: AgentStepDef[]; skills: BrandIqSkill[] }> {
  return getJSON(`/api/brand-iq/steps`);
}
export function ackBrandIq(brand: string): Promise<AgentAck> {
  return postJSON(`/api/brand-kits/${encodeURIComponent(brand)}/brand-iq/acknowledge`, {});
}
export function resetBrandIq(brand: string): Promise<{ saved_version: string }> {
  return postJSON(`/api/brand-kits/${encodeURIComponent(brand)}/brand-iq/reset`, {});
}
export function listKitVersions(brand: string): Promise<{ versions: string[] }> {
  return getJSON(`/api/brand-kits/${encodeURIComponent(brand)}/versions`);
}
export function restoreKitVersion(brand: string, version: string): Promise<{ brand: string; kit: BrandKit }> {
  return postJSON(`/api/brand-kits/${encodeURIComponent(brand)}/versions/${encodeURIComponent(version)}/restore`, {});
}
export function getScoutSteps(): Promise<{ steps: AgentStepDef[]; skills: ScoutSkill[] }> {
  return getJSON(`/api/signal-scout/steps`);
}
export function ackScout(brand: string, focus: string): Promise<AgentAck> {
  return postJSON(`/api/brands/${encodeURIComponent(brand)}/signal-scout/acknowledge`, { focus });
}
export function publishEngagementPlan(planId: string): Promise<EngagementPlan> {
  return postJSON(`/api/v3/engagement-plans/${encodeURIComponent(planId)}/publish`, {});
}
export function ackEngagement(planId: string): Promise<EngagementPlan> {
  return postJSON(`/api/v3/engagement-plans/${encodeURIComponent(planId)}/agent/acknowledge`, {});
}
export function ackSegmentation(brand: string, text: string): Promise<AgentAck & { audience?: string }> {
  return postJSON(`/api/segmentation-planner/acknowledge`, { brand, text });
}
export function ackAgentForm(agent: string, brand: string, planId: number | null, campaignId: number | null): Promise<AgentAck & { answers: { key: string; label?: string; value: string; source: string }[] }> {
  return postJSON(`/api/v3/agents/${encodeURIComponent(agent)}/acknowledge`, { brand, plan_id: planId, campaign_id: campaignId });
}
/** Live simulation (strategy/live_sim.py). */
export function getLiveSim<T>(brand: string): Promise<T> {
  return getJSON(`/api/live-sim?brand=${encodeURIComponent(brand)}`);
}
export function runLiveSimCheck(brand: string): Promise<unknown> {
  return postJSON("/api/live-sim/check", { brand });
}
export function seedLiveSimDemo(brand: string): Promise<unknown> {
  return postJSON(`/api/live-sim/demo/${encodeURIComponent(brand)}`, {});
}
export function resolveLiveSim(brand: string, updateId: string, action: "apply" | "dismiss"): Promise<unknown> {
  return postJSON(`/api/live-sim/${encodeURIComponent(brand)}/updates/${encodeURIComponent(updateId)}/${action}`, {});
}
export function getClientData(brand: string): Promise<Record<string, unknown>> {
  return getJSON(`/api/brand-kits/${encodeURIComponent(brand)}/client-data`);
}
export function refreshAudienceSources(brand: string): Promise<{ brand: string; kit: BrandKit }> {
  return postJSON(`/api/brand-kits/${encodeURIComponent(brand)}/audience-sources/refresh`, {});
}
export function getBrandKit(brand: string, territory?: string): Promise<{ brand: string; kit: BrandKit }> {
  const q = territory ? `?territory=${encodeURIComponent(territory)}` : "";
  return getJSON(`/api/brand-kits/${encodeURIComponent(brand)}${q}`);
}

/* ---- Agentic Brand Journey (plan U4) ---- */

async function postForm<T>(url: string, form: FormData): Promise<T> {
  const res = await fetch(url, { method: "POST", body: form });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(typeof detail?.detail === "string" ? detail.detail : `POST ${url} -> ${res.status}`);
  }
  return res.json();
}

function journeyUrl(brand: string, rest = ""): string {
  return `/api/brands/${encodeURIComponent(brand)}/journey${rest}`;
}

export function getJourney(brand: string, historyStep?: JourneyStepId): Promise<JourneyState> {
  const q = historyStep ? `?history_step=${encodeURIComponent(historyStep)}` : "";
  return getJSON(journeyUrl(brand, q));
}

export function journeyTurn(brand: string, step: JourneyStepId, message: string): Promise<JourneyTurnResult> {
  return postJSON(journeyUrl(brand, `/${step}/turn`), { message });
}

export function journeyKeep(brand: string, step: JourneyStepId, ids: string[] | "all"): Promise<JourneyState> {
  return postJSON(journeyUrl(brand, `/${step}/keep`), ids === "all" ? { all: true } : { draft_ids: ids });
}

export function journeyUndo(brand: string, step: JourneyStepId, ids: string[]): Promise<JourneyState> {
  return postJSON(journeyUrl(brand, `/${step}/undo`), { draft_ids: ids });
}

export function journeyConfirm(brand: string, step: JourneyStepId): Promise<JourneyState> {
  return postJSON(journeyUrl(brand, `/${step}/confirm`), {});
}

export function journeyReopen(brand: string, step: JourneyStepId): Promise<JourneyState> {
  return postJSON(journeyUrl(brand, `/${step}/reopen`), {});
}

export function startJourney(opts: { file?: File | null; description?: string; name?: string }):
    Promise<{ brand: string; changed_steps: JourneyStepId[]; question: JourneyQuestion | null; state: JourneyState }> {
  const form = new FormData();
  if (opts.file) form.set("file", opts.file);
  if (opts.description) form.set("description", opts.description);
  if (opts.name) form.set("name", opts.name);
  return postForm("/api/brands/journey/start", form);
}

export function journeyDocument(brand: string, file: File): Promise<{ brand: string; changed_steps: JourneyStepId[]; state: JourneyState }> {
  const form = new FormData();
  form.set("file", file);
  return postForm(journeyUrl(brand, "/document"), form);
}

export function getJourneyFlow(brand: string): Promise<JourneyFlow> {
  return getJSON(journeyUrl(brand, "/flow"));
}

export function buildJourneyFlow(brand: string, campaignId?: number): Promise<JourneyFlow> {
  return postJSON(journeyUrl(brand, "/flow/build"), campaignId ? { campaign_id: campaignId } : {});
}

export function createCampaign(planId: number, name: string, startDate?: string | null, endDate?: string | null): Promise<HierCampaign> {
  return postJSON(`/api/engagement-plans/${planId}/campaigns`, { name, start_date: startDate || null, end_date: endDate || null });
}

export function scheduleCampaign(campaignId: number, startDate: string | null, endDate: string | null): Promise<HierCampaign> {
  return sendJSON("PATCH", `/api/campaigns/${campaignId}/schedule`, { start_date: startDate, end_date: endDate });
}

/* ---- Flow step edits (plan U7): chat -> structured ops draft -> keep / undo ---- */
export function journeyFlowTurn(brand: string, body: { message?: string; ops?: JourneyFlowOp[] }): Promise<JourneyFlowTurnResult> {
  return postJSON(journeyUrl(brand, "/flow/turn"), body);
}

export function journeyFlowKeep(brand: string): Promise<JourneyState> {
  return postJSON(journeyUrl(brand, "/flow/keep"), {});
}

export function journeyFlowUndo(brand: string): Promise<JourneyState> {
  return postJSON(journeyUrl(brand, "/flow/undo"), {});
}

export function getCampaignDrift(campaignId: number): Promise<CampaignDrift> {
  return getJSON(`/api/campaigns/${campaignId}/drift`);
}

export function refreshCampaignSnapshot(campaignId: number): Promise<CampaignDrift> {
  return postJSON(`/api/campaigns/${campaignId}/refresh-snapshot`, {});
}

async function sendJSON<T>(method: string, url: string, body: unknown): Promise<T> {
  const res = await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body ?? {}) });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(typeof detail?.detail === "string" ? detail.detail : `${method} ${url} -> ${res.status}`);
  }
  return res.json();
}

/* ---- Brand > Engagement Plan > Campaign > Flow ---- */
const enc = encodeURIComponent;

export function getBrandTree(brand: string): Promise<BrandTree> {
  return getJSON(`/api/brands/${enc(brand)}/tree`);
}

export function getHierarchySummary(): Promise<HierarchySummary> {
  return getJSON("/api/hierarchy/summary");
}

/** The Briefing Agent's source of truth: strategy/campaign_artifacts.py's deterministic
 *  Campaign Strategy + Campaign Brief, composed from the Planning stage's saved ctx. Only
 *  reachable for a campaign whose `project_id` is set (it ran through the old Project
 *  Studio's Stage 1) -- the caller checks that before calling this. */
export function getCampaignArtifacts(projectId: string): Promise<CampaignArtifactsPayload> {
  return getJSON(`/api/projects/${enc(projectId)}/campaign-artifacts`);
}

/* ---- Old Project Studio's Stage 1 (strategy/conversation.py + strategy/studio_run.py) --
   reachable from the Briefing Agent when a campaign has no plan yet. Real endpoints, not a
   parallel implementation: the same /api/projects, /api/chat, /api/studio/stream (SSE) and
   /api/studio/answer the old Studio pages themselves use. ---- */

export interface StudioProject {
  id: string;
  name: string;
  messages: { role: string; text: string; meta?: Record<string, unknown> }[];
  state: Record<string, unknown>;
}
export function createProject(name: string): Promise<StudioProject> {
  return postJSON("/api/projects", { name });
}

export interface BriefChatResult {
  reply: string;
  action: "ask" | "run" | string;
  phase: string;
}
/** The free-text brief-capture loop (brand/budget/lifecycle/etc.) that runs before Stage 1's
 *  own question sequence can start -- `action` flips to "run" the moment enough is captured. */
export function postBriefChat(projectId: string, message: string): Promise<BriefChatResult> {
  return postJSON("/api/chat", { project_id: projectId, message });
}

export function postStudioAnswer(projectId: string, askId: string, value: string): Promise<{ ok: boolean }> {
  return postJSON("/api/studio/answer", { project_id: projectId, ask_id: askId, value });
}

export function createPlan(brand: string, body: { name: string; period_start?: string | null; period_end?: string | null }): Promise<HierPlan> {
  return postJSON(`/api/brands/${enc(brand)}/engagement-plans`, body);
}

export function updatePlan(planId: number, body: Partial<Pick<HierPlan, "name" | "period_start" | "period_end" | "status">>): Promise<HierPlan> {
  return sendJSON("PATCH", `/api/engagement-plans/${planId}`, body);
}

export function renameCampaign(campaignId: number, name: string): Promise<HierCampaign> {
  return sendJSON("PATCH", `/api/campaigns/${campaignId}`, { name });
}

export function startCampaignPlan(campaignId: number): Promise<{ campaign: HierCampaign; project: { id: string } }> {
  return postJSON(`/api/campaigns/${campaignId}/campaign-plan`, {});
}

export function createFlow(campaignId: number, name: string): Promise<AnyFlow> {
  return postJSON(`/api/campaigns/${campaignId}/flows`, { name });
}

export function getFlow(flowId: number): Promise<AnyFlow> {
  return getJSON(`/api/flows/${flowId}`);
}

export function buildFlow(flowId: number): Promise<AnyFlow> {
  return postJSON(`/api/flows/${flowId}/build`, {});
}

export function flowTurn(flowId: number, body: { message?: string; ops?: JourneyFlowOp[] }): Promise<JourneyFlowTurnResult> {
  return postJSON(`/api/flows/${flowId}/turn`, body);
}

export function flowAction(flowId: number, action: "keep" | "undo" | "confirm" | "reopen"): Promise<AnyFlow> {
  return postJSON(`/api/flows/${flowId}/${action}`, {});
}

/* ---- Flow Planner chat editing (strategy/flow_sop/editor.py, ported from
   scripts/flow_editor.py) -- "talk to the diagram" ops on top of the SOP generator. ---- */

export function flowSopChatOpening(campaignId: number, audience = "HCP"): Promise<{ reply: string }> {
  return getJSON(`/api/campaigns/${campaignId}/flow-sop/chat/opening?audience=${enc(audience)}`);
}

export interface FlowSopChatResult {
  reply: string;
  action: string;
  ops: Record<string, unknown>[];
  history: string[];
  svg: string;
}

export function flowSopChat(campaignId: number, body: {
  message: string; audience?: string; ops: Record<string, unknown>[]; history: string[];
}): Promise<FlowSopChatResult> {
  return postJSON(`/api/campaigns/${campaignId}/flow-sop/chat`, body);
}

/* ---- Redesign Ask bar: LLM-only agent routing (strategy/agent_router.py). A 503 means no
   LLM is reachable -- callers show that plainly rather than guessing. ---- */
export interface AskRouteResult { agent_ids: string[]; reply: string }
export function routeAsk(body: {
  question: string;
  brand: string | null;
  agents: { id: string; name: string; summary: string; available: boolean }[];
}): Promise<AskRouteResult> {
  return postJSON("/api/v3/route-ask", body);
}

/* ---- Redesign workspace: framework-driven input cards (strategy/agent_forms.py) ---- */
export interface FormDataPoint {
  key: string;
  label: string;
  source: "internal" | "external" | "user" | string;
  derivation: "derive" | "confirm" | "ask" | string;
  value: string | null;
  options: string[];
  recommendation: string | null;
}
export interface FormStage {
  id: string;
  name: string;
  decision: string;
  framework: string;
  how: string;
  feeds: string[];
  data_points: FormDataPoint[];
}
export interface AgentForm {
  framework: { id: string; name: string; derivation_meaning: Record<string, string> } | null;
  stages: FormStage[];
}
export function getAgentForm(agentId: string, brand: string, planId?: number | null, campaignId?: number | null): Promise<AgentForm> {
  const q = new URLSearchParams({ brand });
  if (planId) q.set("plan_id", String(planId));
  if (campaignId) q.set("campaign_id", String(campaignId));
  return getJSON(`/api/v3/agents/${enc(agentId)}/form?${q}`);
}

/* ---- Redesign Phase 4: typed, versioned artifacts (strategy/v3_artifacts.py) ---- */
export interface ArtifactField { id: string; label: string; value: string; source: string; needs_input: boolean }
export interface ArtifactSection { id: string; title: string; fields: ArtifactField[] }
export interface V3Artifact {
  id: string; type: string; agent: string; brand: string; plan_id: number | null; campaign_id: number | null;
  title: string; created_at: string; updated_at: string;
  version: number; version_reason: string; version_created_at: string;
  inputs: Record<string, { label: string; derivation: string; value: string | null; confirmed: boolean }>;
  extras: { id?: string; label: string; value: string }[];
  artifact: { type: string; schema_version: number; sections: ArtifactSection[] };
}
export interface V3ArtifactSummary {
  id: string; type: string; agent: string; brand: string; plan_id: number | null; campaign_id: number | null;
  title: string; updated_at: string; version: number;
}
export function generateArtifact(body: {
  agent: string; brand: string; plan_id: number | null; campaign_id: number | null; title: string;
  inputs: V3Artifact["inputs"]; extras: V3Artifact["extras"];
}): Promise<V3Artifact> {
  return postJSON("/api/v3/artifacts", body);
}
export function findArtifact(agent: string, brand: string, campaignId: number | null): Promise<{ artifacts: V3Artifact[] }> {
  const q = new URLSearchParams({ agent, brand });
  if (campaignId) q.set("campaign_id", String(campaignId));
  return getJSON(`/api/v3/artifacts?${q}`);
}
export function listArtifacts(brand?: string | null): Promise<{ artifacts: V3ArtifactSummary[] }> {
  return getJSON(`/api/v3/artifacts${brand ? `?brand=${enc(brand)}` : ""}`);
}
export function getArtifact(id: string, version?: number): Promise<V3Artifact> {
  return getJSON(`/api/v3/artifacts/${enc(id)}${version ? `?version=${version}` : ""}`);
}
export async function editArtifact(id: string, changes: Record<string, string>): Promise<V3Artifact> {
  const res = await fetch(`/api/v3/artifacts/${enc(id)}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ changes }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(typeof detail?.detail === "string" ? detail.detail : `PATCH artifact -> ${res.status}`);
  }
  return res.json();
}
export function artifactVersions(id: string): Promise<{ versions: { version: number; created_at: string; reason: string }[] }> {
  return getJSON(`/api/v3/artifacts/${enc(id)}/versions`);
}
export function restoreArtifact(id: string, version: number): Promise<V3Artifact> {
  return postJSON(`/api/v3/artifacts/${enc(id)}/restore/${version}`, {});
}

/* ---- Redesign Phase 5: Refine, Check guidelines, Chat, exports (strategy/v3_assist.py) ---- */
export interface RefineChange { field_id: string; label: string; old_value: string; new_value: string; why: string }
export function refineArtifact(id: string, instruction: string): Promise<{ reply: string; changes: RefineChange[] }> {
  return postJSON(`/api/v3/artifacts/${enc(id)}/refine`, { instruction });
}
export async function applyRefinement(id: string, changes: Record<string, string>, reason: string): Promise<V3Artifact> {
  const res = await fetch(`/api/v3/artifacts/${enc(id)}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ changes, reason }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(typeof detail?.detail === "string" ? detail.detail : `PATCH artifact -> ${res.status}`);
  }
  return res.json();
}
export interface GuidelineIssue { field_id: string; label: string; severity: "high" | "medium" | "low"; issue: string; suggestion: string }
export interface GuidelineCheck { summary: string; issues: GuidelineIssue[]; needs_input: { field_id: string; label: string }[] }
export function checkArtifact(id: string): Promise<GuidelineCheck> {
  return postJSON(`/api/v3/artifacts/${enc(id)}/check`, {});
}
export function artifactCsvUrl(id: string, version?: number): string {
  return `/api/v3/artifacts/${enc(id)}/export.csv${version ? `?version=${version}` : ""}`;
}
export function chatAsk(body: {
  question: string; brand: string | null;
  agents: { id: string; name: string; summary: string; available: boolean }[];
}): Promise<{ reply: string; agent_ids: string[] }> {
  return postJSON("/api/v3/chat", body);
}

export function getStudioProject(id: string): Promise<StudioProject> {
  return getJSON(`/api/projects/${enc(id)}`);
}

/* ---- Engagement plans (docs/redesign/engagement-plan.md): next N months for one brand ---- */
export interface EngagementPlan {
  id: string; brand: string; industry: string; title: string;
  period_start: string; period_end: string; months: number; status: string;
  brand_iq_plan: string | null; created_at: string; updated_at: string;
  version: number; version_reason?: string; version_at?: string;
  /** True when the brand's active Brand IQ plan has changed since this plan was built. */
  stale?: boolean;
  body?: Record<string, unknown>;
}
export function getEngagementFramework(archetype?: string): Promise<Record<string, unknown>> {
  return getJSON(`/api/v3/engagement/framework${archetype ? `?archetype=${archetype}` : ""}`);
}
export function createEngagementPlan(body: { brand: string; months?: number; start?: string; title?: string }): Promise<EngagementPlan> {
  return postJSON("/api/v3/engagement-plans", body);
}
export function listEngagementPlans(brand?: string): Promise<{ plans: EngagementPlan[] }> {
  return getJSON(`/api/v3/engagement-plans${brand ? `?brand=${encodeURIComponent(brand)}` : ""}`);
}
export function getEngagementPlan(id: string, version?: number): Promise<EngagementPlan> {
  return getJSON(`/api/v3/engagement-plans/${id}${version ? `?version=${version}` : ""}`);
}
export async function saveEngagementPlan(id: string, body: Record<string, unknown>, reason: string, meta?: Record<string, unknown>): Promise<EngagementPlan> {
  const r = await fetch(`/api/v3/engagement-plans/${id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ body, reason, meta }) });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}
export function engagementPlanVersions(id: string): Promise<{ versions: { version: number; created_at: string; reason: string }[] }> {
  return getJSON(`/api/v3/engagement-plans/${id}/versions`);
}
export function restoreEngagementPlan(id: string, version: number): Promise<EngagementPlan> {
  return postJSON(`/api/v3/engagement-plans/${id}/restore/${version}`, {});
}
/* Engagement Planner agent v2 steps (strategy/engagement_agent.py). A 503 means the model was
   unreachable and nothing was guessed; the message says so. */
const epStep = (id: string, step: string, body: unknown = {}): Promise<EngagementPlan> => postJSON(`/api/v3/engagement-plans/${id}/agent/${step}`, body);
export const engagementRead = (id: string) => epStep(id, "read");
export const engagementClassify = (id: string, override?: Record<string, string>) => epStep(id, "classify", { override: override ?? null });
export const engagementDiagnose = (id: string) => epStep(id, "diagnose");
export const engagementOptions = (id: string, answers: Record<string, string>) => epStep(id, "options", { answers });
export const engagementChoose = (id: string, ids: string[], note?: string) => epStep(id, "choose", { ids, note: note ?? null });
export const engagementDraft = (id: string) => epStep(id, "draft");
export const engagementCheck = (id: string) => epStep(id, "check");
