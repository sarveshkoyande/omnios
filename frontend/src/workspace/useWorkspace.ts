import { useCallback, useEffect, useRef, useState } from "react";
import {
  applyPersonaFeedback,
  closeUpdates,
  createProject,
  deleteProject,
  extractProjectText,
  fetchPersonaOffer,
  generateCampaignPlan,
  generateOrchestrationTasks,
  getProject,
  getTabChat,
  listProjects,
  postChat,
  postStudioAnswer,
  postTabChat,
  renameProject,
  runPersonaReview,
  saveCampaignFlowDocument,
  savePlanContent,
  uploadBriefFile,
} from "../api";
import type { AgentEntry } from "./AgentTeamPanel";
import type { Inferred } from "./BriefCard";
import type { BriefExtractItem, ClarifyPayload, PersonaApplyChange, PersonaOffer, PersonaReview, PlanResult, ProjectSummary, RunEvent, Slots, StageAgentId } from "./types";
import { STAGE_AGENTS } from "./types";
import { Pacer } from "./studio/pacer";
import { STUDIO_IDLE } from "./studio/studioTypes";
import type { StudioAsk, StudioEvent, StudioSection, StudioState } from "./studio/studioTypes";
import { parseDocument } from "./stages/operations/flowbuilder/schema";
import { useWorkflowStore } from "./stages/operations/flowbuilder/store/useWorkflowStore";
import { campaignFlowToDocument } from "./stages/operations/campaignAdapter";

// Stages 2 (Orchestration) and 3 (Operations) don't build anything until the user says so:
// the first time either tab's chat is opened with nothing generated yet, a "kickoff-choice"
// card asks whether to build from the Stage 1 plan as-is or from an uploaded document/extra
// instructions first. `artifactRefresh` is a per-stage counter Stage components watch to
// know when to refetch after a kickoff-triggered generation (they own their own fetch, this
// just tells them "go again").
const KICKOFF_STAGES = new Set<StageAgentId>(["orchestration", "operations"]);

