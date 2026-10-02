/* Segmentation Planner API (app/server.py /api/segmentation-planner/*, strategy/segmentation):
   Camille's Segmentation Agent. Plain steps return the session; the thinking steps (writing the
   SQL, sizing and creating the segment) return {job_id} and stream from GET .../events. */

export interface SegStep { step: string; title: string; details: string }

export type CountStatus = "ok" | "zero" | "unknown" | "unavailable";

interface ItemBase { id: string; at: string }
export type SegItem =
  | (ItemBase & { kind: "user"; text: string })
  | (ItemBase & { kind: "consent"; text: string; options: string[]; answered: string[] | null; closed?: boolean })
  | (ItemBase & { kind: "progress"; title: string; status: "running" | "done"; steps: SegStep[] })
  | (ItemBase & {
      kind: "sql"; segmentName: string; segmentDescription: string; sql: string; explanation: string;
      source: "ai" | "rules"; note: string | null; healed: string[]; problems: string[];
      /** Conditions on a value the dataset doesn't have (they can only match nobody). */
      warnings?: string[];
    })
  | (ItemBase & { kind: "name"; suggested: string; text: string; answered: string | null; reason: string | null; closed?: boolean })
  | (ItemBase & { kind: "count"; count: number | null; status: CountStatus; note: string | null; answered: { proceed: boolean } | null })
  | (ItemBase & {
      kind: "success"; segmentId: string; segmentName: string; segmentUrl: string | null; published: boolean;
      publishError: string | null; developerName: string; count: number | null;
    });

export interface Pending {
  segmentName: string;
  segmentDescription: string;
  sql: string;
  explanation: string;
  source: "ai" | "rules";
  note: string | null;
  healed: string[];
  problems: string[];
  warnings?: string[];
  sql_item: string;
  name: string | null;
  count: number | null;
  count_status: CountStatus | null;
  count_note: string | null;
  profile_source: "data_cloud" | "snapshot";
}

export interface CreatedSegment {
  segmentId: string;
  segmentName: string;
  segmentUrl: string | null;
  published: boolean;
  publishError: string | null;
  developerName: string;
  segmentDescription: string;
  sql: string;
  count: number | null;
  created_at: string;
}

export type SegStage = "ready" | "consent" | "naming" | "confirm";
export interface SegState {
  stage: SegStage;
  query: string | null;
  consent: string[] | null;
  enriched_query: string | null;
  pending: Pending | null;
  segments: CreatedSegment[];
  items: SegItem[];
  token_usage: number;
}

export interface SegSession {
  id: string;
  brand: string | null;
  plan_id: number | null;
  campaign_id: number | null;
  title: string;
  created_at: string;
  updated_at: string;
  state: SegState;
  job: { id: string; kind: string } | null;
  llm: { available: boolean; engine: string };
  datacloud: { configured: boolean; mode?: "live" | "local" };
}

export type SegEvent = { seq: number } & (
  | { type: "item"; item: SegItem }
  | { type: "item_update"; item: SegItem }
  | { type: "progress"; item_id: string; step: SegStep }
  | { type: "error"; message: string }
  | { type: "done"; status: "ok" | "error" | "cancelled"; session: SegSession | null }
);

export interface DatasetColumn {
  name: string;
  type: string;
  kind: "identifier" | "text" | "number" | "date";
  description: string;
  values: string[] | null;
  range: [string, string] | null;
}
export interface Dataset {
  dmo: string;
  source: "data_cloud" | "snapshot";
  profiled_at: string | null;
  row_count: number | null;
  columns: DatasetColumn[];
}

export interface JobStarted { job_id: string; kind: string }

const enc = encodeURIComponent;
const base = (sid: string) => `/api/segmentation-planner/sessions/${enc(sid)}`;

async function readJSON<T>(res: Response, what: string): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(typeof body?.detail === "string" ? body.detail : `${what} -> ${res.status}`);
  }
  return res.json();
}

function send<T>(method: string, url: string, body?: unknown): Promise<T> {
  return fetch(url, {
    method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body ?? {}),
  }).then((r) => readJSON<T>(r, `${method} ${url}`));
}

export const segApi = {
  open: (scope: { brand: string | null; plan_id: number | null; campaign_id: number | null }) =>
    send<SegSession>("POST", "/api/segmentation-planner/sessions", scope),
  get: (sid: string) => fetch(base(sid)).then((r) => readJSON<SegSession>(r, "load segmentation planner")),
  rename: (sid: string, title: string) => send<SegSession>("PATCH", base(sid), { title }),
  query: (sid: string, text: string) => send<SegSession>("POST", `${base(sid)}/query`, { text }),
  consent: (sid: string, values: string[]) => send<JobStarted>("POST", `${base(sid)}/consent`, { values }),
  name: (sid: string, name: string) => send<JobStarted>("POST", `${base(sid)}/name`, { name }),
  create: (sid: string) => send<JobStarted>("POST", `${base(sid)}/create`),
  discard: (sid: string) => send<SegSession>("POST", `${base(sid)}/discard`),
  reset: (sid: string) => send<SegSession>("POST", `${base(sid)}/reset`),
  cancel: (sid: string) => send<SegSession>("POST", `${base(sid)}/cancel`),
  dataset: (refresh = false) =>
    fetch(`/api/segmentation-planner/dataset${refresh ? "?refresh=true" : ""}`).then((r) => readJSON<Dataset>(r, "dataset")),
};

/** Read a step's server-sent events from event number `after`. Resolves when the server ends
 *  the stream (after the step's `done` event); rejects on a network or HTTP error. */
export async function streamJob(sid: string, jobId: string, after: number, onEvent: (ev: SegEvent) => void,
  signal: AbortSignal): Promise<void> {
  const res = await fetch(`${base(sid)}/events?job_id=${enc(jobId)}&after=${after}`, { signal, headers: { Accept: "text/event-stream" } });
  if (!res.ok || !res.body) {
    const body = await res.json().catch(() => null);
    throw new Error(typeof body?.detail === "string" ? body.detail : `events -> ${res.status}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    let end: number;
    while ((end = buffer.indexOf("\n\n")) !== -1) {
      const message = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      const data = message.split("\n").filter((l) => l.startsWith("data:")).map((l) => l.slice(5).replace(/^ /, "")).join("\n");
      if (!data) continue; // heartbeat comment
      onEvent(JSON.parse(data) as SegEvent);
    }
  }
}
