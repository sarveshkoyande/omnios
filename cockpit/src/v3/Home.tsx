import { useEffect, useMemo, useRef, useState } from "react";
import { getBrandTree } from "../api";
import { PHASES, REGISTRY, type Phase, type RegistryAgent } from "../agents";
import { Icon } from "../components/Icon";
import { href } from "../route";
import type { BrandSummary, BrandTree } from "../types";

/** Phase 2 Home (B1-B6): greeting + Ask bar, quick actions, categories, apps grid and recent
 *  work. Everything is scoped to the active brand, or spans all brands (BR3/BR4). */

type RecentItem = { kind: "Plan" | "Campaign" | "Flow"; name: string; brand: string; updated: string; link: string };

function recentFrom(tree: BrandTree): RecentItem[] {
  const out: RecentItem[] = [];
  for (const p of tree.engagement_plans) {
    out.push({ kind: "Plan", name: p.name, brand: tree.brand, updated: p.updated_at, link: href({ kind: "plan", brand: tree.brand, planId: p.id }) });
    for (const c of p.campaigns) {
      out.push({ kind: "Campaign", name: c.name, brand: tree.brand, updated: c.updated_at,
        link: href({ kind: "campaign", brand: tree.brand, planId: p.id, campaignId: c.id }) });
      for (const f of c.flows) {
        out.push({ kind: "Flow", name: f.name, brand: tree.brand, updated: f.updated_at,
          link: href({ kind: "flow", brand: tree.brand, planId: p.id, campaignId: c.id, flowId: f.id }) });
      }
    }
  }
  return out;
}

