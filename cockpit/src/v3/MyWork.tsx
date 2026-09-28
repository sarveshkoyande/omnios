import { useEffect, useState } from "react";
import { listArtifacts, type V3ArtifactSummary } from "../api";
import { REGISTRY } from "../agents";
import { Icon } from "../components/Icon";

/** C15: every artifact the agents have produced, newest first, scoped to the active brand. */
export function MyWork({ activeBrand }: { activeBrand: string | null }) {
  const [items, setItems] = useState<V3ArtifactSummary[] | null>(null);

  useEffect(() => {
    let live = true;
    setItems(null);
    listArtifacts(activeBrand).then((r) => live && setItems(r.artifacts)).catch(() => live && setItems([]));
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
        {items?.length === 0 && <div className="v3-recent-empty">Nothing generated yet{activeBrand ? ` for ${activeBrand}` : ""}. Open an agent and Generate to see it here.</div>}
        {items?.map((a) => {
          const agent = REGISTRY.find((x) => x.id === a.agent);
          return (
            <a key={a.id} className="v3-recent-row" href={`#/v3/agent/${a.agent}/${a.id}`}>
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
