/* Campaign Planner API (app/server.py /api/campaign-planner/*, strategy/campaign_creator):
   Camille's create-campaign flow. Each thinking step is a background job -- the POST returns
   {job_id} and the job's events are read from GET .../events (server-sent events). */

export interface CCStep { step: string; title: string; details: string }

export interface CCOption { label: string; description: string; recommended: boolean }
export interface CCQuestion { id: number | string; question: string; options: CCOption[] }

export type AgentStatus = "active" | "complete" | "skipped" | "error";
export interface CCAgent {
  name: string;
  status: AgentStatus;
  message: string;
  result: string | null;
  source: "ai" | "rules" | null;
  tokens: number;
  reasoning?: string;
  started_at?: string;
  finished_at?: string;
}

interface ItemBase { id: string; at: string }
export type CCItem =
  | (ItemBase & { kind: "user"; text: string; file_name?: string | null })
  | (ItemBase & { kind: "agent"; text: string })
  | (ItemBase & { kind: "progress"; title: string; status: "running" | "done"; steps: CCStep[] })
  | (ItemBase & { kind: "questions"; questions: CCQuestion[]; answered: string | null })
  | (ItemBase & { kind: "assumptions"; assumptions: string[]; resolved: string | null })
  | (ItemBase & {
      kind: "pipeline"; status: "running" | "done"; agents: CCAgent[]; steps: CCStep[];
      feedback: string | null; engine: string; refine: boolean;
    });

export interface BriefingSegment { name: string; hcpSpecialty: string; segmentType: string; details: string[]; messageFocus: string }
export interface Briefing {
  campaignName: string;
  campaignOverview: Record<string, string>;
  keyDecisions: { question: string; decision: string; impact: string }[];
  audienceSegmentation: { rule: string; segments: BriefingSegment[] };
  sfmcCapabilities: { capability: string; use: string }[];
  journeyEntryCriteria: string[];
  designPrinciples: { category: string; principles: string[] }[];
  journeyFlow: { timing: string; stage: string; actions: string }[];
  decisionLogic: { keyQuestion: string; rules: { id: number | string; rule: string }[] };
  operationalRules: string[];
  measurementReporting: { tier: string; metrics: string }[];
  journeyEndGoals: string;
}

/** A Salesforce flow spec as the agents produce it. Its element shapes come from the model, so
 *  the UI reads them defensively. */
export interface FlowSpec {
  flowType?: string;
  triggerObject?: string;
  triggerEvent?: string;
  immediateElements?: Record<string, unknown>[];
  scheduledPaths?: { label?: string; duration?: number | string; unit?: string; elements?: Record<string, unknown>[] }[];
}

export interface Blueprint {
  rationale: unknown;
  planningSummary: Record<string, unknown>;
  technicalDesign: Record<string, unknown>;
  flowQaReport: Record<string, unknown>;
  validation: Record<string, unknown>;
  documentation: Record<string, unknown>;
  spec: FlowSpec;
  mermaid: string;
  tokenUsage: { totalTokens: number };
  sources: Record<string, "ai" | "rules">;
  metadataSource: "org" | "standard";
  metadataObjects: string[];
  specSummary: { elements: Record<string, number>; total: number; scheduled_paths: number };
  generatedAt: string;
  briefingVersion: number | null;
  feedback: string | null;
  engine: string;
}

export interface DeployStep { title: string; status: "active" | "complete" | "error"; details: string }
export interface Deployment {
  flow_name: string;
  label: string;
  status: "running" | "succeeded" | "failed";
  steps: DeployStep[];
  flow_url: string | null;
  deploy_id: string | null;
  errors: string[];
  started_at: string;
  finished_at?: string;
  instance_url?: string | null;
}

export type CCStage = "intake" | "clarifying" | "assumptions" | "briefing" | "blueprint";
export interface CCState {
  stage: CCStage;
  auto_assume: boolean;
  requirements: string;
  typed: string;
  file_name: string | null;
  is_document: boolean;
  questions: CCQuestion[] | null;
  assumptions: string[] | null;
  briefing: Briefing | null;
  briefing_version: number;
  briefing_source: "ai" | "rules" | null;
  briefing_note: string | null;
  blueprint: Blueprint | null;
  blueprint_briefing_version: number | null;
  blueprint_stale: boolean;
  spec: FlowSpec | null;
  deployment: Deployment | null;
  items: CCItem[];
  token_usage: number;
}

export interface CCSession {
  id: string;
  brand: string | null;
  plan_id: number | null;
  campaign_id: number | null;
  title: string;
  artifact_id: string | null;
  created_at: string;
  updated_at: string;
  state: CCState;
  job: { id: string; kind: string } | null;
  llm: { available: boolean; engine: string };
}