function timeAgo(iso: string): string {
  const t = Date.parse(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`);
  if (Number.isNaN(t)) return "";
  const s = Math.max(0, (Date.now() - t) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  if (s < 86400 * 30) return `${Math.floor(s / 86400)} d ago`;
  return new Date(t).toLocaleDateString();
}

/** Everyday words people type, mapped to the agent that handles them. The agents' own names
 *  and summaries are matched too; this just catches wording they don't literally contain. */
const KEYWORDS: Record<string, string[]> = {
  "flow-planner": ["flow", "journey", "diagram", "visio", "sop", "cadence", "resend", "touchpoint", "sequence"],
  "briefing-agent": ["brief", "agency", "handoff", "hand-off", "document"],
  "engagement-plan-builder": ["plan", "engagement", "quarter", "quarterly", "strategy", "goals"],
  "segmentation-planner": ["segment", "segments", "segmentation", "hcp", "hcps", "target", "audience", "doctors", "physicians", "prescribers"],
  "brand-persona-builder": ["persona", "personas", "patient", "patients", "emotion", "motivation"],
  "channel-planner": ["channel", "channels", "budget", "mix", "spend", "cost"],
  "signal-agent": ["competitor", "competitors", "competitive", "market", "signal", "signals", "lifecycle"],
  "journey-builder": ["edit", "journey"],
  "email-template-builder": ["email", "emails", "template", "templates", "subject"],
  "reporting-insights": ["report", "reporting", "performance", "kpi", "kpis", "results", "metrics"],
  "budget-agent": ["budget", "allocation", "allocate"],
};

/** Words too common to say anything about which agent you need. */
const STOPWORDS = new Set([
  "the", "and", "for", "with", "what", "which", "how", "can", "you", "your", "our", "we", "should", "would",
  "could", "this", "that", "these", "those", "are", "was", "were", "will", "from", "into", "about", "does",
  "do", "have", "has", "had", "there", "their", "them", "they", "hello", "hey", "please", "help", "need",
  "want", "make", "get", "give", "tell", "show", "all", "any", "some", "one", "who", "why", "when", "where",
  "between", "each", "more", "most", "also", "than", "then", "its", "not", "but", "out", "use", "using",
]);

/** Scores every agent against what was typed (whole words only, common words ignored).
 *  Returns the best fits, strongest first. */
function matchAgents(query: string): RegistryAgent[] {
  const tokenize = (t: string) => t.toLowerCase().split(/[^a-z0-9-]+/).filter((w) => w.length > 2 && !STOPWORDS.has(w));
  const words = tokenize(query);
  if (words.length === 0) return [];
  return REGISTRY
    .map((a) => {
      const hay = new Set(tokenize(`${a.name} ${a.summary}`));
      const keys = KEYWORDS[a.id] ?? [];
      const score = words.reduce((n, w) => n + (keys.includes(w) ? 2 : 0) + (hay.has(w) ? 1 : 0), 0);
      const soon = a.tags.includes("coming-soon");
      return { a, score: score > 0 ? score + (soon ? -0.5 : 0.5) : 0 };
    })
    .filter((x) => x.score > 0)
    .sort((x, y) => y.score - x.score)
    .slice(0, 3)
    .map((x) => x.a);
}

/** Shown when nothing matches -- the agents that are actually usable today. */
const FALLBACK_IDS = ["flow-planner", "briefing-agent", "engagement-plan-builder"];

const QUICK_ACTIONS: { title: string; sub: string; icon: "document" | "route" | "target"; to?: string }[] = [
  { title: "Start an engagement plan", sub: "Quarterly goals, segments, budget and campaigns", icon: "target" },
  { title: "Build a flow", sub: "Turn a campaign into a flow diagram", icon: "route", to: "#/flow-planner" },
  { title: "Compile a brief", sub: "An agency-ready brief from a campaign plan", icon: "document", to: "#/briefing-agent" },
];

export function Home({ brands, activeBrand }: { brands: BrandSummary[]; activeBrand: string | null }) {
  const [ask, setAsk] = useState("");
  const askRef = useRef<HTMLTextAreaElement>(null);
  const [reply, setReply] = useState<{ question: string; agents: RegistryAgent[]; matched: boolean } | null>(null);
  const [phase, setPhase] = useState<Phase | "all">("all");
  const [recent, setRecent] = useState<RecentItem[] | null>(null);

  const scopeBrands = useMemo(
    () => (activeBrand ? [activeBrand] : brands.map((b) => b.brand)),
    [activeBrand, brands],
  );

  useEffect(() => {
    if (scopeBrands.length === 0) { setRecent([]); return; }
    let live = true;
    setRecent(null);
    Promise.all(scopeBrands.map((b) => getBrandTree(b).catch(() => null)))
      .then((trees) => {
        if (!live) return;
        const items = trees.flatMap((t) => (t ? recentFrom(t) : []));
        items.sort((a, b) => b.updated.localeCompare(a.updated));
        setRecent(items.slice(0, 8));
      });
    return () => { live = false; };
  }, [scopeBrands]);

  const submitAsk = () => {
    const question = ask.trim();
    if (!question) return;
    const found = matchAgents(question);
    setReply({
      question,
      matched: found.length > 0,
      agents: found.length > 0 ? found : REGISTRY.filter((a) => FALLBACK_IDS.includes(a.id)),
    });
    setAsk("");
    if (askRef.current) askRef.current.style.height = "auto";
  };
  const apps = phase === "all" ? REGISTRY : REGISTRY.filter((a) => a.phase === phase);
  const openAgent = (a: RegistryAgent) => { window.location.hash = a.route ?? `#/v3/app/${a.id}`; };

  return (
    <div className="v3-home">
      <section className="v3-hero">
        <h1>Hi there,<br />how can I help today?</h1>
        <form className="v3-ask" onSubmit={(e) => { e.preventDefault(); submitAsk(); }}>
          <Icon name="sparkles" size={16} />
          <textarea ref={askRef} rows={1} value={ask}
            onChange={(e) => {
              setAsk(e.target.value);
              e.target.style.height = "auto";
              e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
            }}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submitAsk(); } }}
            placeholder={activeBrand ? `Ask Omni anything about ${activeBrand}…` : "Ask Omni anything…"} />
          <button type="submit" disabled={!ask.trim()}>Send</button>
        </form>
        {reply && (
          <div className="v3-ask-reply">
            <div className="v3-ask-q">{reply.question}</div>
            <p>
              {reply.matched
                ? <>The best agent{reply.agents.length > 1 ? "s" : ""} for this:</>
                : <>I can't answer free-form questions yet; chat is coming. These agents are ready to use now:</>}
            </p>
            <div className="v3-ask-agents">
              {reply.agents.map((a) => {
                const soon = a.tags.includes("coming-soon");
                return (
                  <button key={a.id} type="button" className="v3-ask-agent" disabled={soon} onClick={() => openAgent(a)}>
                    <span className="v3-app-icon"><Icon name={a.icon} size={15} /></span>
                    <span className="v3-ask-agent-text"><b>{a.name}</b><span>{soon ? "Coming soon" : a.summary}</span></span>
                    {!soon && <span className="v3-ask-open">Open</span>}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </section>

      <section className="v3-quick">
        {QUICK_ACTIONS.map((q) => {
          const inner = (
            <>
              <span className="v3-quick-icon"><Icon name={q.icon} size={16} /></span>
              <span className="v3-quick-text"><b>{q.title}</b><span>{q.to ? q.sub : "Coming soon"}</span></span>
            </>
          );
          return q.to
            ? <a key={q.title} className="v3-quick-card" href={q.to}>{inner}</a>
            : <div key={q.title} className="v3-quick-card disabled" aria-disabled="true">{inner}</div>;
        })}
      </section>

      <section>
        <h2 className="v3-section-title">Categories</h2>
        <div className="v3-cats">
          {PHASES.map((p) => {
            const count = REGISTRY.filter((a) => a.phase === p.id).length;
            const on = phase === p.id;
            return (
              <button key={p.id} type="button" className={`v3-cat ${on ? "active" : ""}`} aria-pressed={on}
                onClick={() => setPhase(on ? "all" : p.id)}>
                <b>{p.label}</b>
                <span>{p.tagline}</span>
                <em><Icon name="layers" size={12} /> {count} agents</em>
              </button>
            );
          })}
        </div>
      </section>

      <section>
        <h2 className="v3-section-title">
          {phase === "all" ? "Agents" : `${PHASES.find((p) => p.id === phase)?.label} agents`}
          {phase !== "all" && <button type="button" className="v3-link" onClick={() => setPhase("all")}>Show all</button>}
        </h2>
        <div className="v3-apps">
          {apps.map((a) => {
            const soon = a.tags.includes("coming-soon");
            return (
              <button key={a.id} type="button" className={`v3-app ${soon ? "soon" : ""}`} disabled={soon}
                onClick={() => openAgent(a)} title={soon ? "Coming soon" : `Open ${a.name}`}>
                <span className="v3-app-top">
                  <span className="v3-app-icon"><Icon name={a.icon} size={16} /></span>
                  <span className="v3-tags">
                    {a.tags.includes("new") && <span className="v3-tag new">New</span>}
                    {soon && <span className="v3-tag soon">Coming soon</span>}
                  </span>
                </span>
                <b>{a.name}</b>
                <span className="v3-app-sub">{a.summary}</span>
              </button>
            );
          })}
        </div>
      </section>

      <section>
        <h2 className="v3-section-title">Recent work</h2>
        <div className="v3-recent">
          {recent === null && <div className="v3-recent-empty">Loading…</div>}
          {recent?.length === 0 && <div className="v3-recent-empty">Nothing yet{activeBrand ? ` for ${activeBrand}` : ""}.</div>}
          {recent?.map((r) => (
            <a key={`${r.kind}:${r.link}`} className="v3-recent-row" href={r.link}>
              <Icon name={r.kind === "Flow" ? "route" : r.kind === "Campaign" ? "target" : "document"} size={15} />
              <span className="v3-recent-name">{r.name}</span>
              <span className="v3-recent-meta">{!activeBrand && <em>{r.brand}</em>}{r.kind}</span>
              <span className="v3-recent-time">{timeAgo(r.updated)}</span>
            </a>
          ))}
        </div>
      </section>
    </div>
  );
}
