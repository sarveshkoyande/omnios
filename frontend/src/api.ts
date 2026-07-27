/** Types + fetch for the existing back-end contract (GET /api/home). */

export interface FeedItem {
  type: string;
  text: string;
  brand?: string;
  icon?: string;
  provenance?: string;
}

export interface Brand {
  brand: string;
  generic: string;
  therapy_area: string;
  indications: string[];
  lifecycle_key: "launch" | "growth" | "mature" | "loe";
  lifecycle_label: string;
  momentum: number;
  trials_recruiting: number;
  trials_total: number;
  pubmed: number;
  competitor_count: number;
  campaigns?: number;
}

export interface ClientGroup {
  client: string;
  brands: Brand[];
}

export interface Dashboard {
  totals?: { brands?: number; clients?: number; recruiting_trials?: number; campaigns?: number };
  library?: {
    claims?: number;
    approved_claims?: number;
    content_assets?: number;
    modules?: number;
    unsubstantiated_claims?: number;
  };
  clients?: ClientGroup[];
}

export interface HomePayload {
  feed: FeedItem[];
  dashboard: Dashboard;
}

export async function fetchHome(): Promise<HomePayload> {
  const res = await fetch("/api/home");
  if (!res.ok) throw new Error(`GET /api/home -> ${res.status}`);
  const data = await res.json();
  return { feed: data.feed ?? [], dashboard: data.dashboard ?? {} };
}

export interface PharmaIntelSummary {
  available: boolean;
  totals: Record<string, number>;
  source_counts: Array<{ source: string; count: number }>;
  evidence_mix: Array<{ label: string; count: number }>;
  top_brands: Array<Record<string, string | number>>;
  message_mix: Array<{ label: string; count: number }>;
}

export interface PharmaIntelArtifactItem {
  id: string;
  title: string;
  subtitle: string;
  url: string;
  content: string;
  metadata: Record<string, string | number>;
}

export interface PharmaIntelArtifacts {
  kind: string;
  value: string;
  title: string;
  items: PharmaIntelArtifactItem[];
}

export type PharmaIntelSection = "totals" | "mix" | "brands" | "sources";

export async function fetchPharmaIntelSummary(section?: PharmaIntelSection): Promise<PharmaIntelSummary> {
  const query = section ? `?section=${section}` : "";
  const res = await fetch(`/api/pharma-intel/summary${query}`);
  if (res.ok) return res.json();

  for (const fallbackPath of ["/static/v2/pharma-intel-summary.json", "/pharma-intel-summary.json"]) {
    const fallback = await fetch(fallbackPath);
    if (fallback.ok) return fallback.json();
  }

  throw new Error(`GET /api/pharma-intel/summary -> ${res.status}`);
}

export async function fetchPharmaIntelArtifacts(kind: string, value = "", limit = 20): Promise<PharmaIntelArtifacts> {
  const params = new URLSearchParams({ kind, limit: String(limit) });
  if (value) params.set("value", value);
  const res = await fetch(`/api/pharma-intel/artifacts?${params.toString()}`);
  if (!res.ok) throw new Error(`GET /api/pharma-intel/artifacts -> ${res.status}`);
  return res.json();
}

export interface CogneeFeedbackItem {
  id: string;
  ts: string;
  topic: string;
  brand: string;
  therapy_area: string;
  request: string;
  observed: string;
  feedback: string;
  expected: string;
  rating: string;
}

export interface CogneeStatus {
  health: { enabled: boolean; graph_ready: boolean | null; note: string };
  topics: Array<{ key: string; query_template: string }>;
  feedback: CogneeFeedbackItem[];
}

export interface CogneeProbeTopic {
  topic: string;
  query: string;
  has_guidance: boolean;
  guidance: string;
  source: string;
  feedback: CogneeFeedbackItem[];
}

export interface CogneeProbe {
  health: CogneeStatus["health"];
  brand: string;
  therapy_area: string;
  enabled: boolean;
  topics: CogneeProbeTopic[];
  elapsed_ms: number;
}

export async function fetchCogneeStatus(): Promise<CogneeStatus> {
  const res = await fetch("/api/cognee/status");
  if (!res.ok) throw new Error(`GET /api/cognee/status -> ${res.status}`);
  return res.json();
}

export async function probeCogneeGrounding(payload: { brand: string; therapy_area: string; topics: string[] }): Promise<CogneeProbe> {
  const res = await fetch("/api/cognee/probe", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`POST /api/cognee/probe -> ${res.status}`);
  return res.json();
}

