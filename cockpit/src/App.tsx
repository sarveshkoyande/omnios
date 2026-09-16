import { useEffect, useState } from "react";
import { getBrandKit, listBrands } from "./api";
import type { BrandKit, BrandSummary, KitUpdateSection } from "./types";
import { BrandWorkspace } from "./components/BrandWorkspace";
import { AgentLibrary } from "./components/AgentLibrary";
import { KitUpdateScreen } from "./components/KitUpdateScreen";
import "./cockpit.css";

type View = "workspace" | "agents" | "kit-update";

export default function App() {
  const [view, setView] = useState<View>("workspace");
  const [brands, setBrands] = useState<BrandSummary[] | null>(null);
  const [knownTerritories, setKnownTerritories] = useState<string[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [territory, setTerritory] = useState<string | null>(null);
  const [kit, setKit] = useState<BrandKit | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [kitUpdateSection, setKitUpdateSection] = useState<KitUpdateSection | null>(null);

  useEffect(() => {
    listBrands()
      .then((r) => {
        setBrands(r.brands);
        setKnownTerritories(r.known_territories);
        if (r.brands.length > 0) {
          setSelected(r.brands[0].brand);
          setTerritory(r.brands[0].territories[0] ?? null);
        }
      })
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (!selected || !territory) return;
    setKit(null);
    getBrandKit(selected, territory)
      .then((r) => setKit(r.kit))
      .catch((e) => setError(String(e)));
  }, [selected, territory]);

  const selectBrand = (b: BrandSummary) => {
    setSelected(b.brand);
    setTerritory(b.territories[0] ?? null);
  };

  const openKitUpdate = (section: KitUpdateSection) => {
    setKitUpdateSection(section);
    setView("kit-update");
  };

  return (
    <div className="app-frame">
      <header className="top-bar">
        <div className="top-bar-brand">Omni OS Cockpit</div>
        <button type="button" className="top-bar-user" title="Signed in as you" aria-label="User account">
          <span aria-hidden>&#128100;</span>
        </button>
      </header>

      <div className="app-shell">
      <aside className="rail">
        <div className="rail-section-label">Workspace</div>
        <button
          type="button"
          className={`rail-item ${view === "workspace" ? "active" : ""}`}
          onClick={() => setView("workspace")}
        >
          Brand Workspace
        </button>
        <button
          type="button"
          className={`rail-item ${view === "agents" ? "active" : ""}`}
          onClick={() => setView("agents")}
        >
          Agent Library
        </button>

        {view === "workspace" && (
          <>
            <div className="rail-section-label" style={{ marginTop: 24 }}>Brands</div>
            {brands?.map((b) => {
              const isSelected = selected === b.brand;
              const activeTerritory = isSelected ? territory : b.territories[0];
              return (
                <div key={b.brand} className="rail-brand-block">
                  <button
                    type="button"
                    className={`rail-item rail-brand-item ${isSelected ? "active" : ""}`}
                    onClick={() => selectBrand(b)}
                  >
                    {b.brand}{activeTerritory ? ` (${activeTerritory})` : ""}
                    <span className="rail-brand-sub">{b.indication || b.therapy_area}</span>
                  </button>
                  {isSelected && (
                    <div className="territory-row">
                      {knownTerritories.map((t) => {
                        const configured = b.territories.includes(t);
                        return (
                          <button
                            key={t}
                            type="button"
                            disabled={!configured}
                            className={`territory-pill ${territory === t ? "active" : ""} ${!configured ? "disabled" : ""}`}
                            title={configured ? `Switch to ${t}` : `Not configured for ${t} yet`}
                            onClick={() => configured && setTerritory(t)}
                          >
                            {t}
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
            {brands && brands.length === 0 && (
              <div className="rail-empty">No brand kits configured yet.</div>
            )}
          </>
        )}
      </aside>

      <main className="main">
        {view === "agents" && <AgentLibrary />}
        {view === "workspace" && (
          <>
            {error && <div className="error-banner">Couldn't load brand data: {error}</div>}
            {!error && !kit && <div className="loading">Loading brand workspace&hellip;</div>}
            {kit && selected && <BrandWorkspace brand={selected} kit={kit} onUpdate={openKitUpdate} />}
          </>
        )}
        {view === "kit-update" && selected && kitUpdateSection && (
          <KitUpdateScreen
            brand={selected}
            initialSection={kitUpdateSection}
            onClose={() => setView("workspace")}
          />
        )}
      </main>
      </div>
    </div>
  );
}
