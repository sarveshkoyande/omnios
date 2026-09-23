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

/** The "+" next to Brands in the rail -- creates a new, empty-but-valid brand kit so a
 *  brand-new brand can go straight into the guided kit-update flow. Throws (with the
 *  server's message) on a blank name or a name that's already taken. */
export function createBrand(name: string): Promise<{ brand: string; kit: BrandKit }> {
  return postJSON("/api/brand-kits", { brand: name });
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
