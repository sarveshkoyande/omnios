import { useCallback, useEffect, useRef, useState } from "react";
import {
  applyPersonaFeedback,
  closeUpdates,
  createProject,
  fetchPersonaOffer,
  getProject,
  listProjects,
  postChat,
  runPersonaReview,
  savePlanContent,
  uploadBriefFile,
} from "../api";
import type { AgentEntry } from "./AgentTeamPanel";
import type { Inferred } from "./BriefCard";
import type { ClarifyPayload, PersonaApplyChange, PersonaOffer, PersonaReview, PlanResult, ProjectSummary, RunEvent, Slots } from "./types";

export interface ChatItem {
  id: string;
  kind:
    | "agent"
    | "user"
    | "narration"
    | "turn"
    | "banter"
    | "clarify"
    | "typing"
    | "plan-update"
    | "persona-offer"
    | "persona-review"
    | "persona-apply-bar"
    | "persona-apply-result";
  text?: string;
  clarify?: ClarifyPayload;
  agentId?: string;
  to?: string;
  updatedSections?: string[];
  personaOffer?: PersonaOffer;
  personaReview?: PersonaReview;
  applyChanges?: PersonaApplyChange[];
}

let seq = 0;
const nextId = () => `m${++seq}`;

const emptyInferred: Inferred = { persona: "", stage_label: "", lifecycle_label: "", competitors: [] };

