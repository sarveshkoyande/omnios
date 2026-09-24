import type { BrandKit, JourneyDraft } from "../../types";

/** Pure helpers shared by the journey canvases (kept out of component files for fast refresh). */

export function hasValue(v: unknown): boolean {
  if (v === null || v === undefined) return false;
  if (typeof v === "string") return v.trim() !== "";
  if (Array.isArray(v)) return v.length > 0;
  if (typeof v === "object") return Object.values(v as object).some(hasValue);
  return true;
}

export function draftsFor(drafts: JourneyDraft[], field: string): JourneyDraft[] {
  return drafts.filter((d) => d.field === field);
}

export interface KitFlag {
  key: string;
  label: string;
}

export function isUnbranded(kit: BrandKit | null): boolean {
  return String(kit?.branded ?? "").toLowerCase() === "unbranded";
}

/** Kit content the agent could not support (R15): a required item with no kept value and
 *  no pending draft is flagged rather than guessed. The user supplies it via chat or
 *  dismisses the flag; Confirm stays disabled until every flag is resolved. */
export function kitFlags(kit: BrandKit | null, drafts: JourneyDraft[]): KitFlag[] {
  const flags: KitFlag[] = [];
  const pending = (k: string) => drafts.some((d) => d.field === k);
  const g = kit?.guardrails;
  if (!pending("guardrails")) {
    if (!hasValue(g?.dos)) flags.push({ key: "guardrails.dos", label: "No compliance dos are supported yet" });
    if (!hasValue(g?.donts)) flags.push({ key: "guardrails.donts", label: "No compliance don'ts are supported yet" });
  }
  if (!isUnbranded(kit)) {
    if (!hasValue(kit?.approved_indication) && !pending("approved_indication"))
      flags.push({ key: "approved_indication", label: "Approved indication wording is not supported by anything provided" });
    if (!hasValue(kit?.safety_reference) && !pending("safety_reference"))
      flags.push({ key: "safety_reference", label: "Safety reference is not supported by anything provided" });
  }
  return flags;
}
