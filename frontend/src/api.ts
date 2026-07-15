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

import type {
  CampaignSetup,
  ChatResponse,
  PersonaApplyChange,
  PersonaDetail,
  PersonaOffer,
  PersonaReview,
  ProjectDetail,
  ProjectSummary,
  RaciRow,
} from "./workspace/types";

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

export async function postChat(projectId: string, message: string): Promise<ChatResponse> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_id: projectId, message }),
  });
  if (!res.ok) throw new Error(`POST /api/chat -> ${res.status}`);
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

export async function getSetup(projectId: string): Promise<CampaignSetup> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/setup`);
  if (!res.ok) throw new Error(`GET setup -> ${res.status}`);
  return res.json();
}

export async function saveSetup(projectId: string, setup: CampaignSetup): Promise<CampaignSetup> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/setup`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(setup),
  });
  if (!res.ok) throw new Error(`PUT setup -> ${res.status}`);
  return res.json();
}

export async function generateRaci(projectId: string): Promise<{ raci: RaciRow[] }> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/setup/raci`, { method: "POST" });
  if (!res.ok) throw new Error(`POST setup/raci -> ${res.status}`);
  return res.json();
}

export async function generateBrd(projectId: string): Promise<{ markdown: string; generated_at: string }> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/setup/brd`, { method: "POST" });
  if (!res.ok) throw new Error(`POST setup/brd -> ${res.status}`);
  return res.json();
}

export async function closeUpdates(projectId: string): Promise<void> {
  const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/close-updates`, { method: "POST" });
  if (!res.ok) throw new Error(`POST close-updates -> ${res.status}`);
}

export async function uploadBriefFile(
  projectId: string,
  file: File,
): Promise<ChatResponse & { reply: string }> {
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
