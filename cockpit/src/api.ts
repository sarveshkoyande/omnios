import type { AnyFlow, BrandKit, BrandTree, CampaignDrift, HierCampaign, HierPlan, HierarchySummary, BrandSummary, JourneyFlow, JourneyFlowOp, JourneyFlowTurnResult, JourneyQuestion, JourneyState, JourneyStepId, JourneyTurnResult } from "./types";

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
