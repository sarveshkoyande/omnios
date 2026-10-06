import { EngagementPlanner2 } from "./ep2/EngagementPlanner2";
import { LiveSimulation } from "./livesim/LiveSimulation";
import { FlowAgent } from "./flowagent/FlowAgent";
import { SignalScoutAgent } from "./signalscout/SignalScoutAgent";
import { BrandIqAgent } from "./brandiq/BrandIqAgent";
import { useEffect, useState } from "react";
import { listBrands } from "../api";
import type { BrandSummary } from "../types";
import { AppDetail } from "./AppDetail";
import { Brands } from "./Brands";
import { BrandKitPage, GuardrailsPage, MarketIntelPage, PersonasPage } from "./BrandKitPage";
import { Chat } from "./Chat";
import { Home } from "./Home";
import { MyWork } from "./MyWork";
import { Rail } from "./Rail";
import { Workspace } from "./Workspace";
import { CampaignPlanner } from "./campaignplanner/CampaignPlanner";
import { EngagementPlanner } from "./engagement/EngagementPlanner";
import { SegmentationPlanner } from "./segmentation/SegmentationPlanner";
import { useBrandScope, useFavorites, useRailPinned } from "./store";
import "./v3.css";

/** Pages the Phase 1 shell can route to. Their real content arrives in later phases
 *  (docs/redesign/cockpit-redesign-plan.md, "Build order"); for now each one states its
 *  brand scope, so navigation and brand switching can be reviewed on their own. */
const PAGES: Record<string, { title: string; phase: string; perBrand?: boolean }> = {
  home: { title: "Home", phase: "Phase 2" },
  work: { title: "My work", phase: "Phase 4" },
  brands: { title: "Campaigns & Journeys", phase: "Phase 6" },
  live: { title: "Live simulation", phase: "Phase 8" },
  chat: { title: "Chat", phase: "Phase 5" },
  "iq/kits": { title: "Brand IQ", phase: "a later phase", perBrand: true },
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
  const isWorkspace = path[0] === "agent" && Boolean(path[1]);
  const isHome = current === "home" || (!PAGES[current] && path[0] !== "app" && !isWorkspace);

  return (
    <div className="v3">
      <Rail current={current} brands={brands} activeBrand={scope.activeBrand} recentBrands={scope.recentBrands}
        onSelectBrand={scope.selectBrand} favorites={favs.favorites} isFavorite={favs.isFavorite}
        toggleFavorite={favs.toggleFavorite} pinned={pinned} setPinned={setPinned} />
      <main className={`v3-main ${isWorkspace ? "v3-main-ws" : ""}`}>
        {isWorkspace && path[1] === "signal-agent" ? (
          <SignalScoutAgent key="signal-agent" brands={brands} activeBrand={scope.activeBrand} />
        ) : isWorkspace && path[1] === "brand-iq" ? (
          <BrandIqAgent key="brand-iq" brands={brands} activeBrand={scope.activeBrand} />
        ) : isWorkspace && path[1] === "flow-planner" && path[2] !== undefined && path[2] !== "for" ? (
          <Workspace key={path.join("/")} agentId="flow-planner" artifactId={path[2]}
            brands={brands} activeBrand={scope.activeBrand}
            isFavorite={favs.isFavorite} toggleFavorite={favs.toggleFavorite} />
        ) : isWorkspace && path[1] === "flow-planner" ? (
          <FlowAgent key={path.join("/")} brands={brands} activeBrand={scope.activeBrand}
            handoff={path[2] === "for" && path[3] ? { brand: path[3], planId: Number(path[4]) || null, campaignId: Number(path[5]) || null } : undefined} />
        ) : isWorkspace && path[1] === "engagement-planner-2" ? (
          <EngagementPlanner2 key="engagement-planner-2" planId={path[2]} brands={brands} activeBrand={scope.activeBrand} />
        ) : isWorkspace && path[1] === "engagement-planner" ? (
          <EngagementPlanner key="engagement-planner" planId={path[2]} brands={brands} activeBrand={scope.activeBrand} />
        ) : isWorkspace && path[1] === "briefing-agent" ? (
          <CampaignPlanner key={path.join("/")}
            artifactId={path[2] !== "for" ? path[2] : undefined}
            handoff={path[2] === "for" && path[3] ? { brand: path[3], planId: Number(path[4]) || null, campaignId: Number(path[5]) || null } : undefined}
            brands={brands} activeBrand={scope.activeBrand}
            isFavorite={favs.isFavorite} toggleFavorite={favs.toggleFavorite} />
        ) : isWorkspace && path[1] === "segmentation-planner" ? (
          <SegmentationPlanner key={path.join("/")}
            handoff={path[2] === "for" && path[3] ? { brand: path[3], planId: Number(path[4]) || null, campaignId: Number(path[5]) || null } : undefined}
            brands={brands} activeBrand={scope.activeBrand}
            isFavorite={favs.isFavorite} toggleFavorite={favs.toggleFavorite} />
        ) : isWorkspace ? (
          <Workspace key={path.join("/")} agentId={path[1]}
            artifactId={path[2] !== "for" ? path[2] : undefined}
            handoff={path[2] === "for" && path[3] ? { brand: path[3], planId: Number(path[4]) || null, campaignId: Number(path[5]) || null } : undefined}
            brands={brands} activeBrand={scope.activeBrand}
            isFavorite={favs.isFavorite} toggleFavorite={favs.toggleFavorite} />
        ) : current === "chat" ? (
          <Chat activeBrand={scope.activeBrand} />
        ) : current === "iq/kits" ? (
          <BrandKitPage activeBrand={scope.activeBrand} brands={brands} />
        ) : current === "iq/personas" ? (
          <PersonasPage activeBrand={scope.activeBrand} brands={brands} />
        ) : current === "iq/guardrails" ? (
          <GuardrailsPage activeBrand={scope.activeBrand} brands={brands} />
        ) : current === "iq/intel" ? (
          <MarketIntelPage activeBrand={scope.activeBrand} brands={brands} />
        ) : current === "live" ? (
          <LiveSimulation brands={brands} activeBrand={scope.activeBrand} />
        ) : current === "brands" ? (
          <Brands brands={brands} activeBrand={scope.activeBrand} />
        ) : current === "work" ? (
          <MyWork activeBrand={scope.activeBrand} />
        ) : path[0] === "app" ? <AppDetail id={path[1] ?? ""} /> : isHome ? (
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