export function useWorkspace() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [projectName, setProjectName] = useState<string>("");
  const [slots, setSlots] = useState<Slots>({ brand: "", therapy_area: "", lifecycle_key: "", budget: 0 });
  const [inferred, setInferred] = useState<Inferred>(emptyInferred);
  const [items, setItems] = useState<ChatItem[]>([]);
  const [showIntake, setShowIntake] = useState(false);
  const [busy, setBusy] = useState(false);
  const [agents, setAgents] = useState<AgentEntry[]>([]);
  const [teamCaption, setTeamCaption] = useState("Your team is ready — kicking off the research…");
  const [planHtml, setPlanHtml] = useState<string | null>(null);
  const [planMarkdown, setPlanMarkdown] = useState<string | null>(null);
  const [result, setResult] = useState<PlanResult | null>(null);
  const [stage, setStage] = useState(1);
  const [sectionsProgress, setSectionsProgress] = useState<{ done: number; total: number } | null>(null);
  const [openPersonaId, setOpenPersonaId] = useState<string | null>(null);
  const [planFrozen, setPlanFrozen] = useState(false);
  const [planEditing, setPlanEditing] = useState(false);
  const esRef = useRef<EventSource | null>(null);
  const hasOpenQuestionsRef = useRef(false);
  const planFrozenRef = useRef(false);
  const personaOfferShownRef = useRef(false);
  const hasResultRef = useRef(false);

  const markPlanFrozen = useCallback((frozen: boolean) => {
    planFrozenRef.current = frozen;
    setPlanFrozen(frozen);
  }, []);

  const refreshProjects = useCallback(() => {
    listProjects().then(setProjects).catch(() => {});
  }, []);

  useEffect(() => {
    refreshProjects();
  }, [refreshProjects]);

  const closeStream = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
  }, []);

  const maybeOfferPersonas = useCallback(async (pid: string) => {
    if (!hasResultRef.current || personaOfferShownRef.current || planFrozenRef.current || hasOpenQuestionsRef.current) return;
    try {
      const offer = await fetchPersonaOffer(pid);
      if (!offer.matched.length && !offer.others.length) return;
      personaOfferShownRef.current = true;
      setItems((prev) => [...prev, { id: nextId(), kind: "persona-offer", personaOffer: offer }]);
    } catch {
      /* best-effort, mirrors legacy */
    }
  }, []);

  const startRun = useCallback(
    (phase: string, pid: string) => {
      setAgents([]);
      setSectionsProgress(null);
      setBusy(true);
      if (phase === "align") { personaOfferShownRef.current = false; setStage(1); }
      const es = new EventSource(`/api/run-stream?project_id=${encodeURIComponent(pid)}&phase=${encodeURIComponent(phase)}`);
      esRef.current = es;
      es.onmessage = (evt) => {
        const ev: RunEvent = JSON.parse(evt.data);
        switch (ev.type) {
          case "agents_init":
            setAgents(ev.agents.map((a) => ({ id: a.id, name: a.name, role: a.role, status: "standby" })));
            break;
          case "agent":
            setAgents((prev) =>
              prev.map((a) =>
                a.id === ev.id
                  ? { ...a, status: ev.status, summary: ev.summary, detail: ev.detail }
                  : a,
              ),
            );
            setTeamCaption(
              ev.status === "running"
                ? `<b>${ev.id}</b> is working…`
                : ev.final
                  ? "Your team has finished — the plan is ready."
                  : `<b>${ev.id}</b> finished — its plan sections just filled in.`,
            );
            if (ev.status === "running" && ev.say) {
              setItems((prev) => [...prev, { id: nextId(), kind: "turn", agentId: ev.id, text: ev.say }]);
            } else if (ev.status === "done") {
              setItems((prev) => [...prev, { id: nextId(), kind: "turn", agentId: ev.id, text: ev.summary || "Done" }]);
            }
            break;
          case "inferred":
            setInferred((prev) => ({
              persona: ev.persona ?? prev.persona,
              stage_label: ev.stage_label ?? prev.stage_label,
              lifecycle_label: ev.lifecycle_label ?? prev.lifecycle_label,
              competitors: ev.competitors ?? prev.competitors,
              cx_maturity: ev.cx_maturity ?? prev.cx_maturity,
            }));
            break;
          case "narration":
            setItems((prev) => [...prev, { id: nextId(), kind: "narration", text: ev.text }]);
            break;
          case "banter":
            setItems((prev) => [...prev, { id: nextId(), kind: "banter", agentId: ev.id, to: ev.to, text: ev.text }]);
            break;
          case "clarify":
            hasOpenQuestionsRef.current = true;
            setItems((prev) => [...prev, { id: nextId(), kind: "clarify", clarify: ev.clarify }]);
            break;
          case "plan":
            setPlanHtml(ev.html);
            setPlanMarkdown(ev.markdown);
            if (ev.partial) setSectionsProgress({ done: ev.sections_done ?? 0, total: ev.sections_total ?? 0 });
            else setSectionsProgress(null);
            break;
          case "result":
            hasResultRef.current = true;
            setResult(ev.result);
            break;
          case "error":
            setItems((prev) => [...prev, { id: nextId(), kind: "agent", text: `⚠ ${ev.message}` }]);
            break;
          case "done": {
            closeStream();
            setBusy(false);
            refreshProjects();
            if (!hasOpenQuestionsRef.current) maybeOfferPersonas(pid);
            break;
          }
        }
      };
      es.onerror = () => {
        closeStream();
        setBusy(false);
        setItems((prev) => [...prev, { id: nextId(), kind: "agent", text: "⚠ The research run was interrupted. You can ask me to re-run." }]);
      };
    },
    [closeStream, refreshProjects, maybeOfferPersonas],
  );

  const openProject = useCallback(async (id: string) => {
    closeStream();
    const proj = await getProject(id);
    setProjectId(proj.id);
    setProjectName(proj.name);
    setSlots(proj.state.slots);
    setPlanHtml(proj.plan_html);
    setPlanMarkdown(proj.plan_markdown);
    setSectionsProgress(null);
    setStage(1);
    setResult(proj.result);
    const openQs = proj.state.open_questions ?? [];
    hasOpenQuestionsRef.current = openQs.length > 0 && (proj.state.clarify_idx ?? 0) < openQs.length;
    markPlanFrozen(!!proj.state.plan_frozen);
    setPlanEditing(false);
    hasResultRef.current = !!proj.result;
    const existingReviews = proj.state.persona_reviews ?? null;
    personaOfferShownRef.current = !!existingReviews?.length;
    const fresh = proj.phase === "collecting" && !proj.messages.some((m) => m.role === "user");
    setShowIntake(fresh);
    setItems(
      proj.messages.map((m) => ({
        id: nextId(),
        kind: m.role,
        text: m.text,
        clarify: m.meta?.kind === "clarify" ? m.meta.clarify ?? undefined : undefined,
      })),
    );
    if (existingReviews?.length) {
      setItems((prev) => [
        ...prev,
        ...existingReviews.map((r): ChatItem => ({ id: nextId(), kind: "persona-review", personaReview: r })),
        ...(planFrozenRef.current ? [] : [{ id: nextId(), kind: "persona-apply-bar" } as ChatItem]),
      ]);
    }
    if (proj.result) {
      const inf = proj.result.inferred_inputs;
      setInferred({
        persona: inf.persona,
        stage_label: inf.stage_label,
        lifecycle_label: inf.lifecycle_label,
        competitors: inf.discovered_competitors,
        cx_maturity: proj.result.cx_maturity?.level ?? "",
      });
      setAgents([]); // done-from-result summary is out of scope for this phase; team panel resets
    } else {
      setInferred(emptyInferred);
      setAgents([]);
    }
    if (proj.result && !hasOpenQuestionsRef.current) maybeOfferPersonas(proj.id);
  }, [closeStream, maybeOfferPersonas, markPlanFrozen]);

  const newProject = useCallback(async () => {
    const proj = await createProject("Untitled plan");
    await refreshProjects();
    await openProject(proj.id);
  }, [openProject, refreshProjects]);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text || busy || !projectId) return;
      setItems((prev) => [...prev, { id: nextId(), kind: "user", text }, { id: "typing", kind: "typing" }]);
      setBusy(true);
      try {
        const data = await postChat(projectId, text);
        setSlots(data.slots);
        if (data.name && data.name !== projectName) setProjectName(data.name);
        markPlanFrozen(data.plan_frozen);
        if (!data.clarify) hasOpenQuestionsRef.current = false;
        setItems((prev) => {
          const withoutTyping = prev.filter((i) => i.id !== "typing");
          const extra: ChatItem[] = [];
          if (data.plan_updated && data.plan_html) {
            extra.push({ id: nextId(), kind: "plan-update", updatedSections: data.updated_sections });
            setPlanHtml(data.plan_html);
            setPlanMarkdown(data.plan_markdown);
          }
          extra.push({ id: nextId(), kind: "agent", text: data.reply, clarify: data.clarify ?? undefined });
          return [...withoutTyping, ...extra];
        });
        refreshProjects();
        if (data.action === "run") startRun("align", projectId);
        else if (data.clarify_just_completed && !data.plan_frozen) {
          if (data.next_phase) startRun(data.next_phase, projectId);
          else maybeOfferPersonas(projectId);
        }
      } catch {
        setItems((prev) => [...prev.filter((i) => i.id !== "typing"), { id: nextId(), kind: "agent", text: "⚠ Something went wrong reaching the agent. Try again." }]);
      } finally {
        setBusy(false);
      }
    },
    [busy, projectId, projectName, refreshProjects, startRun, maybeOfferPersonas, markPlanFrozen],
  );

  const uploadFile = useCallback(
    async (file: File) => {
      if (!projectId || busy) return;
      setItems((prev) => [...prev, { id: nextId(), kind: "user", text: `📎 Uploaded **${file.name}**` }, { id: "typing", kind: "typing" }]);
      setBusy(true);
      try {
        const data = await uploadBriefFile(projectId, file);
        setSlots(data.slots);
        if (data.name && data.name !== projectName) setProjectName(data.name);
        setItems((prev) => [...prev.filter((i) => i.id !== "typing"), { id: nextId(), kind: "agent", text: data.reply }]);
        refreshProjects();
        if (data.action === "run") startRun("align", projectId);
      } catch (e) {
        setItems((prev) => [...prev.filter((i) => i.id !== "typing"), { id: nextId(), kind: "agent", text: `⚠ ${e instanceof Error ? e.message : "Could not process that file."}` }]);
      } finally {
        setBusy(false);
      }
    },
    [busy, projectId, projectName, refreshProjects, startRun],
  );

  const submitIntake = useCallback(
    (text: string) => {
      setShowIntake(false);
      if (text) sendMessage(text);
    },
    [sendMessage],
  );

  const skipPersonaOffer = useCallback((itemId: string) => {
    setItems((prev) => prev.filter((i) => i.id !== itemId));
  }, []);

  const runPersonas = useCallback(
    async (offerItemId: string, ids: string[]) => {
      if (!projectId) return;
      setItems((prev) => [
        ...prev.filter((i) => i.id !== offerItemId),
        { id: nextId(), kind: "user", text: `Run the plan past ${ids.length} persona${ids.length > 1 ? "s" : ""}.` },
        { id: "typing", kind: "typing" },
      ]);
      try {
        const reviews = await runPersonaReview(projectId, ids);
        setItems((prev) => [
          ...prev.filter((i) => i.id !== "typing"),
          { id: nextId(), kind: "agent", text: `Here's how ${reviews.length} of your target personas reacted — honest feedback, in their words:` },
          ...reviews.map((r): ChatItem => ({ id: nextId(), kind: "persona-review", personaReview: r })),
          ...(planFrozenRef.current ? [] : [{ id: nextId(), kind: "persona-apply-bar" } as ChatItem]),
        ]);
        refreshProjects();
      } catch {
        setItems((prev) => [...prev.filter((i) => i.id !== "typing"), { id: nextId(), kind: "agent", text: "⚠ The persona review didn't complete. You can try again." }]);
      }
    },
    [projectId, refreshProjects],
  );

  const applyFeedback = useCallback(
    async (barItemId: string) => {
      if (!projectId) return;
      const reviewIds = items.filter((i) => i.kind === "persona-review").map((i) => i.personaReview!.persona_id);
      try {
        const data = await applyPersonaFeedback(projectId, reviewIds);
        if (data.plan_html) setPlanHtml(data.plan_html);
        if (data.plan_markdown) setPlanMarkdown(data.plan_markdown);
        setItems((prev) => [
          ...prev.filter((i) => i.id !== barItemId),
          { id: nextId(), kind: "persona-apply-result", applyChanges: data.changes },
        ]);
        refreshProjects();
      } catch {
        setItems((prev) => [...prev, { id: nextId(), kind: "agent", text: "⚠ Couldn't adjust the plan automatically. Try again." }]);
      }
    },
    [projectId, items, refreshProjects],
  );

  const beginPlanEdit = useCallback(() => setPlanEditing(true), []);

  const cancelPlanEdit = useCallback((doc: { revert: () => void } | null) => {
    doc?.revert();
    setPlanEditing(false);
  }, []);

  const savePlanEdit = useCallback(
    async (html: string, markdown: string) => {
      if (!projectId) return;
      try {
        await savePlanContent(projectId, html, markdown);
        setPlanEditing(false);
        setPlanHtml(html);
        setPlanMarkdown(markdown);
        setItems((prev) => [...prev, { id: nextId(), kind: "agent", text: "✏️ Your edits to the plan have been saved." }]);
        refreshProjects();
      } catch {
        setItems((prev) => [...prev, { id: nextId(), kind: "agent", text: "⚠ Couldn't save your edits. Try again." }]);
      }
    },
    [projectId, refreshProjects],
  );

  const closeUpdatesAction = useCallback(async () => {
    if (!projectId) return;
    try {
      await closeUpdates(projectId);
      markPlanFrozen(true);
      setItems((prev) => [...prev, { id: nextId(), kind: "agent", text: "🔒 Updates closed — this plan is locked in. I won't auto-adjust it further." }]);
    } catch {
      /* best-effort, mirrors legacy */
    }
  }, [projectId, markPlanFrozen]);

  return {
    projects,
    projectId,
    projectName,
    slots,
    inferred,
    items,
    showIntake,
    busy,
    agents,
    teamCaption,
    planHtml,
    planMarkdown,
    planFrozen,
    planEditing,
    result,
    stage,
    setStage,
    sectionsProgress,
    profileOpen: openPersonaId,
    newProject,
    openProject,
    sendMessage,
    uploadFile,
    submitIntake,
    setShowIntake,
    skipPersonaOffer,
    runPersonas,
    applyFeedback,
    beginPlanEdit,
    cancelPlanEdit,
    savePlanEdit,
    closeUpdatesAction,
    openPersonaProfile: setOpenPersonaId,
    closePersonaProfile: () => setOpenPersonaId(null),
  };
}
