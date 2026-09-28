import { REGISTRY } from "../agents";
import { href } from "../route";
import "./v3.css";

/** Phase 0 frame of the redesigned Cockpit (docs/redesign/cockpit-redesign-plan.md). The
 *  rail and main area are placeholders that Phase 1 (shell) and Phase 2 (Home) fill in. */
export function V3App({ path }: { path: string[] }) {
  return (
    <div className="v3">
      <aside className="v3-rail" aria-label="Navigation">
        <div className="v3-rail-brand">Omni OS</div>
        <span className="v3-muted">Navigation arrives in Phase 1.</span>
      </aside>
      <main className="v3-main">
        <h1 className="v3-page-title">Omni OS · redesign preview</h1>
        <p className="v3-page-sub">
          Phase 0 foundation. The current Cockpit is unchanged at <a href={href({ kind: "home" })}>/cockpit</a>.
        </p>
        <div className="v3-card">
          <b>Agent registry</b>
          <p className="v3-muted">{REGISTRY.length} agents, one entry each: {REGISTRY.map((a) => a.name).join(" · ")}</p>
          {path.length > 0 && <p className="v3-muted">Route: /{path.join("/")}</p>}
        </div>
      </main>
    </div>
  );
}
