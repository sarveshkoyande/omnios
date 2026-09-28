import { useEffect, useMemo, useRef, useState } from "react";
import { getBrandTree, listArtifacts, routeAsk } from "../api";
import { PHASES, REGISTRY, type Phase, type RegistryAgent } from "../agents";
import { Icon } from "../components/Icon";
import { href } from "../route";
import type { BrandSummary, BrandTree } from "../types";

/** Phase 2 Home (B1-B6): greeting + Ask bar, quick actions, categories, apps grid and recent
 *  work. Everything is scoped to the active brand, or spans all brands (BR3/BR4). */

type RecentItem = { kind: "Plan" | "Campaign" | "Flow" | "Brief"; name: string; brand: string; updated: string; link: string };

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

/** The three quick starts, shown as big buttons inside the Ask box. Each one sets its agent
 *  as the box's context (same as picking it from the "/" menu). */
const QUICK: { id: string; title: string; sub: string }[] = [
  { id: "campaign-planner", title: "Plan a campaign", sub: "Objective, audience, messages, channels, timing" },
  { id: "flow-planner", title: "Build a flow", sub: "Turn a campaign plan into a flow diagram" },
  { id: "briefing-agent", title: "Compile a brief", sub: "An agency-ready brief from a campaign plan" },
];

/** The slash-command name an agent answers to, e.g. "/flow-planner". */
const slashName = (a: RegistryAgent) => `/${a.id}`;

