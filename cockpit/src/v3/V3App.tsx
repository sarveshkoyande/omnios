import { useEffect, useState } from "react";
import { listBrands } from "../api";
import type { BrandSummary } from "../types";
import { AppDetail } from "./AppDetail";
import { Home } from "./Home";
import { Rail } from "./Rail";
import { useBrandScope, useFavorites, useRailPinned } from "./store";
import "./v3.css";

/** Pages the Phase 1 shell can route to. Their real content arrives in later phases
 *  (docs/redesign/cockpit-redesign-plan.md, "Build order"); for now each one states its
 *  brand scope, so navigation and brand switching can be reviewed on their own. */
const PAGES: Record<string, { title: string; phase: string; perBrand?: boolean }> = {
  home: { title: "Home", phase: "Phase 2" },
  work: { title: "My work", phase: "Phase 4" },
  brands: { title: "Brands & Campaigns", phase: "Phase 6" },
  chat: { title: "Chat", phase: "Phase 5" },
  "iq/kits": { title: "Brand Kits", phase: "a later phase", perBrand: true },
  "iq/personas": { title: "Personas", phase: "a later phase", perBrand: true },
  "iq/guardrails": { title: "Compliance Guardrails", phase: "a later phase", perBrand: true },
  "iq/intel": { title: "Market Intelligence", phase: "a later phase", perBrand: true },
};

export function V3App({ path }: { path: string[] }) {
  const [brands, setBrands] = useState<BrandSummary[]>([]);
  useEffect(() => { listBrands().then((r) => setBrands(r.brands)).catch(() => setBrands([])); }, []);

  const scope = useBrandScope(brands.map((b) => b.brand));
  const favs = useFavorites();
  const [pinned, setPinned] = useRailPinned();

  const current = path.join("/") || "home";
  const page = PAGES[current] ?? PAGES.home;
  const isHome = current === "home" || !PAGES[current] && path[0] !== "app";

  return (
    <div className="v3">
      <Rail current={current} brands={brands} activeBrand={scope.activeBrand} recentBrands={scope.recentBrands}
        onSelectBrand={scope.selectBrand} favorites={favs.favorites} isFavorite={favs.isFavorite}
        toggleFavorite={favs.toggleFavorite} pinned={pinned} setPinned={setPinned} />
      <main className="v3-main">
        {path[0] === "app" ? <AppDetail id={path[1] ?? ""} /> : isHome ? (
          <Home brands={brands} activeBrand={scope.activeBrand} />
        ) : (<>
        <h1 className="v3-page-title">{page.title}</h1>
        <p className="v3-page-sub">
          {scope.activeBrand ? <>Scoped to <b>{scope.activeBrand}</b></> : "All brands"}
        </p>

        {page.perBrand && !scope.activeBrand ? (
          <div className="v3-card">
            <b>Pick a brand</b>
            <p className="v3-muted">{page.title} is kept per brand. Choose which one to open:</p>
            <div className="v3-chip-row">
              {brands.map((b) => (
                <button key={b.brand} type="button" className="v3-chip" onClick={() => scope.selectBrand(b.brand)}>{b.brand}</button>
              ))}
            </div>
          </div>
        ) : (
          <div className="v3-card">
            <p className="v3-muted">This page is built in {page.phase}.</p>
          </div>
        )}
        </>)}
      </main>
    </div>
  );
}
