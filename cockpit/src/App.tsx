import { useEffect, useState } from "react";
import { createBrand, getBrandKit, listBrands } from "./api";
import type { BrandKit, BrandSummary, KitUpdateSection } from "./types";
import { BrandWorkspace } from "./components/BrandWorkspace";
import { AgentLibrary } from "./components/AgentLibrary";
import { KitUpdateScreen } from "./components/KitUpdateScreen";
import { Icon } from "./components/Icon";
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
    // The brand switcher is now reachable from every view (including kit-update); picking
    // a different brand always lands on that brand's workspace rather than leaving a
    // kit-update session open for the brand you just navigated away from.
    setView("workspace");
  };

  const openKitUpdate = (section: KitUpdateSection) => {
    setKitUpdateSection(section);
    setView("kit-update");
  };

  /** The "+" next to Brands: sets up a brand-new brand and takes you straight into the
   *  guided update flow (kit-brand-details is the natural starting tab for a kit that
   *  has nothing in it yet) instead of a blank workspace view. window.prompt is a
   *  deliberately minimal first cut for naming the brand -- a real modal is an easy
   *  upgrade later if this affordance earns one. */
  const addBrand = async () => {
    const name = window.prompt("Name the new brand:");
    if (!name || !name.trim()) return;
    try {
      await createBrand(name);
      const r = await listBrands();
      setBrands(r.brands);
      setKnownTerritories(r.known_territories);
      setSelected(name.trim());
      setTerritory("US");
      setKitUpdateSection("kit-brand-details");
      setView("kit-update");
    } catch (e) {
      window.alert(String(e instanceof Error ? e.message : e));
    }
  };

  return (
    <div className="app-frame">
      <header className="top-bar">
        <div className="top-bar-brand">Omni OS Cockpit</div>
        <button type="button" className="top-bar-user" title="Signed in as you" aria-label="User account">
          <Icon name="user" size={17} />
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

        {/* Persistent across every view, including the kit-update ("agent") screen --
            the brand switcher is app-level context, not workspace-view-specific chrome. */}
        <div className="rail-section-row" style={{ marginTop: 24 }}>
          <span className="rail-section-label" style={{ marginTop: 0 }}>Brands</span>
          <button type="button" className="rail-add-brand" title="Set up a new brand" aria-label="Set up a new brand" onClick={addBrand}>
            <Icon name="plus" size={14} />
          </button>
        </div>
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
              {isSelected && view === "workspace" && (
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
