/* Readers for model-returned values, which can come back in any JSON shape. */

/** Any model-returned value as display text: strings as-is, lists joined, objects as
 *  "key: value" pairs -- never "[object Object]". */
export function txt(v: unknown): string {
  if (v === null || v === undefined) return "";
  if (typeof v === "string") return v;
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  if (Array.isArray(v)) return v.map(txt).filter(Boolean).join("; ");
  if (typeof v === "object") {
    return Object.entries(v as Record<string, unknown>).filter(([, x]) => txt(x)).map(([k, x]) => `${k}: ${txt(x)}`).join(" | ");
  }
  return String(v);
}

/** A model-returned list, whatever it came back as. */
export function list(v: unknown): unknown[] {
  if (Array.isArray(v)) return v;
  if (v === null || v === undefined || v === "") return [];
  return [v];
}