export function Home({ brands, activeBrand }: { brands: BrandSummary[]; activeBrand: string | null }) {
  const [ask, setAsk] = useState("");
  const askRef = useRef<HTMLTextAreaElement>(null);
  const [reply, setReply] = useState<
    { question: string; status: "thinking" } |
    { question: string; status: "done"; text: string; agents: RegistryAgent[] } |
    { question: string; status: "error"; text: string } | null
  >(null);
  const [context, setContext] = useState<RegistryAgent | null>(null);
  const [menuIndex, setMenuIndex] = useState(0);
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
    Promise.all([
      Promise.all(scopeBrands.map((b) => getBrandTree(b).catch(() => null))),
      listArtifacts(activeBrand).then((r) => r.artifacts).catch(() => []),
    ])
      .then(([trees, artifacts]) => {
        if (!live) return;
        const items = [
          ...trees.flatMap((t) => (t ? recentFrom(t) : [])),
          ...artifacts.map((a): RecentItem => ({
            kind: "Brief", name: a.title, brand: a.brand, updated: a.updated_at, link: `#/v3/agent/${a.agent}/${a.id}`,
          })),
        ];
        items.sort((a, b) => b.updated.localeCompare(a.updated));
        setRecent(items.slice(0, 8));
      });
    return () => { live = false; };
  }, [scopeBrands, activeBrand]);

  const openAgent = (a: RegistryAgent) => { window.location.hash = a.route ?? `#/v3/app/${a.id}`; };

  const resetBox = () => {
    setAsk("");
    if (askRef.current) askRef.current.style.height = "auto";
  };

  /** Slash commands: a lone "/word" in the box opens the agent menu, like Claude's /skills.
   *  The menu narrows by the command-name prefix you've typed after the slash. */
  const slashQuery = /^\/\S*$/.test(ask) ? ask.slice(1).toLowerCase() : null;
  const menu = slashQuery === null ? [] : [...REGISTRY]
    .filter((a) => a.id.startsWith(slashQuery) || a.name.toLowerCase().startsWith(slashQuery))
    .sort((x, y) => Number(x.tags.includes("coming-soon")) - Number(y.tags.includes("coming-soon")));

  const pickContext = (a: RegistryAgent) => {
    if (a.tags.includes("coming-soon")) return;
    setContext(a);
    resetBox();
    setMenuIndex(0);
    askRef.current?.focus();
  };

  /** With an agent chosen as context, Send goes straight to it -- no routing needed. Without
   *  one, the question is routed by the LLM (strategy/agent_router.py), never by keywords. */
  const submitAsk = () => {
    const question = ask.trim();
    if (context) { openAgent(context); return; }
    if (!question || reply?.status === "thinking") return;
    setReply({ question, status: "thinking" });
    resetBox();
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

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (menu.length > 0) {
      if (e.key === "ArrowDown") { e.preventDefault(); setMenuIndex((i) => (i + 1) % menu.length); return; }
      if (e.key === "ArrowUp") { e.preventDefault(); setMenuIndex((i) => (i - 1 + menu.length) % menu.length); return; }
      if (e.key === "Enter" || e.key === "Tab") { e.preventDefault(); pickContext(menu[Math.min(menuIndex, menu.length - 1)]); return; }
      if (e.key === "Escape") { e.preventDefault(); resetBox(); return; }
    }
    if (e.key === "Backspace" && !ask && context) { setContext(null); return; }
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submitAsk(); }
  };

  const apps = phase === "all" ? REGISTRY : REGISTRY.filter((a) => a.phase === phase);
  return (
    <div className="v3-home">
      <section className="v3-hero">
        <h1>Hi there,<br />how can I help today?</h1>
        <div className="v3-ask-wrap">
          <form className="v3-ask" onSubmit={(e) => { e.preventDefault(); submitAsk(); }}>
            <div className="v3-ask-row">
              <Icon name="sparkles" size={16} />
              {context && (
                <span className="v3-ctx">
                  <Icon name={context.icon} size={13} />{context.name}
                  <button type="button" aria-label={`Remove ${context.name}`} onClick={() => setContext(null)}><Icon name="close" size={11} /></button>
                </span>
              )}
              <textarea ref={askRef} rows={1} value={ask}
                onChange={(e) => {
                  setAsk(e.target.value);
                  setMenuIndex(0);
                  e.target.style.height = "auto";
                  e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
                }}
                onKeyDown={onKeyDown}
                placeholder={context
                  ? `Add a note for ${context.name} (optional), then Send`
                  : activeBrand ? `Ask Omni anything about ${activeBrand}… or type / for agents` : "Ask Omni anything… or type / for agents"} />
              <button type="submit" className="v3-ask-send" disabled={!context && (!ask.trim() || slashQuery !== null || reply?.status === "thinking")}>
                {context ? "Open" : "Send"}
              </button>
            </div>
            <div className="v3-ask-foot">
              {QUICK.map((q) => {
                const a = REGISTRY.find((x) => x.id === q.id);
                if (!a) return null;
                const soon = a.tags.includes("coming-soon") || !a.route;
                const on = context?.id === a.id;
                return (
                  <button key={a.id} type="button" className={`v3-ask-quick ${on ? "on" : ""}`} disabled={soon}
                    aria-pressed={on} title={soon ? "Coming soon" : undefined} onClick={() => (on ? setContext(null) : pickContext(a))}>
                    <span className="v3-quick-icon"><Icon name={a.icon} size={16} /></span>
                    <span className="v3-quick-text"><b>{q.title}</b><span>{soon ? "Coming soon" : q.sub}</span></span>
                  </button>
                );
              })}
            </div>
            <div className="v3-ask-hint">Type <kbd>/</kbd> for all agents</div>
          </form>
          {menu.length > 0 && (
            <div className="v3-slash" role="listbox" aria-label="Agents">
              {menu.map((a, i) => {
                const soon = a.tags.includes("coming-soon");
                return (
                  <button key={a.id} type="button" role="option" aria-selected={i === menuIndex} disabled={soon}
                    className={`v3-slash-item ${i === menuIndex ? "active" : ""}`}
                    onMouseEnter={() => setMenuIndex(i)} onMouseDown={(e) => { e.preventDefault(); pickContext(a); }}>
                    <span className="v3-app-icon"><Icon name={a.icon} size={14} /></span>
                    <span className="v3-slash-text"><b>{a.name}</b><span>{soon ? "Coming soon" : a.summary}</span></span>
                    <code>{slashName(a)}</code>
                  </button>
                );
              })}
            </div>
          )}
        </div>
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
              <Icon name={r.kind === "Flow" ? "route" : r.kind === "Campaign" ? "target" : r.kind === "Brief" ? "sparkles" : "document"} size={15} />
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
