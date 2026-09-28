import { PHASES, REGISTRY } from "../agents";
import { Icon } from "../components/Icon";

/** What an app does and works from, for agents that are built but don't have a workspace
 *  screen yet. Their workspace versions arrive in Phases 3-6. */
export function AppDetail({ id }: { id: string }) {
  const a = REGISTRY.find((x) => x.id === id);
  if (!a) return <p className="v3-muted">No agent called "{id}".</p>;
  return (
    <div className="v3-detail">
      <a className="v3-link" href="#/v3/home"><Icon name="arrowLeft" size={13} /> Home</a>
      <div className="v3-detail-head">
        <span className="v3-app-icon lg"><Icon name={a.icon} size={20} /></span>
        <div>
          <h1 className="v3-page-title">{a.name}</h1>
          <p className="v3-page-sub">{PHASES.find((p) => p.id === a.phase)?.label}</p>
        </div>
      </div>
      <div className="v3-card">
        <b>What it does</b>
        <p>{a.about ?? a.summary}</p>
        {a.worksFrom && a.worksFrom.length > 0 && (
          <>
            <b>Works from</b>
            <ul className="v3-detail-list">
              {a.worksFrom.map((w) => <li key={w.label}><b>{w.label}</b> — {w.detail}</li>)}
            </ul>
          </>
        )}
        <p className="v3-muted">Its workspace screen arrives in a later phase of the redesign.</p>
      </div>
    </div>
  );
}