export type CCEvent = { seq: number } & (
  | { type: "item"; item: CCItem }
  | { type: "item_update"; item: CCItem }
  | { type: "item_status"; item_id: string; status: "running" | "done" }
  | { type: "progress"; item_id: string; step: CCStep }
  | { type: "agent_start"; item_id: string; agent: CCAgent }
  | { type: "thought"; item_id: string; agent: string; text: string }
  | { type: "agent_done"; item_id: string; agent: CCAgent }
  | { type: "mermaid"; item_id: string; mermaid: string }
  | { type: "briefing"; briefing: Briefing; version: number; source: "ai" | "rules"; note: string | null }
  | { type: "blueprint"; blueprint: Blueprint }
  | { type: "deploy"; deployment: Deployment }
  | { type: "error"; message: string }
  | { type: "done"; status: "ok" | "error" | "cancelled"; session: CCSession | null }
);

export interface SalesforceStatus {
  configured: boolean;
  connected: boolean;
  instance_url: string | null;
  user: { display_name?: string; username?: string; organization_id?: string; email?: string } | null;
}

const enc = encodeURIComponent;
const base = (sid: string) => `/api/campaign-planner/sessions/${enc(sid)}`;

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

export interface JobStarted { job_id: string; kind: string }

export const ccApi = {
  open: (scope: { brand: string | null; plan_id: number | null; campaign_id: number | null }) =>
    send<CCSession>("POST", "/api/campaign-planner/sessions", scope),
  get: (sid: string) => fetch(base(sid)).then((r) => readJSON<CCSession>(r, "load campaign planner")),
  rename: (sid: string, title: string) => send<CCSession>("PATCH", base(sid), { title }),
  analyze: (sid: string, prompt: string, file: File | null, autoAssume: boolean) => {
    const form = new FormData();
    form.append("prompt", prompt);
    form.append("auto_assume", autoAssume ? "true" : "false");
    if (file) form.append("file", file);
    return fetch(`${base(sid)}/analyze`, { method: "POST", body: form }).then((r) => readJSON<JobStarted>(r, "analyze"));
  },
  answers: (sid: string, answers: string) => send<JobStarted>("POST", `${base(sid)}/answers`, { answers }),
  assumptions: (sid: string, mode: "accept" | "resolve", resolved = "") =>
    send<JobStarted>("POST", `${base(sid)}/assumptions`, { mode, resolved }),
  updateBriefing: (sid: string, modifications: string) =>
    send<JobStarted>("POST", `${base(sid)}/briefing/update`, { modifications }),
  briefingVersions: (sid: string) =>
    fetch(`${base(sid)}/briefing/versions`).then((r) => readJSON<{ versions: { version: number; created_at: string; reason: string }[] }>(r, "versions")),
  briefingVersion: (sid: string, v: number) =>
    fetch(`${base(sid)}/briefing/versions/${v}`).then((r) => readJSON<{ version: number; briefing: Briefing }>(r, "version")),
  restoreBriefing: (sid: string, v: number) => send<CCSession>("POST", `${base(sid)}/briefing/restore/${v}`),
  blueprint: (sid: string, feedback?: string) => send<JobStarted>("POST", `${base(sid)}/blueprint`, { feedback: feedback ?? null }),
  deploy: (sid: string) => send<JobStarted>("POST", `${base(sid)}/deploy`),
  reset: (sid: string) => send<CCSession>("POST", `${base(sid)}/reset`),
  cancel: (sid: string) => send<CCSession>("POST", `${base(sid)}/cancel`),
  exportUrl: (sid: string, fmt: "pdf" | "docx") => `${base(sid)}/briefing.${fmt}`,
  packageUrl: (sid: string) => `${base(sid)}/flow-package.zip`,
};

export const sfApi = {
  status: () => fetch("/api/salesforce/status").then((r) => readJSON<SalesforceStatus>(r, "Salesforce status")),
  connectUrl: (returnTo: string) => `/api/salesforce/connect?return_to=${enc(returnTo)}`,
  disconnect: () => send<SalesforceStatus>("POST", "/api/salesforce/disconnect"),
};

/** Read a job's server-sent events from event number `after`. Resolves when the server ends
 *  the stream (after the job's `done` event); rejects on a network error or an HTTP error. */
export async function streamJob(sid: string, jobId: string, after: number, onEvent: (ev: CCEvent) => void,
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
      onEvent(JSON.parse(data) as CCEvent);
    }
  }
}
