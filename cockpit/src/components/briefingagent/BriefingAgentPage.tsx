import { useEffect, useRef, useState } from "react";
import { getBrandTree, getCampaignArtifacts, getStudioProject, listBrands, postBriefChat, postStudioAnswer, startCampaignPlan } from "../../api";
import type { BrandSummary, BrandTree, CampaignArtifactsPayload, TreeCampaign, TreePlan } from "../../types";
import { Icon } from "../Icon";
import { periodLabel } from "../hierarchy/shared";
import { PickerModal, type PickerItem } from "../flowplanner/PickerModal";

/**
 * Briefing Agent wizard: the same brand -> engagement plan -> campaign chat wizard as the
 * Flow Planner (plan-launcher-backdrop/plan-launcher-card.fp-wide, wiz-choice-grid, the
 * chat-bubble acknowledge/ask/clarify pattern, inline pickers, minimize-and-reopen) --
 * deliberately duplicated rather than shared, so the two pages can keep evolving their own
 * copy and pacing independently. Where it differs: the terminal step doesn't build an SVG
 * diagram, it composes the real Campaign Strategy + Campaign Brief that already exist in this
 * app -- strategy/campaign_artifacts.py, the same deterministic-from-ctx process the old
 * Project Studio's own Campaign Artifacts page (frontend/src/workspace/CampaignArtifacts.tsx)
 * renders -- reached here via the campaign's own `project_id`. A campaign that was never
 * planned through that Stage 1 (no `project_id`) can now run it right here: "no-plan" offers
 * to start it, "brief-chat" is the real free-text intake loop (strategy/conversation.py's
 * interpret_message via /api/chat) that captures brand/budget/lifecycle until it returns
 * `action: "run"`, and "stage1" drives the real 11-step question sequence (strategy/
 * studio_run.py) over its actual SSE protocol (GET /api/studio/stream, POST /api/studio/answer)
 * -- the same endpoints the old Project Studio pages use, not a reimplementation. Each ask's
 * own `text` already reads as a complete recommendation in prose ("Your broad target is
 * **X**... Lock this, or steer it another way?"), so this renders it as a single free-text
 * question rather than porting the old UI's separate recommendation/evidence/option-chip
 * layout -- a real simplification, not a fake one: nothing here is invented, the full payload
 * (evidence_basis, options, recommendation) still exists on the event, just not all surfaced.
 * On `run_done`, strategy/campaign_artifacts.py's own persistence mints the resulting campaign
 * record from the plan (strategy/campaign_store.py's persist_campaign_from_result) -- it is
 * not guaranteed to be the exact campaign object this wizard started from; a mismatch here is
 * a known, accepted follow-up rather than something this page tries to reconcile. */

function FlowPlannerTextRow({ text, setText, onSend, thinking, placeholder }: {
  text: string; setText: (v: string) => void; onSend: () => void; thinking: boolean; placeholder: string;
}) {
  return (
    <div className="wiz-text-block">
      <form className="wiz-text-row wiz-text-row-highlight" onSubmit={(e) => { e.preventDefault(); onSend(); }}>
        <input className="wiz-text-input" placeholder={placeholder} value={text} disabled={thinking}
          onChange={(e) => setText(e.target.value)} />
        <button type="submit" className="wiz-text-send" disabled={thinking || !text.trim()} aria-label="Send">
          <Icon name="arrowRight" size={15} />
        </button>
      </form>
      {thinking && <div className="wiz-thinking"><span /><span /><span /> Thinking&hellip;</div>}
    </div>
  );
}

function seeded(seed: string): number {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  return (h % 1000) / 1000;
}

const ILLUSTRATIVE_COMPANIES = ["Aurelia Biosciences", "Meridian Therapeutics", "Northgate Pharma", "Solace Bio", "Vantree Sciences"];
const ILLUSTRATIVE_FOCUS = ["cardiometabolic disease", "oncology", "immunology", "neurology", "rare disease"];
const ILLUSTRATIVE_STAGE = ["pre-launch", "early launch", "in-market growth", "lifecycle expansion", "loss-of-exclusivity defense"];

function brandDetail(b: BrandSummary) {
  const real = Boolean(b.company || b.generic || b.therapy_area);
  const r = seeded(b.brand);
  const company = b.company || ILLUSTRATIVE_COMPANIES[Math.floor(r * ILLUSTRATIVE_COMPANIES.length)];
  const generic = b.generic || `${b.brand.toLowerCase()}umab — illustrative compound name`;
  const focus = b.therapy_area || ILLUSTRATIVE_FOCUS[Math.floor(seeded(b.brand + "focus") * ILLUSTRATIVE_FOCUS.length)];
  const stage = ILLUSTRATIVE_STAGE[Math.floor(seeded(b.brand + "stage") * ILLUSTRATIVE_STAGE.length)];
  const indication = b.indication || `A representative patient population in ${focus}.`;
  return { real, company, generic, focus, stage, indication };
}

type Step =
  | { kind: "ask-brand" }
  | { kind: "ask-engagement" }
  | { kind: "ask-campaign" }
  | { kind: "no-plan" }
  | { kind: "brief-chat" }
  | { kind: "stage1" }
  | { kind: "briefing" }
  | { kind: "ready" }
  | { kind: "stub"; message: string };

/** One Stage 1 question, as strategy/studio_run.py's "ask" event carries it. `text` already
 *  reads as a complete, grounded recommendation in prose -- see the file doc comment. */
type StudioAsk = { ask_id: string; text: string };

type PickerKind = "brand" | "engagement" | "campaign" | null;

