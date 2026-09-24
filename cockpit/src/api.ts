import type { BrandKit, BrandSummary, JourneyFlow, JourneyFlowOp, JourneyFlowTurnResult, JourneyQuestion, JourneyState, JourneyStepId, JourneyTurnResult } from "./types";

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

export function createCampaign(planId: number, name: string): Promise<{ id: number; name: string }> {
  return postJSON(`/api/engagement-plans/${planId}/campaigns`, { name });
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