export async function submitCogneeFeedback(payload: {
  topic: string;
  brand: string;
  therapy_area: string;
  request: string;
  observed: string;
  feedback: string;
  expected: string;
  rating: string;
}): Promise<{ ok: boolean; record: CogneeFeedbackItem; items: CogneeFeedbackItem[] }> {
  const res = await fetch("/api/cognee/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`POST /api/cognee/feedback -> ${res.status}`);
  return res.json();
}

import type {
  BriefExtractItem,
  CampaignPlan,
  BindingsResponse,
  CampaignArtifactsPayload,
  ChatResponse,
  NotificationsResponse,
  NudgeRunResponse,
  OrchestrationSchedule,
  OrchestrationTask,
  PersonaApplyChange,
  PushResponse,
  SyncResponse,
  PersonaDetail,
  PersonaOffer,
  PersonaReview,
  ProjectDetail,
  ProjectSummary,
  ReportingInsights,
} from "./workspace/types";
import type { WorkflowDocument } from "./workspace/stages/operations/flowbuilder/schema/document";
import type { CampaignFlow } from "./workspace/types";

export async function listProjects(): Promise<ProjectSummary[]> {
  const res = await fetch("/api/projects");
  if (!res.ok) throw new Error(`GET /api/projects -> ${res.status}`);
  return res.json();
}

export async function createProject(name: string): Promise<ProjectSummary> {
  const res = await fetch("/api/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error(`POST /api/projects -> ${res.status}`);
  return res.json();
}

export async function getProject(id: string): Promise<ProjectDetail> {
  const res = await fetch(`/api/projects/${encodeURIComponent(id)}`);
  if (!res.ok) throw new Error(`GET /api/projects/${id} -> ${res.status}`);
  return res.json();
}

export async function fetchReportingInsights(projectId: string): Promise<ReportingInsights> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/reporting-insights`);
  if (!res.ok) throw new Error(`GET reporting-insights -> ${res.status}`);
  return res.json();
}

export async function renameProject(id: string, name: string): Promise<ProjectSummary> {
  const res = await fetch(`/api/projects/${encodeURIComponent(id)}/name`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error(`PATCH /api/projects/${id}/name -> ${res.status}`);
  return res.json();
}

export async function deleteProject(id: string): Promise<void> {
  const res = await fetch(`/api/projects/${encodeURIComponent(id)}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`DELETE /api/projects/${id} -> ${res.status}`);
}

export async function postChat(projectId: string, message: string): Promise<ChatResponse> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_id: projectId, message }),
  });
  if (!res.ok) throw new Error(`POST /api/chat -> ${res.status}`);
  return res.json();
}

export interface TabChatMessage {
  role: "user" | "assistant";
  agent_id: string | null;
  text: string;
  kind: string;
  ts: string;
}

export interface TabChatAskResponse {
  reply: string;
  document?: WorkflowDocument | null;
  flow?: CampaignFlow | null;
  /** Orchestration agent: it changed the activity board / sent a nudge — refetch. */
  changed?: boolean;
}

export async function getTabChat(projectId: string, stageId: string): Promise<TabChatMessage[]> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/tab-chat/${stageId}`);
  if (!res.ok) throw new Error(`GET tab-chat/${stageId} -> ${res.status}`);
  return res.json();
}

export async function postTabChat(
  projectId: string,
  stageId: string,
  message: string,
  document?: WorkflowDocument | null,
): Promise<TabChatAskResponse> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/tab-chat/${stageId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, document: document ?? null }),
  });
  if (!res.ok) throw new Error(`POST tab-chat/${stageId} -> ${res.status}`);
  return res.json();
}

export async function fetchPersonaOffer(projectId: string): Promise<PersonaOffer> {
  const res = await fetch(`/api/personas?project_id=${encodeURIComponent(projectId)}`);
  if (!res.ok) throw new Error(`GET /api/personas -> ${res.status}`);
  const data = await res.json();
  return { matched: data.matched ?? [], others: data.others ?? [] };
}

export async function fetchPersonaDetail(personaId: string): Promise<PersonaDetail> {
  const res = await fetch(`/api/personas/${encodeURIComponent(personaId)}`);
  if (!res.ok) throw new Error(`GET /api/personas/${personaId} -> ${res.status}`);
  return res.json();
}

export async function runPersonaReview(projectId: string, personaIds: string[]): Promise<PersonaReview[]> {
  const res = await fetch("/api/persona-review", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_id: projectId, persona_ids: personaIds }),
  });
  if (!res.ok) throw new Error(`POST /api/persona-review -> ${res.status}`);
  const data = await res.json();
  return data.reviews ?? [];
}

export async function applyPersonaFeedback(
  projectId: string,
  personaIds: string[],
): Promise<{ changes: PersonaApplyChange[]; plan_html: string | null; plan_markdown: string | null }> {
  const res = await fetch("/api/persona-apply", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_id: projectId, persona_ids: personaIds }),
  });
  if (!res.ok) throw new Error(`POST /api/persona-apply -> ${res.status}`);
  return res.json();
}

import type { LibraryDetail, LibraryIndex } from "./library/types";

export async function fetchLibraryIndex(): Promise<LibraryIndex> {
  const res = await fetch("/api/library");
  if (!res.ok) throw new Error(`GET /api/library -> ${res.status}`);
  return res.json();
}

export async function fetchLibraryBrand(brand: string): Promise<LibraryDetail> {
  const res = await fetch(`/api/library/${encodeURIComponent(brand)}`);
  if (!res.ok) throw new Error(`GET /api/library/${brand} -> ${res.status}`);
  return res.json();
}

export async function savePlanContent(projectId: string, html: string, markdown: string): Promise<void> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/plan-content`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ html, markdown }),
  });
  if (!res.ok) throw new Error(`POST plan-content -> ${res.status}`);
}

