import { useEffect, useState } from "react";
import { listArtifacts, listEngagementPlans, type V3ArtifactSummary } from "../api";
import { REGISTRY } from "../agents";
import { Icon } from "../components/Icon";

type WorkItem = Pick<V3ArtifactSummary, "id" | "agent" | "brand" | "title" | "updated_at" | "version"> & { href: string };

/** C15: everything the agents have produced -- artifacts and engagement plans -- newest first,
 *  scoped to the active brand. */
export function MyWork({ activeBrand }: { activeBrand: string | null }) {
  const [items, setItems] = useState<WorkItem[] | null>(null);

  useEffect(() => {
    let live = true;
    setItems(null);
    Promise.all([
      listArtifacts(activeBrand).then((r) => r.artifacts.map((a) => ({ ...a, href: `#/v3/agent/${a.agent}/${a.id}` }))).catch(() => []),
      listEngagementPlans(activeBrand ?? undefined).then((r) => r.plans.map((p) => ({
        id: p.id, agent: "engagement-planner", brand: p.brand, title: p.title, updated_at: p.updated_at, version: p.version,
        href: `#/v3/agent/engagement-planner/${p.id}`,
      }))).catch(() => []),
    ]).then(([a, p]) => {
      if (live) setItems([...a, ...p].sort((x, y) => (x.updated_at < y.updated_at ? 1 : -1)));
    });
    return () => { live = false; };
  }, [activeBrand]);

  return (
    <div className="v3-home">
      <div>
        <h1 className="v3-page-title">My work</h1>
        <p className="v3-page-sub">{activeBrand ? <>Scoped to <b>{activeBrand}</b></> : "All brands"}</p>
      </div>
      <div className="v3-recent">
        {items === null && <div className="v3-recent-empty">Loading…</div>}
        {items?.length === 0 && <div className="v3-recent-empty">Nothing generated yet{activeBrand ? ` for ${activeBrand}` : ""}. Run an agent to see its work here.</div>}
        {items?.map((a) => {
          const agent = REGISTRY.find((x) => x.id === a.agent);
          return (
            <a key={`${a.agent}:${a.id}`} className="v3-recent-row" href={a.href}>
              <Icon name={agent?.icon ?? "document"} size={15} />
              <span className="v3-recent-name">{a.title}</span>
              <span className="v3-recent-meta">{!activeBrand && <em>{a.brand}</em>}{agent?.name ?? a.agent} · v{a.version}</span>
              <span className="v3-recent-time">{new Date(a.updated_at).toLocaleString()}</span>
            </a>
          );
        })}
      </div>
    </div>
  );
}