type Phase =
  | { kind: "idle" }
  | { kind: "active"; mode: "opening"; userText: string; lines: string[]; line: number; target: Exclude<PickerKind, null> }
  | { kind: "active"; mode: "closing"; userText: string; lines: string[]; line: number; next: Step }
  | { kind: "clarify"; userText: string; message: string; suggestions: Suggestion[]; onShowList: () => void };

type Suggestion = { label: string; onPick: () => void };

function closeMatches<T>(items: T[], nameOf: (t: T) => string, query: string, limit = 3): T[] {
  const q = query.toLowerCase().trim();
  const scored = items.map((it) => {
    const n = nameOf(it).toLowerCase();
    let score = 0;
    if (n === q) score = 4;
    else if (n.startsWith(q)) score = 3;
    else if (n.includes(q)) score = 2;
    else if (q.length > 2 && q.split(/\s+/).some((w) => w.length > 2 && n.includes(w))) score = 1;
    return { it, score };
  });
  const matched = scored.filter((s) => s.score > 0).sort((a, b) => b.score - a.score);
  return (matched.length > 0 ? matched : scored).slice(0, limit).map((s) => s.it);
}

const BRIEFING_LINES = [
  "Retrieving the campaign's saved planning context…",
  "Compiling the Campaign Strategy's decision records…",
  "Assembling the Campaign Brief…",
];

function askLineFor(step: Step, brand: BrandSummary | null, plan: TreePlan | null): string[] {
  switch (step.kind) {
    case "ask-brand":
      return [
        "Good day. Let us proceed to compile a campaign brief.",
        "Would you prefer to begin with a new brand, or would you like to select one of your existing brands?",
      ];
    case "ask-engagement":
      return [
        `Understood. I have set the brand to ${brand?.brand ?? "the brand you selected"}.`,
        "Would you like to create a new engagement plan, or would you prefer to choose from the plans already associated with this brand?",
      ];
    case "ask-campaign":
      return [
        `This brief will be compiled under the engagement plan “${plan?.name ?? "the plan you selected"}.”`,
        "Would you like to create a new campaign, or would you prefer to select an existing campaign from this plan?",
      ];
    default:
      return [];
  }
}

