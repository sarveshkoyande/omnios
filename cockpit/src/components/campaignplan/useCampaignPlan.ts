import { useCallback, useEffect, useRef, useState } from "react";
import type { ChatResponse, ClarifyPayload, ProjectDetail, Slots } from "@omni-frontend/workspace/types";
import type { GroundingItem, StudioAsk, StudioEvent, StudioSection } from "@omni-frontend/workspace/studio/studioTypes";

/** One entry in the Campaign Plan conversation. */
export type PlanChatItem =
  | { id: string; kind: "user" | "agent"; text: string; clarify?: ClarifyPayload | null }
  | { id: string; kind: "status"; text: string }
  | { id: string; kind: "ask"; ask: StudioAsk; answered: string | null };

/** The section being worked on right now (Studio run). */
export interface ActiveSection {
  num: number;
  title: string;
  state: "ground" | "ask" | "draft";
  grounding: GroundingItem[];
  note?: string;
}

let seq = 0;
const nid = () => `cp-${++seq}`;

async function json<T>(res: Response, what: string): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(typeof body?.detail === "string" ? body.detail : `${what} -> ${res.status}`);
  }
  return res.json();
}

/** The Campaign Plan's planning stage, natively in the Cockpit: the brief captured through
 *  chat (/api/chat), then the section-by-section Studio run (/api/studio/stream) whose asks
 *  are answered through /api/studio/answer. Mirrors frontend/'s useWorkspace Stage 1 logic
 *  without its UI. */
