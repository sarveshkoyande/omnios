/** Campaign Ops (2) — sandbox stage types.
 *
 * This stage answers one question: *can we launch, and what is in the way?* Everything here
 * is derived on the client from the plan the earlier stages already produced — there is no
 * new backend endpoint, so nothing outside this folder is affected.
 */

/** The ten build categories. Every touchpoint in the journey generates lines across several. */
export type CategoryId =
  | "creative"
  | "digital"
  | "systems"
  | "data"
  | "approvals"
  | "measurement"
  | "field"
  | "qa"
  | "fulfilment"
  | "access";

export interface CategoryMeta {
  id: CategoryId;
  name: string;
  icon: string;
  /** Which team picks the work up — matches the Stage 2 team roster where it overlaps. */
  team: string;
}

/**
 * What we found when we checked the item against what already exists.
 *
 * `adapt` is the tier that matters and the one the current build has no concept of: the
 * claim is approved and the asset exists, but this campaign needs a new rendition of it,
 * so it still costs work and still needs an (abbreviated) review.
 */
export type Coverage = "reuse" | "adapt" | "build" | "blocked";

/** What review the item has to clear before it can go live. */
export type ReviewPath = "none" | "abbreviated" | "full";

export interface Deliverable {
  id: string;
  category: CategoryId;
  title: string;
  /** Which touchpoint / message / segment in the plan produced this line. */
  source: string;
  channel?: string;
  coverage: Coverage;
  /** Why the coverage check landed where it did — shown verbatim in the UI. */
  coverageReason: string;
  review: ReviewPath;
  effortDays: number;
  owner: string;
}

export interface CategoryRollup {
  meta: CategoryMeta;
  items: Deliverable[];
  reuse: number;
  adapt: number;
  build: number;
  blocked: number;
}

/** One of the 14 setup-run steps. */
export interface RunStep {
  n: number;
  title: string;
  agent: string;
  question: string;
  /** `ready` — we can compute it from data we hold. `needs` — blocked on data the app has
   *  no source for yet (capacity, budget, approval records). See the gaps panel. */
  state: "ready" | "needs";
  needsNote?: string;
}

export interface Risk {
  id: string;
  title: string;
  detail: string;
  severity: "high" | "medium" | "low";
  owner: string;
}

export interface LaunchVerdict {
  status: "on-track" | "at-risk" | "blocked";
  headline: string;
  goLive: string;
  /** Business days of work left once reuse is taken out. */
  remainingDays: number;
  /** Business days available before go-live. */
  availableDays: number;
  projectedOverrunDays: number;
  totals: { total: number; reuse: number; adapt: number; build: number; blocked: number };
  effortSaved: number;
  blockers: { title: string; detail: string }[];
}