export function BriefingAgentPage() {
  const [step, setStep] = useState<Step>({ kind: "ask-brand" });
  const [picker, setPicker] = useState<PickerKind>(null);
  const [text, setText] = useState("");
  const [sentText, setSentText] = useState("");
  const [thinking, setThinking] = useState(false);
  const [cardOpen, setCardOpen] = useState(true);
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });

  const [brands, setBrands] = useState<BrandSummary[] | null>(null);
  const [brand, setBrand] = useState<BrandSummary | null>(null);
  const [tree, setTree] = useState<BrandTree | null>(null);
  const [plan, setPlan] = useState<TreePlan | null>(null);
  const [campaign, setCampaign] = useState<TreeCampaign | null>(null);
  const [briefingLine, setBriefingLine] = useState(0);
  const [artifacts, setArtifacts] = useState<CampaignArtifactsPayload | null>(null);

  // Stage 1 (strategy/conversation.py + strategy/studio_run.py), run right here when the
  // picked campaign has no project yet -- see the file doc comment for the full protocol.
  const [projectId, setProjectId] = useState<string | null>(null);
  const [lastAgentLine, setLastAgentLine] = useState("");
  const [briefThinking, setBriefThinking] = useState(false);
  const [briefText, setBriefText] = useState("");
  const [askPending, setAskPending] = useState<StudioAsk | null>(null);
  const [stage1Text, setStage1Text] = useState("");
  const [stage1Thinking, setStage1Thinking] = useState(false);
  const [narrationLines, setNarrationLines] = useState<string[]>([]);
  const [stage1Error, setStage1Error] = useState<string | null>(null);
  const [resumeToken, setResumeToken] = useState(0);
  const esRef = useRef<EventSource | null>(null);

  const effectiveProjectId = projectId ?? campaign?.project_id ?? null;

  useEffect(() => { listBrands().then((r) => setBrands(r.brands)).catch(() => setBrands([])); }, []);

  /** The terminal fetch: composes the real Campaign Strategy + Campaign Brief once a project
   *  exists (either the campaign already had one, or Stage 1 just produced one below). A
   *  campaign with neither is routed to "no-plan" instead of stubbed outright, since Stage 1
   *  can now be run from right here. */
  useEffect(() => {
    if (step.kind !== "briefing" || !campaign) return;
    let cancelled = false;

    if (!effectiveProjectId) {
      setStep({ kind: "no-plan" });
      return;
    }

    setBriefingLine(0);
    const id = setInterval(() => {
      if (!cancelled) setBriefingLine((i) => (i + 1 < BRIEFING_LINES.length ? i + 1 : i));
    }, 650);

    getCampaignArtifacts(effectiveProjectId)
      .then((data) => {
        if (cancelled) return;
        clearInterval(id);
        setArtifacts(data);
        setTimeout(() => { if (!cancelled) { setCardOpen(true); setStep({ kind: "ready" }); } }, 400);
      })
      .catch((e) => {
        if (cancelled) return;
        clearInterval(id);
        setStep({ kind: "stub", message: `I was unable to retrieve the Campaign Brief for ${campaign.name}. ${e instanceof Error ? e.message : String(e)}` });
      });
    return () => { cancelled = true; clearInterval(id); };
  }, [step.kind, campaign, effectiveProjectId]);

  /** Stage 1's own SSE protocol: the stream ends at every grounded ask (server-side, by
   *  design), so this reopens it fresh each time `resumeToken` bumps after an answer is
   *  recorded, and never while an ask is actually pending an answer. */
  useEffect(() => {
    if (step.kind !== "stage1" || !projectId || askPending) return;
    setStage1Error(null);
    setNarrationLines([]);
    const es = new EventSource(`/api/studio/stream?project_id=${encodeURIComponent(projectId)}`);
    esRef.current = es;
    es.onmessage = (ev) => {
      let data: Record<string, unknown>;
      try { data = JSON.parse(ev.data); } catch { return; }
      if (data.type === "chat" && typeof data.text === "string") {
        setNarrationLines((prev) => [...prev.slice(-3), data.text as string]);
      } else if (data.type === "ask" && !data.auto_assumed) {
        es.close();
        setAskPending({ ask_id: String(data.ask_id), text: String(data.text ?? "") });
      } else if (data.type === "run_done") {
        es.close();
        setStep({ kind: "briefing" });
      } else if (data.type === "error") {
        es.close();
        setStage1Error(typeof data.message === "string" ? data.message : "Planning Stage 1 failed unexpectedly.");
      }
    };
    es.onerror = () => {
      // A network drop mid-stream (not the server's own deliberate close-at-ask, which we
      // already close ourselves above before this could fire) -- surface it rather than
      // leaving the loading state spinning forever.
      es.close();
      setStage1Error((prev) => prev ?? "Lost the connection to Planning Stage 1. You can try again.");
    };
    return () => { es.close(); };
  }, [step.kind, projectId, resumeToken, askPending]);

  const startPlanning = async () => {
    if (!campaign) return;
    setStep({ kind: "brief-chat" });
    setBriefThinking(true);
    try {
      // Bound to the campaign at creation (F3): when Stage 1 finishes, its plan updates THIS
      // campaign instead of persist_campaign_from_result minting a duplicate.
      const started = await startCampaignPlan(campaign.id);
      const proj = await getStudioProject(started.project.id);
      setProjectId(proj.id);
      const agentMsgs = proj.messages.filter((m) => m.role === "agent");
      const opening = agentMsgs[agentMsgs.length - 1]?.text
        ?? "Tell me about this campaign's brand, indication and budget, and I'll take it from there.";
      setLastAgentLine(opening);
    } catch (e) {
      setStep({ kind: "stub", message: `I was unable to start Planning for ${campaign.name}. ${e instanceof Error ? e.message : String(e)}` });
    } finally {
      setBriefThinking(false);
    }
  };

  const sendBrief = async () => {
    const value = briefText.trim();
    if (!value || !projectId || briefThinking) return;
    setBriefText("");
    setBriefThinking(true);
    try {
      const r = await postBriefChat(projectId, value);
      setLastAgentLine(r.reply);
      if (r.action === "run") setStep({ kind: "stage1" });
    } catch (e) {
      setLastAgentLine(`I ran into a problem recording that: ${e instanceof Error ? e.message : String(e)}. Could you try again?`);
    } finally {
      setBriefThinking(false);
    }
  };

  const sendStage1Answer = async () => {
    const value = stage1Text.trim();
    if (!value || !projectId || !askPending || stage1Thinking) return;
    setStage1Text("");
    setStage1Thinking(true);
    try {
      await postStudioAnswer(projectId, askPending.ask_id, value);
      setAskPending(null);
      setResumeToken((t) => t + 1);
    } catch (e) {
      setStage1Error(e instanceof Error ? e.message : String(e));
    } finally {
      setStage1Thinking(false);
    }
  };

  useEffect(() => {
    if (phase.kind !== "active") return;
    if (phase.line + 1 < phase.lines.length) {
      const id = setTimeout(() => setPhase((p) => (p.kind === "active" ? { ...p, line: p.line + 1 } as Phase : p)), 600);
      return () => clearTimeout(id);
    }
    const id = setTimeout(() => {
      setPhase((p) => {
        if (p.kind !== "active") return p;
        if (p.mode === "opening") setPicker(p.target);
        else setStep(p.next);
        return { kind: "idle" };
      });
    }, 550);
    return () => clearTimeout(id);
  }, [phase]);

  const openPicker = (target: Exclude<PickerKind, null>, userText: string, lines: string[]) =>
    setPhase({ kind: "active", mode: "opening", userText, lines, line: 0, target });
  const advance = (next: Step, userText: string, lines: string[]) =>
    setPhase({ kind: "active", mode: "closing", userText, lines, line: 0, next });

  const chooseBrandKind = (kind: "new" | "existing") => {
    if (kind === "new") {
      advance({ kind: "stub", message: "New-brand flows have not yet been built. Please proceed by selecting an existing brand instead." },
        "New brand", [
          "Understood. You have requested a new brand.",
          "This capability has not yet been built, so allow me to proceed with an existing brand instead.",
        ]);
      return;
    }
    openPicker("brand", "Existing brand", [
      "Understood. You have chosen to proceed with an existing brand.",
      "One moment, please, while I retrieve your available brand kits.",
    ]);
  };
  const chooseEngagementKind = (kind: "new" | "existing") => {
    if (kind === "new") {
      advance({ kind: "stub", message: "New-engagement flows have not yet been built. Please proceed by selecting an existing engagement plan instead." },
        "New engagement", [
          "Understood. You have requested a new engagement plan.",
          "This capability has not yet been built, so allow me to proceed with an existing plan instead.",
        ]);
      return;
    }
    openPicker("engagement", "Existing engagement", [
      `Understood. You have chosen to proceed with an existing engagement plan for ${brand?.brand ?? "this brand"}.`,
      "One moment, please, while I retrieve the available plans.",
    ]);
  };
  const chooseCampaignKind = (kind: "existing" | "adhoc") => {
    if (kind === "adhoc") {
      advance({ kind: "stub", message: "Ad-hoc campaign flows have not yet been built. Please proceed by selecting an existing campaign instead." },
        "Ad-hoc campaign", [
          "Understood. You have requested an ad-hoc campaign.",
          "This capability has not yet been built, so allow me to proceed with an existing campaign instead.",
        ]);
      return;
    }
    openPicker("campaign", "Existing campaign", [
      `Understood. You have chosen to proceed with an existing campaign under ${plan?.name ?? "this plan"}.`,
      "One moment, please, while I retrieve the available campaigns.",
    ]);
  };

  const resolveFromBrand = async (b: BrandSummary, t: string, userText: string) => {
    setBrand(b);
    setTree(null);
    const bt = await getBrandTree(b.brand).catch(() => ({ brand: b.brand, engagement_plans: [] }) as BrandTree);
    setTree(bt);
    const p = bt.engagement_plans.find((x) => t.includes(x.name.toLowerCase()));
    if (!p) {
      advance({ kind: "ask-engagement" }, userText, [
        `Understood. The brand has been set to ${b.brand}.`,
        "I am now reviewing its associated engagement plans.",
      ]);
      return;
    }
    setPlan(p);
    const c = p.campaigns.find((x) => t.includes(x.name.toLowerCase()));
    if (!c) {
      advance({ kind: "ask-campaign" }, userText, [
        `Understood. The brand and engagement plan have been set to ${b.brand} and “${p.name}.”`,
        "I am now retrieving this plan's campaigns.",
      ]);
      return;
    }
    setCampaign(c);
    advance({ kind: "briefing" }, userText, [
      `Understood. I have set the brand to ${b.brand}, the engagement plan to “${p.name},” and the campaign to “${c.name}.”`,
      "I will now begin compiling the campaign brief.",
    ]);
  };
  const resolveFromPlan = (p: TreePlan, t: string, userText: string) => {
    setPlan(p);
    const c = p.campaigns.find((x) => t.includes(x.name.toLowerCase()));
    if (!c) {
      advance({ kind: "ask-campaign" }, userText, [
        `Understood. The engagement plan has been set to “${p.name}.”`,
        "I am now retrieving this plan's campaigns.",
      ]);
      return;
    }
    setCampaign(c);
    advance({ kind: "briefing" }, userText, [
      `Understood. The engagement plan has been set to “${p.name}” and the campaign to “${c.name}.”`,
      "I will now begin compiling the campaign brief.",
    ]);
  };
  const resolveFromCampaign = (c: TreeCampaign, userText: string) => {
    setCampaign(c);
    advance({ kind: "briefing" }, userText, [
      `Understood. The campaign has been set to “${c.name}.”`,
      "I will now begin compiling the campaign brief.",
    ]);
  };

  const onPickBrand = (b: BrandSummary) => { setPicker(null); void resolveFromBrand(b, "", b.brand); };
  const onPickPlan = (p: TreePlan) => { setPicker(null); resolveFromPlan(p, "", p.name); };
  const onPickCampaign = (c: TreeCampaign) => { setPicker(null); resolveFromCampaign(c, c.name); };

  const restart = () => {
    esRef.current?.close();
    setStep({ kind: "ask-brand" });
    setBrand(null); setTree(null); setPlan(null); setCampaign(null); setText(""); setSentText(""); setThinking(false);
    setCardOpen(true); setArtifacts(null); setPhase({ kind: "idle" });
    setProjectId(null); setLastAgentLine(""); setBriefThinking(false); setBriefText("");
    setAskPending(null); setStage1Text(""); setStage1Thinking(false); setNarrationLines([]);
    setStage1Error(null); setResumeToken(0);
  };

  const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

  const send = async () => {
    const raw = text.trim();
    if (!raw || thinking) return;
    const t = raw.toLowerCase();
    setText("");
    setSentText(raw);
    setThinking(true);
    await sleep(550);

    try {
      if (step.kind === "ask-brand") {
        if (t.includes("new")) { chooseBrandKind("new"); return; }
        const b = (brands ?? []).find((x) => t.includes(x.brand.toLowerCase()));
        if (!b) {
          const guesses = closeMatches(brands ?? [], (x) => x.brand, raw);
          setPhase({
            kind: "clarify", userText: raw,
            message: `I was unable to find a brand named "${raw}." Did you perhaps mean one of the following, or would you prefer to view the complete list?`,
            suggestions: guesses.map((g) => ({ label: g.brand, onPick: () => void resolveFromBrand(g, g.brand.toLowerCase(), g.brand) })),
            onShowList: () => openPicker("brand", "Show me the full list", ["Very well. Allow me to present your complete brand list."]),
          });
          return;
        }
        await resolveFromBrand(b, t, raw);
      } else if (step.kind === "ask-engagement") {
        if (t.includes("new")) { chooseEngagementKind("new"); return; }
        const p = (tree?.engagement_plans ?? []).find((x) => t.includes(x.name.toLowerCase()));
        if (!p) {
          const guesses = closeMatches(tree?.engagement_plans ?? [], (x) => x.name, raw);
          setPhase({
            kind: "clarify", userText: raw,
            message: `I was unable to find an engagement plan named "${raw}" under ${brand?.brand}. Did you perhaps mean one of the following, or would you prefer to view the complete list?`,
            suggestions: guesses.map((g) => ({ label: g.name, onPick: () => resolveFromPlan(g, g.name.toLowerCase(), g.name) })),
            onShowList: () => openPicker("engagement", "Show me the full list", [`Very well. Allow me to present the complete list of plans for ${brand?.brand}.`]),
          });
          return;
        }
        resolveFromPlan(p, t, raw);
      } else if (step.kind === "ask-campaign") {
        if (t.includes("adhoc") || t.includes("ad-hoc") || t.includes("ad hoc")) { chooseCampaignKind("adhoc"); return; }
        const c = (plan?.campaigns ?? []).find((x) => t.includes(x.name.toLowerCase()));
        if (!c) {
          const guesses = closeMatches(plan?.campaigns ?? [], (x) => x.name, raw);
          setPhase({
            kind: "clarify", userText: raw,
            message: `I was unable to find a campaign named "${raw}" under ${plan?.name}. Did you perhaps mean one of the following, or would you prefer to view the complete list?`,
            suggestions: guesses.map((g) => ({ label: g.name, onPick: () => resolveFromCampaign(g, g.name) })),
            onShowList: () => openPicker("campaign", "Show me the full list", [`Very well. Allow me to present the complete list of campaigns for ${plan?.name}.`]),
          });
          return;
        }
        resolveFromCampaign(c, raw);
      }
    } finally {
      setThinking(false);
    }
  };

  const brandItems: PickerItem<BrandSummary>[] = (brands ?? []).map((b) => ({
    id: b.brand, title: b.brand, subtitle: b.indication || b.therapy_area, value: b,
  }));
  const planItems: PickerItem<TreePlan>[] = (tree?.engagement_plans ?? []).map((p) => ({
    id: String(p.id), title: p.name, subtitle: periodLabel(p.period_start, p.period_end) ?? p.status, value: p,
  }));
  const campaignItems: PickerItem<TreeCampaign>[] = (plan?.campaigns ?? []).map((c) => ({
    id: String(c.id), title: c.name, subtitle: `${c.status} · ${c.flow_count} flow${c.flow_count === 1 ? "" : "s"}`, value: c,
  }));

  return (
    <div className="hier-page flow-planner-page">
      <div className="hier-head">
        <div>
          <div className="kit-update-eyebrow">Agent Library</div>
          <h1 className="kit-update-title">Briefing Agent</h1>
        </div>
      </div>

      {step.kind === "ready" && artifacts && (
        <div className="briefing-canvas">
          <BriefingDocument data={artifacts} />
        </div>
      )}

      {!cardOpen && (
        <button type="button" className="plan-launcher-fab fp-reopen-fab" aria-label="Reopen Briefing Agent" onClick={() => setCardOpen(true)}>
          <Icon name="sparkles" size={24} />
        </button>
      )}
      {cardOpen && <div className="plan-launcher-backdrop" onClick={() => setCardOpen(false)} />}
      {cardOpen && (
      <div className={`plan-launcher-card fp-wide ${picker ? "fp-expanded" : ""}`} role="dialog" aria-modal="true" aria-label="Briefing Agent">
        <button type="button" className="plan-launcher-close" aria-label="Minimize" onClick={() => setCardOpen(false)}>
          <Icon name="close" size={16} />
        </button>
        {picker === "brand" ? (
          <div className="fp-chat">
            <div className="flow-editor-msg flow-editor-msg-agent">Please review the list below and select the brand you would like to proceed with.</div>
            <PickerModal variant="inline" title="Select a brand" items={brandItems} onSelect={onPickBrand} onClose={() => setPicker(null)}
              renderDetail={(b) => {
                const d = brandDetail(b);
                return (
                  <div className="hier-detail-card">
                    <div className="hier-detail-head">
                      <div><span className="hier-detail-name">{b.brand}</span></div>
                      {!d.real && <span className="illustrative-tag">Illustrative</span>}
                    </div>
                    <p className="hier-detail-summary">{d.indication}</p>
                    <div className="hier-punch-card">
                      <span className="hier-punch-icon"><Icon name="target" size={18} /></span>
                      <div className="hier-punch-body">
                        <div className="hier-detail-subhead">Brand</div>
                        <p className="hier-objective-text">{d.company} · {d.generic}</p>
                      </div>
                    </div>
                    <div className="hier-punch-card">
                      <span className="hier-punch-icon"><Icon name="layers" size={18} /></span>
                      <div className="hier-punch-body">
                        <div className="hier-detail-subhead">Focus &amp; stage</div>
                        <p className="hier-objective-text">{d.focus}, {d.stage}</p>
                      </div>
                    </div>
                    <div>
                      <div className="hier-detail-subhead">Territories</div>
                      <p className="hier-detail-summary">
                        {b.territories.length > 0 ? b.territories.join(", ") : "Not yet configured for a territory."}
                      </p>
                    </div>
                  </div>
                );
              }} />
          </div>
        ) : picker === "engagement" ? (
          <div className="fp-chat">
            <div className="flow-editor-msg flow-editor-msg-agent">Please review {brand?.brand}&rsquo;s engagement plans below and select the one you would like to proceed with.</div>
            <PickerModal variant="inline" title={`Select an engagement plan in ${brand?.brand}`} items={planItems} onSelect={onPickPlan} onClose={() => setPicker(null)}
              renderDetail={(p) => (
                <div className="hier-detail-card">
                  <div className="hier-detail-head"><div><span className="hier-detail-name">{p.name}</span></div></div>
                  <p className="hier-detail-summary">{periodLabel(p.period_start, p.period_end) ?? "No period set"} · {p.status}</p>
                  <p className="hier-detail-summary">{p.campaigns.length} campaign{p.campaigns.length === 1 ? "" : "s"}</p>
                </div>
              )} />
          </div>
        ) : picker === "campaign" ? (
          <div className="fp-chat">
            <div className="flow-editor-msg flow-editor-msg-agent">Please review {plan?.name}&rsquo;s campaigns below and select the one you would like to proceed with.</div>
            <PickerModal variant="inline" title={`Select a campaign in ${plan?.name}`} items={campaignItems} onSelect={onPickCampaign} onClose={() => setPicker(null)}
              renderDetail={(c) => (
                <div className="hier-detail-card">
                  <div className="hier-detail-head"><div><span className="hier-detail-name">{c.name}</span></div></div>
                  <p className="hier-detail-summary">{c.status} · {c.flow_count} flow{c.flow_count === 1 ? "" : "s"}</p>
                  {!c.project_id && <p className="hier-detail-summary">This campaign has no Campaign Plan yet, so a brief cannot be compiled from it.</p>}
                </div>
              )} />
          </div>
        ) : phase.kind === "active" ? (
          <div className="fp-chat">
            {askLineFor(step, brand, plan).map((line, i) => (
              <div key={i} className="flow-editor-msg flow-editor-msg-agent flow-editor-msg-anchor">{line}</div>
            ))}
            <div className="flow-editor-msg flow-editor-msg-user">{phase.userText}</div>
            {phase.lines.slice(0, phase.line + 1).map((line, i) => (
              <div key={i} className="flow-editor-msg flow-editor-msg-agent">{line}</div>
            ))}
            {phase.line < phase.lines.length - 1 && (
              <div className="flow-editor-msg flow-editor-msg-agent flow-editor-msg-pending"><span /><span /><span /></div>
            )}
          </div>
        ) : phase.kind === "clarify" ? (
          <div className="fp-chat">
            {askLineFor(step, brand, plan).map((line, i) => (
              <div key={i} className="flow-editor-msg flow-editor-msg-agent flow-editor-msg-anchor">{line}</div>
            ))}
            <div className="flow-editor-msg flow-editor-msg-user">{phase.userText}</div>
            <div className="flow-editor-msg flow-editor-msg-agent">{phase.message}</div>
            <div className="fp-quick-replies">
              {phase.suggestions.map((s) => (
                <button key={s.label} type="button" className="fp-chip" onClick={() => { const pick = s.onPick; setPhase({ kind: "idle" }); pick(); }}>
                  {s.label}
                </button>
              ))}
              <button type="button" className="fp-chip fp-chip-muted" onClick={() => { const show = phase.onShowList; setPhase({ kind: "idle" }); show(); }}>
                Show me the full list
              </button>
            </div>
            <FlowPlannerTextRow text={text} setText={setText} onSend={send} thinking={thinking} placeholder="Or try another name…" />
          </div>
        ) : thinking ? (
          <div className="fp-chat">
            {askLineFor(step, brand, plan).map((line, i) => (
              <div key={i} className="flow-editor-msg flow-editor-msg-agent flow-editor-msg-anchor">{line}</div>
            ))}
            <div className="flow-editor-msg flow-editor-msg-user">{sentText}</div>
            <div className="flow-editor-msg flow-editor-msg-agent flow-editor-msg-pending"><span /><span /><span /></div>
          </div>
        ) : (
        <>
        {step.kind === "ask-brand" && (
          <div className="fp-chat">
            {askLineFor(step, brand, plan).map((line, i) => (
              <div key={i} className="flow-editor-msg flow-editor-msg-agent flow-editor-msg-anchor">{line}</div>
            ))}
            <div className="wiz-choice-grid">
              <button type="button" className="wiz-choice-card" onClick={() => chooseBrandKind("new")}>
                <Icon name="sparkles" size={22} />
                <b>New brand</b>
                <span>Not built yet.</span>
              </button>
              <button type="button" className="wiz-choice-card" onClick={() => chooseBrandKind("existing")}>
                <Icon name="target" size={22} />
                <b>Existing brand</b>
                <span>Pick from your brand kits.</span>
              </button>
            </div>
            <FlowPlannerTextRow text={text} setText={setText} onSend={send} thinking={thinking}
              placeholder={`Or name a brand, e.g. "${brands?.[0]?.brand ?? "Cardiovex"}"`} />
          </div>
        )}
        {step.kind === "ask-engagement" && (
          <div className="fp-chat">
            {askLineFor(step, brand, plan).map((line, i) => (
              <div key={i} className="flow-editor-msg flow-editor-msg-agent flow-editor-msg-anchor">{line}</div>
            ))}
            <div className="wiz-choice-grid">
              <button type="button" className="wiz-choice-card" onClick={() => chooseEngagementKind("new")}>
                <Icon name="sparkles" size={22} />
                <b>New engagement</b>
                <span>Not built yet.</span>
              </button>
              <button type="button" className="wiz-choice-card" onClick={() => chooseEngagementKind("existing")}>
                <Icon name="document" size={22} />
                <b>Existing engagement</b>
                <span>Pick from {brand?.brand}&rsquo;s plans.</span>
              </button>
            </div>
            <FlowPlannerTextRow text={text} setText={setText} onSend={send} thinking={thinking}
              placeholder={`Or name a plan, e.g. "${tree?.engagement_plans[0]?.name ?? "Q4 2026 Launch Push"}"`} />
          </div>
        )}
        {step.kind === "ask-campaign" && (
          <div className="fp-chat">
            {askLineFor(step, brand, plan).map((line, i) => (
              <div key={i} className="flow-editor-msg flow-editor-msg-agent flow-editor-msg-anchor">{line}</div>
            ))}
            <div className="wiz-choice-grid">
              <button type="button" className="wiz-choice-card" onClick={() => chooseCampaignKind("existing")}>
                <Icon name="document" size={22} />
                <b>Existing campaign</b>
                <span>Pick from this plan&rsquo;s campaigns.</span>
              </button>
              <button type="button" className="wiz-choice-card" onClick={() => chooseCampaignKind("adhoc")}>
                <Icon name="zap" size={22} />
                <b>Ad-hoc campaign</b>
                <span>Not built yet.</span>
              </button>
            </div>
            <FlowPlannerTextRow text={text} setText={setText} onSend={send} thinking={thinking}
              placeholder={`Or name a campaign, e.g. "${plan?.campaigns[0]?.name ?? "Payer Access Follow-up"}"`} />
          </div>
        )}
        {step.kind === "no-plan" && (
          <div className="fp-chat">
            <div className="flow-editor-msg flow-editor-msg-agent">
              {campaign?.name} does not yet have a Campaign Plan, so there is nothing to compile a brief from yet.
            </div>
            <div className="flow-editor-msg flow-editor-msg-agent">
              Would you like me to run Planning Stage 1 for it now? This runs the full planning question set and will take several minutes.
            </div>
            <div className="fp-quick-replies">
              <button type="button" className="fp-chip" onClick={startPlanning}>Run Planning now</button>
              <button type="button" className="fp-chip fp-chip-muted" onClick={() => setStep({ kind: "stub", message: `Understood. ${campaign?.name} still has no Campaign Plan to compile a brief from.` })}>
                Not now
              </button>
            </div>
          </div>
        )}
        {step.kind === "brief-chat" && (
          <div className="fp-chat">
            <div className="flow-editor-msg flow-editor-msg-agent">{lastAgentLine}</div>
            {briefThinking && (
              <div className="flow-editor-msg flow-editor-msg-agent flow-editor-msg-pending"><span /><span /><span /></div>
            )}
            <FlowPlannerTextRow text={briefText} setText={setBriefText} onSend={sendBrief} thinking={briefThinking}
              placeholder="e.g. brand, indication, lifecycle stage, budget…" />
          </div>
        )}
        {step.kind === "stage1" && (
          <div className="fp-chat">
            {askPending ? (
              <>
                <div className="flow-editor-msg flow-editor-msg-agent">{askPending.text}</div>
                {stage1Thinking && (
                  <div className="flow-editor-msg flow-editor-msg-agent flow-editor-msg-pending"><span /><span /><span /></div>
                )}
                <FlowPlannerTextRow text={stage1Text} setText={setStage1Text} onSend={sendStage1Answer} thinking={stage1Thinking}
                  placeholder="Your answer…" />
              </>
            ) : stage1Error ? (
              <>
                <div className="flow-editor-msg flow-editor-msg-agent">{stage1Error}</div>
                <div className="fp-quick-replies">
                  <button type="button" className="fp-chip" onClick={() => { setStage1Error(null); setResumeToken((t) => t + 1); }}>Try again</button>
                  <button type="button" className="fp-chip fp-chip-muted" onClick={restart}>Start over</button>
                </div>
              </>
            ) : (
              <div className="fp-loading">
                <div className="fp-loading-head">
                  <span className="fp-loading-spinner"><Icon name="sparkles" size={18} /></span>
                  <span>Running Planning Stage 1&hellip;</span>
                </div>
                <div className="fp-loading-lines">
                  {(narrationLines.length > 0 ? narrationLines : ["Assembling your planning team…"]).map((line, i) => (
                    <div key={i} className="fp-loading-line is-active"><span className="fp-loading-dot" /><span>{line}</span></div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
        {step.kind === "briefing" && (
          <div className="fp-chat">
            {BRIEFING_LINES.slice(0, briefingLine + 1).map((line, i) => (
              <div key={i} className="flow-editor-msg flow-editor-msg-agent">{line}</div>
            ))}
            {briefingLine < BRIEFING_LINES.length - 1 && (
              <div className="flow-editor-msg flow-editor-msg-agent flow-editor-msg-pending"><span /><span /><span /></div>
            )}
          </div>
        )}
        {step.kind === "ready" && (
          <>
            <h3>Campaign Brief ready for {campaign?.name}.</h3>
            <p className="flow-planner-ready-hint">Close this card to read the full brief.</p>
            <button type="button" className="wiz-big-btn" onClick={restart}>
              Start another briefing <Icon name="arrowRight" size={16} />
            </button>
          </>
        )}
        {step.kind === "stub" && (
          <div className="fp-chat">
            <div className="flow-editor-msg flow-editor-msg-agent">{step.message}</div>
            <button type="button" className="wiz-big-btn" onClick={restart}>
              Start over <Icon name="arrowRight" size={16} />
            </button>
          </div>
        )}
        </>
        )}
      </div>
      )}
    </div>
  );
}

/** The Campaign Strategy + Campaign Brief, read straight off strategy/campaign_artifacts.py's
 *  real payload -- every value below is a field that endpoint actually returns, none of it
 *  invented for display. A leaner summary of what frontend/src/workspace/CampaignArtifacts.tsx
 *  renders in full (that one also carries a journey-diagram projection and a technical
 *  appendix this view leaves out), not a different or approximated document. */
function BriefingDocument({ data }: { data: CampaignArtifactsPayload }) {
  const { strategy, brief } = data;
  return (
    <div className="briefing-doc">
      <section className="briefing-section">
        <h2>{brief.title}</h2>
        <p className="flow-planner-ready-hint" style={{ margin: 0 }}>
          Version {brief.version} · Generated {brief.generated_at}
        </p>
        <div className="hier-detail-card">
          <div className="hier-detail-head"><span className="hier-detail-name">{brief.header.brand}</span></div>
          <p className="hier-detail-summary">{brief.header.therapy_area} · {brief.header.lifecycle} · Owner: {brief.header.owner}</p>
          {brief.snapshot && (
            <>
              <div className="hier-punch-card">
                <span className="hier-punch-icon"><Icon name="target" size={18} /></span>
                <div className="hier-punch-body">
                  <div className="hier-detail-subhead">Objective</div>
                  <p className="hier-objective-text">{brief.snapshot.objective}</p>
                </div>
              </div>
              <div className="hier-punch-card">
                <span className="hier-punch-icon"><Icon name="users" size={18} /></span>
                <div className="hier-punch-body">
                  <div className="hier-detail-subhead">Target audience</div>
                  <p className="hier-objective-text">{brief.snapshot.target_audience}</p>
                </div>
              </div>
              <div className="hier-punch-card">
                <span className="hier-punch-icon"><Icon name="message" size={18} /></span>
                <div className="hier-punch-body">
                  <div className="hier-detail-subhead">Why now</div>
                  <p className="hier-objective-text">{brief.snapshot.reason}</p>
                </div>
              </div>
            </>
          )}
        </div>
      </section>

      <section className="briefing-section">
        <h3>Purpose</h3>
        <p className="hier-detail-summary">{brief.purpose.summary}</p>
        <p className="hier-detail-summary">{brief.purpose.program_context}</p>
        {brief.purpose.trigger_logic.length > 0 && (
          <ul className="briefing-list">{brief.purpose.trigger_logic.map((t, i) => <li key={i}>{t}</li>)}</ul>
        )}
      </section>

      <section className="briefing-section">
        <h3>Objective</h3>
        <p className="hier-detail-summary"><b>{brief.objective.pillar}</b> — {brief.objective.statement}</p>
        {brief.objective.leading_indicators.length > 0 && (
          <ul className="briefing-list">{brief.objective.leading_indicators.map((t, i) => <li key={i}>{t}</li>)}</ul>
        )}
      </section>

      <section className="briefing-section">
        <h3>Audience</h3>
        <p className="hier-detail-summary">{brief.audience.segment}</p>
        {brief.audience.eligibility_rules.length > 0 && (
          <ul className="briefing-list">{brief.audience.eligibility_rules.map((t, i) => <li key={i}>{t}</li>)}</ul>
        )}
        {brief.audience.segments.map((s, i) => (
          <div key={i} className="briefing-row">
            <div style={{ flex: 1 }}>
              <b>{s.name}</b>{s.volume != null && <span className="hier-plan-row-sub"> · {s.volume.toLocaleString()}{s.volume_note ? ` (${s.volume_note})` : ""}</span>}
              <p className="hier-detail-summary" style={{ margin: "4px 0 0" }}>{s.profile}</p>
            </div>
          </div>
        ))}
      </section>

      <section className="briefing-section">
        <h3>Communications strategy</h3>
        <p className="hier-detail-summary"><b>Core claim:</b> {brief.comms_strategy.core_claim}</p>
        <p className="hier-detail-summary">{brief.comms_strategy.belief_shift}</p>
        {brief.comms_strategy.message_ladder.length > 0 && (
          <ul className="briefing-list">{brief.comms_strategy.message_ladder.map((t, i) => <li key={i}>{t}</li>)}</ul>
        )}
        {brief.comms_strategy.tone_guardrails.length > 0 && (
          <p className="hier-detail-summary"><b>Tone guardrails:</b> {brief.comms_strategy.tone_guardrails.join(" · ")}</p>
        )}
      </section>

      {brief.deliverables.length > 0 && (
        <section className="briefing-section">
          <h3>Deliverables</h3>
          {brief.deliverables.map((d, i) => (
            <div key={i} className="briefing-row">
              <div style={{ flex: 1 }}><b>{d.asset}</b> — {d.variants}</div>
              <div className="hier-plan-row-sub">{d.notes}</div>
            </div>
          ))}
        </section>
      )}

      <section className="briefing-section">
        <h3>Channel mix</h3>
        <p className="hier-detail-summary">Anchor: {brief.channel_journey.anchor}</p>
        {brief.channel_journey.mix.map((m, i) => (
          <div key={i} className="briefing-row">
            <div style={{ flex: 1 }}>{m.channel}</div>
            <div><b>{m.pct}%</b></div>
          </div>
        ))}
        <p className="hier-detail-summary">{brief.channel_journey.cadence_note}</p>
      </section>

      <section className="briefing-section">
        <h3>Measurement plan</h3>
        {brief.measurement_plan.kpis.length > 0 && (
          <ul className="briefing-list">{brief.measurement_plan.kpis.map((t, i) => <li key={i}>{t}</li>)}</ul>
        )}
        <p className="hier-detail-summary">{brief.measurement_plan.test_design}</p>
      </section>

      {brief.risk_register.length > 0 && (
        <section className="briefing-section">
          <h3>Risk register</h3>
          {brief.risk_register.map((r, i) => (
            <div key={i} className="briefing-row">
              <div style={{ flex: 1 }}><b>{r.risk}</b> <span className="hier-plan-row-sub">({r.severity})</span></div>
              <div className="hier-plan-row-sub">{r.mitigation}</div>
            </div>
          ))}
        </section>
      )}

      <section className="briefing-section">
        <h3>Timeline &amp; approvals</h3>
        <p className="hier-detail-summary">{brief.timeline.window} — {brief.timeline.note}</p>
        {brief.approvals.length > 0 && (
          <p className="hier-detail-summary">{brief.approvals.map((a) => `${a.role}: ${a.name}`).join(" · ")}</p>
        )}
      </section>

      <section className="briefing-section">
        <h2>{strategy.title}</h2>
        <p className="hier-detail-summary">{strategy.note}</p>
        {strategy.records.map((r, i) => (
          <div key={i} className="hier-detail-card">
            <div className="hier-detail-head"><span className="hier-detail-name">{r.stage_name}</span></div>
            <p className="hier-detail-summary"><b>Framework:</b> {r.framework}</p>
            <p className="hier-detail-summary"><b>Decision:</b> {r.decision}</p>
            <p className="hier-detail-summary"><b>Rationale:</b> {r.rationale}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
