import { useEffect, useMemo, useRef, useState } from "react";
import { getBrandTree, routeAsk } from "../api";
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

const QUICK_ACTIONS: { title: string; sub: string; icon: "document" | "route" | "target"; to?: string }[] = [
  { title: "Start an engagement plan", sub: "Quarterly goals, segments, budget and campaigns", icon: "target" },
  { title: "Build a flow", sub: "Turn a campaign into a flow diagram", icon: "route", to: "#/flow-planner" },
  { title: "Compile a brief", sub: "An agency-ready brief from a campaign plan", icon: "document", to: "#/briefing-agent" },
];

export function Home({ brands, activeBrand }: { brands: BrandSummary[]; activeBrand: string | null }) {
  const [ask, setAsk] = useState("");
  const askRef = useRef<HTMLTextAreaElement>(null);
  const [reply, setReply] = useState<
    { question: string; status: "thinking" } |
    { question: string; status: "done"; text: string; agents: RegistryAgent[] } |
    { question: string; status: "error"; text: string } | null
  >(null);
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

  /** LLM-only routing (strategy/agent_router.py) -- no keyword matching anywhere. */
  const submitAsk = () => {
    const question = ask.trim();
    if (!question || reply?.status === "thinking") return;
    setReply({ question, status: "thinking" });
    setAsk("");
    if (askRef.current) askRef.current.style.height = "auto";
    routeAsk({
      question,
      brand: activeBrand,
      agents: REGISTRY.map((a) => ({ id: a.id, name: a.name, summary: a.summary, available: !a.tags.includes("coming-soon") })),
    })
      .then((r) => setReply({
        question, status: "done", text: r.reply,
        agents: r.agent_ids.map((id) => REGISTRY.find((a) => a.id === id)).filter((a): a is RegistryAgent => Boolean(a)),
      }))
      .catch((e) => setReply({ question, status: "error", text: e instanceof Error ? e.message : String(e) }));
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
          <button type="submit" disabled={!ask.trim() || reply?.status === "thinking"}>Send</button>
        </form>
        {reply && (
          <div className="v3-ask-reply">
            <div className="v3-ask-q">{reply.question}</div>
            {reply.status === "thinking" && (
              <div className="v3-ask-thinking"><span /><span /><span /></div>
            )}
            {reply.status === "error" && <p className="v3-ask-error">{reply.text}</p>}
            {reply.status === "done" && (
              <>
                {reply.text && <p>{reply.text}</p>}
                {reply.agents.length > 0 && (
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
                )}
              </>
            )}
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