export function useCampaignPlan(projectId: string) {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [slots, setSlots] = useState<Slots | null>(null);
  const [items, setItems] = useState<PlanChatItem[]>([]);
  const [sections, setSections] = useState<StudioSection[]>([]);
  const [planHtml, setPlanHtml] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [active, setActive] = useState<ActiveSection | null>(null);
  const [running, setRunning] = useState(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [hasResult, setHasResult] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  const push = useCallback((item: PlanChatItem) => setItems((prev) => [...prev, item]), []);

  const closeStream = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
  }, []);

  const apply = useCallback((ev: StudioEvent) => {
    switch (ev.type) {
      case "run_open":
        setTotal(ev.total_sections);
        setDone(false);
        break;
      case "phase_open":
        setActive({ num: ev.num, title: ev.title, state: "ground", grounding: [] });
        break;
      case "grounding":
        setActive((a) => (a ? { ...a, grounding: ev.items } : a));
        break;
      case "drafting":
        setActive((a) => (a ? { ...a, state: "draft", note: ev.note } : a));
        break;
      case "ask":
        setActive((a) => (a ? { ...a, state: "ask" } : a));
        setItems((prev) => [...prev, {
          id: nid(), kind: "ask", ask: ev,
          answered: ev.auto_assumed ? (ev.auto_answer || ev.recommendation?.label || "") : null,
        }]);
        if (!ev.auto_assumed) setRunning(false);
        break;
      case "section_html":
        setActive(null);
        setSections((prev) => prev.some((s) => s.section_id === ev.section_id)
          ? prev.map((s) => (s.section_id === ev.section_id ? { ...s, num: ev.num, title: ev.title, html: ev.html } : s))
          : [...prev, { section_id: ev.section_id, num: ev.num, title: ev.title, owner: ev.owner, html: ev.html }]);
        break;
      case "chat":
        if (ev.kind === "banter") {
          setItems((prev) => {
            const last = prev[prev.length - 1];
            return last && last.kind === "status" ? [...prev.slice(0, -1), { ...last, text: ev.text }] : [...prev, { id: nid(), kind: "status", text: ev.text }];
          });
        } else {
          setItems((prev) => [...prev, { id: nid(), kind: "agent", text: ev.text }]);
        }
        break;
      case "plan":
        setPlanHtml(ev.html);
        break;
      case "run_done":
        setActive(null);
        setRunning(false);
        setDone(true);
        setHasResult(true);
        break;
      case "error":
        setItems((prev) => [...prev, { id: nid(), kind: "agent", text: `Something went wrong: ${ev.message}` }]);
        setRunning(false);
        break;
      default:
        break;
    }
  }, []);

  const startRun = useCallback(() => {
    closeStream();
    setRunning(true);
    setDone(false);
    const es = new EventSource(`/api/studio/stream?project_id=${encodeURIComponent(projectId)}`);
    esRef.current = es;
    es.onmessage = (msg) => {
      const ev: StudioEvent = JSON.parse(msg.data);
      // The server ends the stream at each ask and at the end; close it so it never
      // auto-reconnects and replays (an auto-assumed ask keeps streaming).
      if ((ev.type === "ask" && !ev.auto_assumed) || ev.type === "run_done" || ev.type === "error") {
        es.close();
        if (esRef.current === es) esRef.current = null;
      }
      apply(ev);
    };
    es.onerror = () => {
      if (esRef.current !== es) return;
      closeStream();
      setRunning(false);
      push({ id: nid(), kind: "agent", text: "The build was interrupted. Open this plan again to resume where it stopped." });
    };
  }, [apply, closeStream, projectId, push]);

  // Load (and resume an unfinished build).
  useEffect(() => {
    let live = true;
    fetch(`/api/projects/${encodeURIComponent(projectId)}`)
      .then((r) => json<ProjectDetail>(r, "load plan"))
      .then((proj) => {
        if (!live) return;
        setSlots(proj.state.slots);
        setPlanHtml(proj.plan_html);
        setHasResult(!!proj.result);
        const studio = proj.state.studio;
        setSections(studio?.sections ?? []);
        setTotal(studio?.sections?.length ?? 0);
        const pendingAsk = studio?.await_ask ?? null;
        const restored: PlanChatItem[] = proj.messages.map((m) => {
          if (m.meta?.kind === "studio_ask" && m.meta.ask) {
            return { id: nid(), kind: "ask", ask: m.meta.ask as StudioAsk, answered: m.meta.answer ?? "" };
          }
          return { id: nid(), kind: m.role, text: m.text, clarify: m.meta?.kind === "clarify" ? m.meta.clarify : null };
        });
        setItems(restored);
        const st = proj.state as { phase?: string; studio_done?: boolean };
        // Keyed on the Studio's own done flag, not on `result`: the server saves the research
        // result early, long before the section build finishes, so a result alone doesn't
        // mean the plan is complete. The stream replays to the pending ask (or keeps drafting).
        if (st.studio_done) {
          setDone(true);
        } else if (studio || pendingAsk || st.phase === "running") {
          startRun();
        }
        setLoaded(true);
      })
      .catch((e) => { if (live) setError(e instanceof Error ? e.message : String(e)); });
    return () => { live = false; closeStream(); };
  }, [projectId, startRun, closeStream]);

  const send = useCallback(async (text: string) => {
    const message = text.trim();
    if (!message || busy || running) return;
    push({ id: nid(), kind: "user", text: message });
    setBusy(true);
    try {
      const res = await fetch("/api/chat", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_id: projectId, message }),
      });
      const data = await json<ChatResponse>(res, "chat");
      setSlots(data.slots);
      if (data.plan_updated && data.plan_html) setPlanHtml(data.plan_html);
      push({ id: nid(), kind: "agent", text: data.reply, clarify: data.clarify });
      if (data.action === "run") startRun();
    } catch (e) {
      push({ id: nid(), kind: "agent", text: `Couldn't reach the planning agent: ${e instanceof Error ? e.message : String(e)}` });
    } finally {
      setBusy(false);
    }
  }, [busy, projectId, push, running, startRun]);

  const answer = useCallback(async (itemId: string, ask: StudioAsk, value: string) => {
    setItems((prev) => prev.map((i) => (i.id === itemId && i.kind === "ask" ? { ...i, answered: value } : i)));
    try {
      const res = await fetch("/api/studio/answer", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_id: projectId, ask_id: ask.ask_id, value }),
      });
      await json<unknown>(res, "answer");
      startRun();
    } catch (e) {
      setItems((prev) => prev.map((i) => (i.id === itemId && i.kind === "ask" ? { ...i, answered: null } : i)));
      push({ id: nid(), kind: "agent", text: `Couldn't record that answer: ${e instanceof Error ? e.message : String(e)}` });
    }
  }, [projectId, push, startRun]);

  const pendingAsk = items.some((i) => i.kind === "ask" && i.answered === null);
  return { loaded, error, slots, items, sections, planHtml, total, active, running, busy, done, hasResult, pendingAsk, send, answer };
}