export async function postStudioAnswer(projectId: string, askId: string, value: string): Promise<void> {
  const res = await fetch("/api/studio/answer", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_id: projectId, ask_id: askId, value }),
  });
  if (!res.ok) throw new Error(`POST /api/studio/answer -> ${res.status}`);
}

export interface StudioAutoAssumeResult {
  auto_assume: boolean;
  /** Set when an ask is already sitting on the gate — the caller answers it to get moving. */
  pending_ask_id: string | null;
  pending_value: string;
}

export async function setStudioAutoAssume(projectId: string, enabled: boolean): Promise<StudioAutoAssumeResult> {
  const res = await fetch("/api/studio/auto-assume", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_id: projectId, enabled }),
  });
  if (!res.ok) throw new Error(`POST /api/studio/auto-assume -> ${res.status}`);
  return res.json();
}

export async function saveCampaignFlowDocument(projectId: string, doc: WorkflowDocument): Promise<void> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/campaign-plan-layout`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(doc),
  });
  if (!res.ok) throw new Error(`PATCH campaign-plan-layout -> ${res.status}`);
}

export async function regenerateCampaignFlowDocument(
  projectId: string,
  doc?: WorkflowDocument | null,
): Promise<{
  reply: string;
  document?: WorkflowDocument | null;
  flow?: CampaignFlow | null;
  regenerated?: boolean;
  source?: "ai" | "deterministic-fallback";
}> {
  const body = JSON.stringify({ document: doc ?? null });
  let res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/regenerate-campaign-plan-layout`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  });
  if (res.status === 404) {
    res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/campaign-plan-layout/regenerate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    });
  }
  if (res.status === 404) {
    const fallback = await fetch(`/api/projects/${encodeURIComponent(projectId)}/campaign-plan/generate`, {
      method: "POST",
    });
    if (fallback.ok) {
      const data = await fallback.json();
      return {
        reply: "Diagram rebuilt from the campaign brief and saved plan.",
        flow: data.flow?.flow ?? data.flow ?? null,
        regenerated: true,
        source: "deterministic-fallback",
      };
    }
    return postTabChat(
      projectId,
      "operations",
      "FULL REGENERATION, not an incremental edit: redraw the campaign operations diagram completely from scratch using the campaign brief, saved plan, and this chat context. Return a complete replacement WorkflowDocument.",
      doc ?? null,
    );
  }
  if (!res.ok) throw new Error(`POST regenerate-campaign-plan-layout -> ${res.status}`);
  return res.json();
}

export async function generateOrchestrationTasks(projectId: string, extraContext?: string): Promise<OrchestrationTask[]> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/orchestration-tasks/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ extra_context: extraContext ?? null }),
  });
  if (!res.ok) throw new Error(`POST orchestration-tasks/generate -> ${res.status}`);
  const data = await res.json();
  return data.tasks ?? [];
}

export async function saveOrchestrationTasks(projectId: string, tasks: OrchestrationTask[]): Promise<void> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/orchestration-tasks`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tasks }),
  });
  if (!res.ok) throw new Error(`PATCH orchestration-tasks -> ${res.status}`);
}

export async function getOrchestrationSchedule(
  projectId: string,
  opts?: { goLive?: string; startDate?: string },
): Promise<OrchestrationSchedule> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/orchestration-schedule`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ go_live: opts?.goLive ?? null, start_date: opts?.startDate ?? null }),
  });
  if (!res.ok) throw new Error(`POST orchestration-schedule -> ${res.status}`);
  return res.json();
}