// Stage 1 (Planning & Strategy) keeps the existing global `items` thread (the automated
// run's live narration + interactive chat, unchanged). Stages 2-4 are new: each gets its
// own agent identity and its own persisted thread (strategy/tab_chat.py), fetched/posted
// via getTabChat/postTabChat and cached per stage in `tabChatItems` below.
const STAGE_ORDER: StageAgentId[] = ["planning", "orchestration", "operations", "reporting"];

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
    | "persona-apply-result"
    | "brief-extract"
    | "studio-ask"
    | "kickoff-choice";
  text?: string;
  clarify?: ClarifyPayload;
  agentId?: string;
  to?: string;
  updatedSections?: string[];
  extracted?: BriefExtractItem[];
  personaOffer?: PersonaOffer;
  personaReview?: PersonaReview;
  applyChanges?: PersonaApplyChange[];
  ask?: StudioAsk;
  askOwnerName?: string;
  askAnswered?: string;
  kickoffStage?: StageAgentId;
  kickoffResolved?: boolean;
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
  const [tabChatItems, setTabChatItems] = useState<Record<StageAgentId, ChatItem[]>>({
    planning: [], orchestration: [], operations: [], reporting: [],
  });
  const loadedTabChatRef = useRef<Set<StageAgentId>>(new Set());
  const [kickoffAwaitingInput, setKickoffAwaitingInput] = useState<StageAgentId | null>(null);
  const [artifactRefresh, setArtifactRefresh] = useState<Record<StageAgentId, number>>({
    planning: 0, orchestration: 0, operations: 0, reporting: 0,
  });
  const [showIntake, setShowIntake] = useState(false);
  const [busy, setBusy] = useState(false);
  const [agents, setAgents] = useState<AgentEntry[]>([]);
  const [teamCaption, setTeamCaption] = useState("Your team is ready. Kicking off the research…");
  const [planHtml, setPlanHtml] = useState<string | null>(null);
  const [planMarkdown, setPlanMarkdown] = useState<string | null>(null);
  const [result, setResult] = useState<PlanResult | null>(null);
  const [stage, setStage] = useState(1);
  const [revealedPhases, setRevealedPhases] = useState<string[]>([]);
  const [sectionsProgress, setSectionsProgress] = useState<{ done: number; total: number } | null>(null);
  const [openPersonaId, setOpenPersonaId] = useState<string | null>(null);
  const [planFrozen, setPlanFrozen] = useState(false);
  const [planEditing, setPlanEditing] = useState(false);
  const [studio, setStudio] = useState<StudioState>(STUDIO_IDLE);
  const [typingAuthor, setTypingAuthor] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const pacerRef = useRef<Pacer | null>(null);
  const slotOwnerNameRef = useRef("");
  const studioActiveRef = useRef(false);
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

  // Lazy-load each non-planning tab's chat history the first time that tab is opened for
  // this project; cached thereafter (loadedTabChatRef resets on project switch below).
  useEffect(() => {
    if (!projectId || stage === 1) return;
    const stageId = STAGE_ORDER[stage - 1];
    if (loadedTabChatRef.current.has(stageId)) return;
    loadedTabChatRef.current.add(stageId);
    const needsKickoffCheck = KICKOFF_STAGES.has(stageId);
    Promise.all([getTabChat(projectId, stageId), needsKickoffCheck ? getProject(projectId) : Promise.resolve(null)])
      .then(([history, proj]) => {
        const historyItems: ChatItem[] = history.map((m) => ({
          id: nextId(),
          kind: m.role === "user" ? "user" : "agent",
          agentId: m.agent_id ?? undefined,
          text: m.text,
        }));
        const artifactExists =
          stageId === "orchestration"
            ? !!(proj?.orchestration_tasks && proj.orchestration_tasks.length)
            : stageId === "operations"
              ? !!proj?.campaign_plan_layout
              : true;
        const needsKickoff = needsKickoffCheck && history.length === 0 && !!proj?.result && !artifactExists;
        setTabChatItems((prev) => ({
          ...prev,
          [stageId]: needsKickoff
            ? [...historyItems, { id: nextId(), kind: "kickoff-choice", kickoffStage: stageId }]
            : historyItems,
        }));
      })
      .catch(() => {});
  }, [projectId, stage]);

  useEffect(() => {
    refreshProjects();
  }, [refreshProjects]);

  const closeStream = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
    studioActiveRef.current = false;
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

  // ---------------------------------------------------------------- //
  // Sequential Plan Studio (SSE v2): the section-by-section run that drives
  // Stage 1. Events replay through the Pacer at a human rhythm; the stream
  // ends at every grounded ask and a new stream resumes after the answer.
  // ---------------------------------------------------------------- //
  const applyStudioEvent = useCallback((ev: StudioEvent, pid: string) => {
    switch (ev.type) {
      case "run_open":
        studioActiveRef.current = true;
        setStudio((prev) => ({ ...prev, active: true, done: false, total: ev.total_sections }));
        break;
      case "phase_open":
        // The backend still tags each section with which of its 5 internal work-steps
        // owns it (studio_run.py's AGENT_ROSTER) — normalized here to the single
        // Planning & Strategy persona so no per-step identity reaches the UI.
        slotOwnerNameRef.current = STAGE_AGENTS.planning.name;
        setStudio((prev) => ({
          ...prev,
          slot: { idx: ev.idx, num: ev.num, title: ev.title, owner: STAGE_AGENTS.planning.id, ownerName: STAGE_AGENTS.planning.name, state: "ground", grounding: [] },
        }));
        break;
      case "grounding":
        setStudio((prev) =>
          prev.slot ? { ...prev, slot: { ...prev.slot, state: "ground", grounding: ev.items } } : prev,
        );
        break;
      case "chat":
        // "turn" is the agent addressing the human -> single Planning & Strategy identity,
        // always appended. "banter" is an ambient status aside (e.g. the research heartbeat
        // lines): show ONE cycling status line — each new banter REPLACES the trailing banter
        // in place rather than stacking a growing list. Reusing the previous banter's id keeps
        // React swapping the text of the same node, so it reads as one line updating.
        if (ev.kind === "banter") {
          setItems((prev) => {
            const last = prev[prev.length - 1];
            if (last && last.kind === "banter") {
              return [...prev.slice(0, -1), { ...last, text: ev.text }];
            }
            return [...prev, { id: nextId(), kind: "banter", agentId: STAGE_AGENTS.planning.id, text: ev.text }];
          });
        } else {
          setItems((prev) => [...prev, { id: nextId(), kind: "turn", agentId: STAGE_AGENTS.planning.id, text: ev.text }]);
        }
        break;
      case "ask":
        setStudio((prev) => (prev.slot ? { ...prev, slot: { ...prev.slot, state: "ask" } } : prev));
        setItems((prev) => [
          ...prev,
          { id: nextId(), kind: "studio-ask", ask: ev, askOwnerName: slotOwnerNameRef.current },
        ]);
        setBusy(false);
        break;
      case "drafting":
        setStudio((prev) => (prev.slot ? { ...prev, slot: { ...prev.slot, state: "draft", draftNote: ev.note } } : prev));
        break;
      case "section_html":
        setStudio((prev) => ({
          ...prev,
          slot: null,
          sections: prev.sections.some((s) => s.section_id === ev.section_id)
            ? prev.sections
            : [...prev.sections, { section_id: ev.section_id, num: ev.num, title: ev.title, owner: STAGE_AGENTS.planning.id, html: ev.html }],
        }));
        break;
      case "phase_done":
        break;
      case "decision_record": {
        // The landed step's reasoning — accumulated for the Decision Trail panel.
        const { type: _t, ...record } = ev;
        setStudio((prev) =>
          prev.records.some((r) => r.stage_id === record.stage_id)
            ? prev
            : { ...prev, records: [...prev.records, record] },
        );
        break;
      }
      case "plan":
        setPlanHtml(ev.html);
        setPlanMarkdown(ev.markdown);
        break;
      case "agents_init":
        // Backend still announces its full internal roster; collapse to the one
        // identity the UI shows (AgentTeamPanel now renders a single status card).
        setAgents([{ id: STAGE_AGENTS.planning.id, name: STAGE_AGENTS.planning.name, status: "standby" }]);
        setTeamCaption("Researching your brief…");
        break;
      case "run_done":
        studioActiveRef.current = false;
        setStudio((prev) => ({ ...prev, active: false, done: true, slot: null }));
        setBusy(false);
        refreshProjects();
        getProject(pid)
          .then((proj) => {
            if (proj.result) {
              hasResultRef.current = true;
              setResult(proj.result);
              maybeOfferPersonas(pid);
            }
          })
          .catch(() => {});
        break;
      case "error":
        setItems((prev) => [...prev, { id: nextId(), kind: "agent", text: `⚠ ${ev.message}` }]);
        setBusy(false);
        break;
    }
  }, [maybeOfferPersonas, refreshProjects]);

  const startStudioRun = useCallback(
    (pid: string) => {
      closeStream(); // never leave a previous stream running into a stale pacer
      studioActiveRef.current = true;
      setBusy(true);
      setStage(1);
      setStudio((prev) => ({ ...prev, active: true, done: false, total: prev.total || 11 }));
      setAgents([{ id: STAGE_AGENTS.planning.id, name: STAGE_AGENTS.planning.name, status: "running" }]);
      setTeamCaption("Researching your brief...");
      pacerRef.current?.dispose();
      const pacer = new Pacer(
        (ev) => applyStudioEvent(ev, pid),
        setTypingAuthor,
        (awaiting) => setStudio((prev) => ({ ...prev, awaitingContinue: awaiting })),
      );
      pacerRef.current = pacer;
      const es = new EventSource(`/api/studio/stream?project_id=${encodeURIComponent(pid)}`);
      esRef.current = es;
      es.onmessage = (evt) => {
        const ev: StudioEvent = JSON.parse(evt.data);
        // The server ends the stream at asks and at run completion; close THIS
        // EventSource so it never auto-reconnects and replays the phase (and
        // never touch a newer stream that may have replaced it).
        if (ev.type === "ask" || ev.type === "run_done" || ev.type === "error") {
          es.close();
          if (esRef.current === es) esRef.current = null;
        }
        pacer.enqueue(ev);
      };
      es.onerror = () => {
        if (esRef.current !== es) return; // superseded or closed deliberately
        closeStream();
        setBusy(false);
        setItems((prev) => [...prev, { id: nextId(), kind: "agent", text: "⚠ The build stream was interrupted. Open the plan again to resume where it left off." }]);
      };
    },
    [applyStudioEvent, closeStream],
  );

  const answerStudioAsk = useCallback(
    async (itemId: string, ask: StudioAsk, value: string) => {
      if (!projectId) return;
      setItems((prev) =>
        prev.map((i) => (i.id === itemId ? { ...i, askAnswered: value } : i)),
      );
      setItems((prev) => [...prev, { id: nextId(), kind: "user", text: value }]);
      try {
        await postStudioAnswer(projectId, ask.ask_id, value);
        startStudioRun(projectId); // resume: drafts this section, opens the next
      } catch {
        setItems((prev) => [...prev, { id: nextId(), kind: "agent", text: "⚠ Couldn't record that answer. Try picking it again." }]);
      }
    },
    [projectId, startStudioRun],
  );

  const skipStudioPacing = useCallback(() => {
    pacerRef.current?.skip();
  }, []);

  const continueStudioSection = useCallback(() => {
    pacerRef.current?.resume();
  }, []);

  const startRun = useCallback(
    (phase: string, pid: string) => {
      setAgents([]);
      setSectionsProgress(null);
      setBusy(true);
      if (phase === "align") { personaOfferShownRef.current = false; setStage(1); setRevealedPhases([]); }
      const es = new EventSource(`/api/run-stream?project_id=${encodeURIComponent(pid)}&phase=${encodeURIComponent(phase)}`);
      esRef.current = es;
      es.onmessage = (evt) => {
        const ev: RunEvent = JSON.parse(evt.data);
        switch (ev.type) {
          case "agents_init":
            // Legacy protocol still announces its full internal roster; collapse to
            // the one identity the UI shows, same as the live studio path.
            setAgents([{ id: STAGE_AGENTS.planning.id, name: STAGE_AGENTS.planning.name, status: "standby" }]);
            break;
          case "agent":
            // Only one entry exists now (seeded above); every work-step update just
            // refreshes that single agent's status, regardless of which internal
            // step (ev.id) the backend actually attributes it to.
            setAgents((prev) => prev.map((a) => ({ ...a, status: ev.status, summary: ev.summary, detail: ev.detail })));
            setTeamCaption(
              ev.status === "running"
                ? `<b>${STAGE_AGENTS.planning.name}</b> is working…`
                : ev.final
                  ? "Your agent has finished. The plan is ready."
                  : `<b>${STAGE_AGENTS.planning.name}</b> updated the plan.`,
            );
            if (ev.status === "running" && ev.say) {
              setItems((prev) => [...prev, { id: nextId(), kind: "turn", agentId: STAGE_AGENTS.planning.id, text: ev.say }]);
            } else if (ev.status === "done") {
              setItems((prev) => [...prev, { id: nextId(), kind: "turn", agentId: STAGE_AGENTS.planning.id, text: ev.summary || "Done" }]);
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
            // One cycling status line: replace the trailing banter in place (see the studio
            // "chat" handler above) rather than stacking a list of asides.
            setItems((prev) => {
              const last = prev[prev.length - 1];
              if (last && last.kind === "banter") {
                return [...prev.slice(0, -1), { ...last, text: ev.text }];
              }
              return [...prev, { id: nextId(), kind: "banter", agentId: STAGE_AGENTS.planning.id, text: ev.text }];
            });
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
            if (ev.revealed_phases) setRevealedPhases(ev.revealed_phases);
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
    pacerRef.current?.dispose();
    setStudio(STUDIO_IDLE);
    setTypingAuthor(null);
    loadedTabChatRef.current = new Set();
    setTabChatItems({ planning: [], orchestration: [], operations: [], reporting: [] });
    setKickoffAwaitingInput(null);
    setArtifactRefresh({ planning: 0, orchestration: 0, operations: 0, reporting: 0 });
    const proj = await getProject(id);
    setProjectId(proj.id);
    setProjectName(proj.name);
    setSlots(proj.state.slots);
    setPlanHtml(proj.plan_html);
    setPlanMarkdown(proj.plan_markdown);
    setSectionsProgress(null);
    setStage(1);
    setResult(proj.result);
    // Projects built before phase-gating existed never persisted revealed_phases -- treat a
    // missing field (not an empty array, which means "genuinely only Align so far" under the
    // new code) as fully revealed so previously-accessible plans don't suddenly lock back up.
    setRevealedPhases(proj.state.revealed_phases ?? (proj.result ? ["align", "select", "create", "deploy"] : []));
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
    // A studio build that was interrupted mid-phase resumes exactly where it
    // stopped (the server re-poses the pending ask, or continues drafting).
    const st = proj.state as {
      phase?: string;
      studio?: { idx: number; sections?: StudioSection[] };
      studio_done?: boolean;
    };
    if (st.studio_done) {
      // Already fully built: redisplay the finished sections as a static plan canvas
      // instead of re-opening the SSE stream and replaying the whole paced reveal.
      const sections = st.studio?.sections ?? [];
      setStudio({
        active: false,
        done: true,
        total: sections.length,
        slot: null,
        records: [],
        awaitingContinue: false,
        sections: sections.map((s) => ({ ...s, owner: STAGE_AGENTS.planning.id })),
      });
    } else if ((st.studio && !st.studio_done) || (st.phase === "running" && !proj.result)) {
      // Resume an unfinished studio build wherever it stopped (re-poses the pending ask or keeps
      // drafting). Keyed on `studio_done`, NOT on `!proj.result`: the plan/brief now persist as
      // soon as research finishes (see api_studio_stream early persist), so a result exists well
      // before the section reveal is complete — gating resume on `!proj.result` would strand the
      // remaining asks. The reveal stream is idempotent (phase_open/grounding replay, ends at the
      // pending ask), so resuming on open never skips a gate or double-drafts.
      startStudioRun(proj.id);
    }
  }, [closeStream, maybeOfferPersonas, markPlanFrozen, startStudioRun]);

  const newProject = useCallback(async () => {
    const proj = await createProject("Untitled plan");
    await refreshProjects();
    await openProject(proj.id);
  }, [openProject, refreshProjects]);

  // Builds Stage 2's task checklist or Stage 3's campaign flow on demand -- called from the
  // kickoff card ("Use the Stage 1 plan", extra === null) or after the user follows up with
  // typed instructions / an uploaded document while a kickoff is awaiting input (extra is
  // that text). Never runs automatically; see the tab-chat load effect above for the gate.
  const applyKickoffContext = useCallback(
    async (stageId: StageAgentId, extra: string | null) => {
      if (!projectId) return;
      const appendAgentMsg = (text: string) =>
        setTabChatItems((prev) => ({
          ...prev,
          [stageId]: [...(prev[stageId] || []), { id: nextId(), kind: "agent", agentId: stageId, text }],
        }));
      try {
        if (stageId === "orchestration") {
          await generateOrchestrationTasks(projectId, extra ?? undefined);
          appendAgentMsg(
            extra
              ? "Built the setup-task checklist from the Stage 1 plan plus what you gave me — see the Activities & setup tasks board."
              : "Built the setup-task checklist from the Stage 1 plan — see the Activities & setup tasks board.",
          );
        } else if (stageId === "operations") {
          const plan = await generateCampaignPlan(projectId);
          const doc = campaignFlowToDocument(plan.flow);
          await saveCampaignFlowDocument(projectId, doc);
          if (extra) {
            const data = await postTabChat(projectId, "operations", extra, doc);
            appendAgentMsg(data.reply);
            const finalDoc = data.document ?? doc;
            const parsed = parseDocument(finalDoc);
            if (parsed.ok) useWorkflowStore.getState().loadDocument(parsed.document);
          } else {
            useWorkflowStore.getState().loadDocument(doc);
            appendAgentMsg("Built the campaign engagement flow from the Stage 1 plan — see the diagram below.");
          }
        }
        const refreshed = await getProject(projectId);
        if (refreshed.result) setResult(refreshed.result);
        if (refreshed.plan_html) setPlanHtml(refreshed.plan_html);
        if (refreshed.plan_markdown) setPlanMarkdown(refreshed.plan_markdown);
        setArtifactRefresh((prev) => ({ ...prev, [stageId]: (prev[stageId] ?? 0) + 1 }));
      } catch (err) {
        console.error("kickoff build failed", err);
        appendAgentMsg("⚠ Couldn't build that. Try again.");
      }
    },
    [projectId],
  );

  const onKickoffUsePlan = useCallback(
    async (itemId: string, stageId: StageAgentId) => {
      setTabChatItems((prev) => ({
        ...prev,
        [stageId]: (prev[stageId] || []).map((i) => (i.id === itemId ? { ...i, kickoffResolved: true } : i)),
      }));
      setBusy(true);
      setTypingAuthor(stageId);
      await applyKickoffContext(stageId, null);
      setBusy(false);
      setTypingAuthor(null);
    },
    [applyKickoffContext],
  );

  const onKickoffWantUpload = useCallback((_itemId: string, stageId: StageAgentId) => {
    setKickoffAwaitingInput(stageId);
  }, []);

  const sendTabChatMessage = useCallback(
    async (text: string) => {
      const stageId = STAGE_ORDER[stage - 1];
      setTabChatItems((prev) => ({
        ...prev,
        [stageId]: [...(prev[stageId] || []), { id: nextId(), kind: "user", text }],
      }));
      setBusy(true);
      setTypingAuthor(stageId);
      try {
        if (kickoffAwaitingInput === stageId) {
          setTabChatItems((prev) => ({
            ...prev,
            [stageId]: (prev[stageId] || []).map((i) => (i.kind === "kickoff-choice" ? { ...i, kickoffResolved: true } : i)),
          }));
          setKickoffAwaitingInput(null);
          await applyKickoffContext(stageId, text);
          return;
        }
        if (stageId === "operations") {
          // Send the live diagram snapshot immediately so the agent can start before
          // persistence finishes. The builder still autosaves in the background.
          const current = useWorkflowStore.getState().document;
          const data = await postTabChat(projectId as string, stageId, text, current);
          setTabChatItems((prev) => ({
            ...prev,
            [stageId]: [...(prev[stageId] || []), { id: nextId(), kind: "agent", agentId: stageId, text: data.reply }],
          }));
          if (data.document) {
            const parsed = parseDocument(data.document);
            if (parsed.ok) useWorkflowStore.getState().loadDocument(parsed.document);
          }
          const refreshed = await getProject(projectId as string);
          if (refreshed.result) setResult(refreshed.result);
          if (refreshed.campaign_plan_layout) {
            const parsed = parseDocument(refreshed.campaign_plan_layout);
            if (parsed.ok) useWorkflowStore.getState().loadDocument(parsed.document);
          }
          return;
        }
        const data = await postTabChat(projectId as string, stageId, text);
        setTabChatItems((prev) => ({
          ...prev,
          [stageId]: [...(prev[stageId] || []), { id: nextId(), kind: "agent", agentId: stageId, text: data.reply }],
        }));
        if (data.document) {
          const parsed = parseDocument(data.document);
          if (parsed.ok) useWorkflowStore.getState().loadDocument(parsed.document);
        }
        // The orchestration agent can change the activity board / raise nudges from
        // chat — bump this stage's refresh token so the board and notification centre refetch.
        if (data.changed) setArtifactRefresh((prev) => ({ ...prev, [stageId]: (prev[stageId] ?? 0) + 1 }));
      } catch {
        setTabChatItems((prev) => ({
          ...prev,
          [stageId]: [...(prev[stageId] || []), { id: nextId(), kind: "agent", text: "⚠ Something went wrong reaching the agent. Try again." }],
        }));
      } finally {
        setBusy(false);
        setTypingAuthor(null);
      }
    },
    [projectId, stage, kickoffAwaitingInput, applyKickoffContext],
  );

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text || busy || !projectId) return;
      if (stage !== 1) { await sendTabChatMessage(text); return; }
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
        if (data.action === "run") startStudioRun(projectId);
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
    [busy, projectId, projectName, refreshProjects, startRun, startStudioRun, maybeOfferPersonas, markPlanFrozen, stage, sendTabChatMessage],
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
        setItems((prev) => {
          const withoutTyping = prev.filter((i) => i.id !== "typing");
          const extra: ChatItem[] = [];
          if (data.extracted?.length) extra.push({ id: nextId(), kind: "brief-extract", extracted: data.extracted });
          extra.push({ id: nextId(), kind: "agent", text: data.reply });
          return [...withoutTyping, ...extra];
        });
        refreshProjects();
        if (data.action === "run") startStudioRun(projectId);
      } catch (e) {
        setItems((prev) => [...prev.filter((i) => i.id !== "typing"), { id: nextId(), kind: "agent", text: `⚠ ${e instanceof Error ? e.message : "Could not process that file."}` }]);
      } finally {
        setBusy(false);
      }
    },
    [busy, projectId, projectName, refreshProjects, startStudioRun],
  );

  // Stage 2/3 counterpart to uploadFile: does NOT touch the project's brief slots (this
  // isn't a brand-plan import), just extracts the document's text and either resolves a
  // pending kickoff (if the user clicked "Upload a document / add instructions") or, once
  // an artifact already exists, treats it as a normal grounded chat turn for that tab.
  const uploadTabDocument = useCallback(
    async (stageId: StageAgentId, file: File) => {
      if (!projectId || busy) return;
      setTabChatItems((prev) => ({
        ...prev,
        [stageId]: [...(prev[stageId] || []), { id: nextId(), kind: "user", text: `📎 Uploaded **${file.name}**` }],
      }));
      setBusy(true);
      setTypingAuthor(stageId);
      try {
        const { text } = await extractProjectText(projectId, file);
        if (kickoffAwaitingInput === stageId) {
          setTabChatItems((prev) => ({
            ...prev,
            [stageId]: (prev[stageId] || []).map((i) => (i.kind === "kickoff-choice" ? { ...i, kickoffResolved: true } : i)),
          }));
          setKickoffAwaitingInput(null);
          await applyKickoffContext(stageId, text);
        } else {
          const current = stageId === "operations" ? useWorkflowStore.getState().document : undefined;
          const data = await postTabChat(projectId, stageId, text, current);
          setTabChatItems((prev) => ({
            ...prev,
            [stageId]: [...(prev[stageId] || []), { id: nextId(), kind: "agent", agentId: stageId, text: data.reply }],
          }));
          if (data.document) {
            const parsed = parseDocument(data.document);
            if (parsed.ok) useWorkflowStore.getState().loadDocument(parsed.document);
          }
        }
      } catch (e) {
        setTabChatItems((prev) => ({
          ...prev,
          [stageId]: [...(prev[stageId] || []), { id: nextId(), kind: "agent", text: `⚠ ${e instanceof Error ? e.message : "Could not process that file."}` }],
        }));
      } finally {
        setBusy(false);
        setTypingAuthor(null);
      }
    },
    [projectId, busy, kickoffAwaitingInput, applyKickoffContext],
  );

  // Composer's single upload button is shared across all four stage tabs -- Stage 1 fills
  // the brief from a brand plan, Stages 2-4 route through the tab-scoped uploader above.
  const handleUpload = useCallback(
    (file: File) => {
      if (stage === 1) { uploadFile(file); return; }
      uploadTabDocument(STAGE_ORDER[stage - 1], file);
    },
    [stage, uploadFile, uploadTabDocument],
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
          { id: nextId(), kind: "agent", text: `Here's how ${reviews.length} of your target personas reacted. Honest feedback, in their words:` },
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
        // The rebalance changes the ctx the Campaign Brief projects from — tell
        // the artifacts panel to refetch so brief and plan never disagree.
        setArtifactRefresh((prev) => ({ ...prev, planning: prev.planning + 1 }));
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
      setItems((prev) => [...prev, { id: nextId(), kind: "agent", text: "🔒 Updates closed. This plan is locked in. I won't auto-adjust it further." }]);
    } catch {
      /* best-effort, mirrors legacy */
    }
  }, [projectId, markPlanFrozen]);

  const renameProjectAction = useCallback(
    async (name: string) => {
      if (!projectId) return;
      const trimmed = name.trim();
      if (!trimmed || trimmed === projectName) return;
      setProjectName(trimmed);
      try {
        await renameProject(projectId, trimmed);
        refreshProjects();
      } catch {
        setProjectName(projectName); // revert on failure
      }
    },
    [projectId, projectName, refreshProjects],
  );

  const deleteProjectAction = useCallback(
    async (id: string) => {
      await deleteProject(id);
      refreshProjects();
      if (id === projectId) {
        setProjectId(null);
        setProjectName("");
        setItems([]);
        setResult(null);
        setPlanHtml(null);
        setPlanMarkdown(null);
      }
    },
    [projectId, refreshProjects],
  );

  const activeChatItems = stage === 1 ? items : tabChatItems[STAGE_ORDER[stage - 1]] || [];

  return {
    projects,
    projectId,
    projectName,
    renameProject: renameProjectAction,
    deleteProject: deleteProjectAction,
    slots,
    inferred,
    items,
    activeChatItems,
    activeAgentId: STAGE_ORDER[stage - 1],
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
    revealedPhases,
    sectionsProgress,
    profileOpen: openPersonaId,
    newProject,
    openProject,
    sendMessage,
    uploadFile,
    handleUpload,
    kickoffAwaitingStage: kickoffAwaitingInput,
    onKickoffUsePlan,
    onKickoffWantUpload,
    artifactRefresh,
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
    studio,
    typingAuthor,
    answerStudioAsk,
    skipStudioPacing,
    continueStudioSection,
  };
}
