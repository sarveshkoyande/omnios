import type { BrandKit, BrandSummary, KitDraft, KitUpdateSection } from "./types";

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

/** Cockpit has no multi-project model -- one workspace per brand -- so the brand name
 *  itself doubles as the project_id the backend's generic (project_id, brand, section)
 *  draft/chat keys expect. */
function projectIdFor(brand: string): string {
  return brand;
}

export function listBrands(): Promise<{ brands: BrandSummary[]; known_territories: string[] }> {
  return getJSON("/api/brand-kits");
}

/** New Brand setup, step 1: upload a brand-plan document and let the agent read the
 *  brand name off it instead of asking the user to type it blind. Returns "" (not an
 *  error) when the LLM can't determine a name -- the caller falls back to a manual
 *  text field. */
export async function inferBrandName(file: File): Promise<{ name: string }> {
  const form = new FormData();
  form.set("file", file);
  const res = await fetch("/api/brand-kits/infer-name", { method: "POST", body: form });
  if (!res.ok) throw new Error(`infer-name -> ${res.status}`);
  return res.json();
}

/** New Brand setup's hidden "generate one for me" escape hatch -- fabricates a complete
 *  fictional brand-plan document (name + text) for when the user doesn't have a real one
 *  handy. Throws if the LLM is unavailable; the caller should let the user upload a real
 *  file instead. */
export async function generateRandomBrandPlan(): Promise<{ name: string; text: string }> {
  const res = await fetch("/api/brand-kits/generate-random", { method: "POST" });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(typeof detail?.detail === "string" ? detail.detail : `generate-random -> ${res.status}`);
  }
  return res.json();
}

/** New Brand setup, step 2 (final): creates the brand scoped to the confirmed
 *  territory and immediately ingests the same document against all 5 kit-update
 *  sections, so the guided screen the user lands on already has drafts waiting. */
export async function setupBrand(file: File, name: string, territory: string): Promise<{ brand: string; sections: KitDraft[] }> {
  const form = new FormData();
  form.set("file", file);
  form.set("name", name);
  form.set("territory", territory);
  const res = await fetch("/api/brand-kits/setup", { method: "POST", body: form });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(typeof detail?.detail === "string" ? detail.detail : `setup -> ${res.status}`);
  }
  return res.json();
}

/** `territory` is the real gate, not a display filter -- the server 404s if this brand
 *  isn't configured for the requested market rather than silently returning a different
 *  territory's content. */
export function getBrandKit(brand: string, territory?: string): Promise<{ brand: string; kit: BrandKit }> {
  const q = territory ? `?territory=${encodeURIComponent(territory)}` : "";
  return getJSON(`/api/brand-kits/${encodeURIComponent(brand)}${q}`);
}

export function sampleKitPdfUrl(brand: string): string {
  return `/api/brand-kits/${encodeURIComponent(brand)}/sample-pdf`;
}

export function getKitUpdateState(brand: string): Promise<{ brand: string; sections: KitDraft[] }> {
  return getJSON(`/api/projects/${encodeURIComponent(projectIdFor(brand))}/kit-update/${encodeURIComponent(brand)}`);
}

export async function ingestKitUpdate(brand: string, opts: { useSample: true } | { file: File }): Promise<{ sections: KitDraft[] }> {
  const form = new FormData();
  if ("useSample" in opts) {
    form.set("use_sample", "true");
  } else {
    form.set("file", opts.file);
  }
  const res = await fetch(`/api/projects/${encodeURIComponent(projectIdFor(brand))}/kit-update/${encodeURIComponent(brand)}/ingest`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(`ingest -> ${res.status}`);
  return res.json();
}

export function askKitUpdate(brand: string, section: KitUpdateSection, message: string): Promise<{ reply: string; diff: KitDraft["diff"] }> {
  return postJSON(
    `/api/projects/${encodeURIComponent(projectIdFor(brand))}/kit-update/${encodeURIComponent(brand)}/${section}/ask`,
    { message });
}

export function publishKitUpdate(brand: string, section: KitUpdateSection, acceptedFields: string[]): Promise<KitDraft> {
  return postJSON(
    `/api/projects/${encodeURIComponent(projectIdFor(brand))}/kit-update/${encodeURIComponent(brand)}/${section}/publish`,
    { accepted_fields: acceptedFields });
}