export async function pushOrchestration(
  projectId: string,
  opts?: { teams?: string[]; goLive?: string },
): Promise<PushResponse> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/orchestration/push`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ teams: opts?.teams ?? null, go_live: opts?.goLive ?? null }),
  });
  if (!res.ok) throw new Error(`POST orchestration/push -> ${res.status}`);
  return res.json();
}

export async function getOrchestrationBindings(projectId: string): Promise<BindingsResponse> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/orchestration/bindings`);
  if (!res.ok) throw new Error(`GET orchestration/bindings -> ${res.status}`);
  return res.json();
}

export async function syncOrchestration(projectId: string): Promise<SyncResponse> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/orchestration/sync`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`POST orchestration/sync -> ${res.status}`);
  return res.json();
}

export async function simulateExternalChange(
  projectId: string,
  activityId: string,
  status = "Done",
): Promise<void> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/orchestration/simulate-external`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ activity_id: activityId, status }),
  });
  if (!res.ok) throw new Error(`POST orchestration/simulate-external -> ${res.status}`);
}

export async function getCampaignArtifacts(projectId: string): Promise<CampaignArtifactsPayload> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/campaign-artifacts`);
  if (!res.ok) throw new Error(`GET campaign-artifacts -> ${res.status}`);
  return res.json();
}

export async function runNudges(projectId: string, goLive?: string): Promise<NudgeRunResponse> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/orchestration/nudge/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ go_live: goLive ?? null }),
  });
  if (!res.ok) throw new Error(`POST orchestration/nudge/run -> ${res.status}`);
  return res.json();
}

export async function getNotifications(projectId: string): Promise<NotificationsResponse> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/orchestration/notifications`);
  if (!res.ok) throw new Error(`GET orchestration/notifications -> ${res.status}`);
  return res.json();
}

export async function ackNotification(projectId: string, dedupeKey: string): Promise<void> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/orchestration/notifications/ack`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dedupe_key: dedupeKey }),
  });
  if (!res.ok) throw new Error(`POST notifications/ack -> ${res.status}`);
}

export async function generateCampaignPlan(projectId: string): Promise<CampaignPlan> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/campaign-plan/generate`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`POST campaign-plan/generate -> ${res.status}`);
  const data = await res.json();
  // The endpoint's `flow` key holds the full CampaignPlan (overview/segments/flow/...),
  // not the bare CampaignFlow -- the journey graph lives at .flow.flow.
  return data.flow;
}

export async function extractProjectText(projectId: string, file: File): Promise<{ text: string; filename: string }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/extract-text`, { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `POST extract-text -> ${res.status}`);
  }
  return res.json();
}

export async function closeUpdates(projectId: string): Promise<void> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/close-updates`, { method: "POST" });
  if (!res.ok) throw new Error(`POST close-updates -> ${res.status}`);
}

export interface SfmcPushConfig {
  auth_base_uri: string;
  client_id: string;
  client_secret: string;
  account_id?: string;
  scope?: string;
  entry_data_extension_id?: string;
  entry_event_definition_key?: string;
  email_asset_id?: string;
  sender_profile_id?: string;
  delivery_profile_id?: string;
  schema_version_id?: string;
  fire_test_event?: boolean;
  contact_key?: string;
  contact_key_value?: string;
}

export interface SfmcPushResponse {
  bundle?: unknown;
  token?: unknown;
  journey?: { id?: string; definitionId?: string; version?: number; versionNumber?: number };
  publish?: unknown;
  eventDefinition?: unknown;
  fireEvent?: unknown;
  tokenType?: string;
  journeyId?: string;
  versionNumber?: number;
}

export async function pushSfmcJourney(projectId: string, config: SfmcPushConfig): Promise<SfmcPushResponse> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/export.sfmc.push`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `POST export.sfmc.push -> ${res.status}`);
  }
  return res.json();
}

export async function uploadBriefFile(
  projectId: string,
  file: File,
): Promise<ChatResponse & { reply: string; extracted?: BriefExtractItem[]; filled_count?: number }> {
  const form = new FormData();
  form.append("project_id", projectId);
  form.append("file", file);
  const res = await fetch("/api/upload", { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `POST /api/upload -> ${res.status}`);
  }
  return res.json();
}
