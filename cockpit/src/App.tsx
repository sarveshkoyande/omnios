import { useCallback, useEffect, useState } from "react";
import { getBrandKit, getBrandTree, getHierarchySummary, listBrands } from "./api";
import type { BrandKit, BrandSummary, BrandTree, HierarchySummary } from "./types";
import { BrandWorkspace } from "./components/BrandWorkspace";
import { AgentLibrary } from "./components/AgentLibrary";
import { JourneyScreen } from "./components/journey/JourneyScreen";
import { Icon } from "./components/Icon";
import { BrandOverview } from "./components/hierarchy/BrandOverview";
import { EngagementPlanPage } from "./components/hierarchy/EngagementPlanPage";
import { CampaignPage } from "./components/hierarchy/CampaignPage";
import { FlowPage } from "./components/hierarchy/FlowPage";
import { CampaignPlanPage } from "./components/campaignplan/CampaignPlanPage";
import { go, href, routeBrand, useRoute, type Route } from "./route";
import "./cockpit.css";

type Crumb = { label: string; to?: Route };

/** Brand > Engagement Plan > Campaign > Flow, from the route plus the brand's tree (S-R1). */
function crumbsFor(route: Route, tree: BrandTree | null): Crumb[] {
  const brand = routeBrand(route);
  if (!brand) return [];
  const out: Crumb[] = [{ label: brand, to: { kind: "brand", brand, tab: "overview" } }];
  if (route.kind === "journey") out.push({ label: "Brand journey" });
  if (route.kind === "brand" && route.tab === "workspace") out.push({ label: "Brief & kit" });
  if (!("planId" in route)) return out;
  const plan = tree?.engagement_plans.find((p) => p.id === route.planId);
  out.push({ label: plan?.name ?? "Engagement plan", to: { kind: "plan", brand, planId: route.planId } });
  if (!("campaignId" in route)) return out;
  const campaign = plan?.campaigns.find((c) => c.id === route.campaignId);
  out.push({ label: campaign?.name ?? "Campaign", to: { kind: "campaign", brand, planId: route.planId, campaignId: route.campaignId } });
  if (route.kind === "campaign-plan") out.push({ label: "Campaign Plan" });
  if (route.kind === "flow") out.push({ label: campaign?.flows.find((f) => f.id === route.flowId)?.name ?? "Flow" });
  return out;
}

function Breadcrumb({ crumbs }: { crumbs: Crumb[] }) {
  if (crumbs.length < 2) return null;
  return (
    <nav className="breadcrumb" aria-label="Breadcrumb">
      {crumbs.map((c, i) => {
        const last = i === crumbs.length - 1;
        return (
          <span key={i} className="breadcrumb-item">
            {c.to && !last ? <a href={href(c.to)}>{c.label}</a> : <span aria-current={last ? "page" : undefined}>{c.label}</span>}
            {!last && <span className="breadcrumb-sep" aria-hidden>›</span>}
          </span>
        );
      })}
    </nav>
  );
}

export default function App() {
  const route = useRoute();
  const [brands, setBrands] = useState<BrandSummary[] | null>(null);
  const [knownTerritories, setKnownTerritories] = useState<string[]>([]);
  const [territory, setTerritory] = useState<Record<string, string | null>>({});
  const [kit, setKit] = useState<BrandKit | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [kitVersion, setKitVersion] = useState(0);
  const [tree, setTree] = useState<BrandTree | null>(null);
  const [treeError, setTreeError] = useState<string | null>(null);
  const [treeVersion, setTreeVersion] = useState(0);
  const [summary, setSummary] = useState<HierarchySummary>({});

  const brand = routeBrand(route);
  const refreshTree = useCallback(() => setTreeVersion((v) => v + 1), []);

  const loadBrands = useCallback(() => listBrands().then((r) => {
    setBrands(r.brands);
    setKnownTerritories(r.known_territories);
    return r.brands;
  }), []);

  useEffect(() => {
    loadBrands().catch((e) => setError(String(e)));
  }, [loadBrands]);

  // One entry point (S-R4): the landing route opens the first brand.
  useEffect(() => {
    if (route.kind === "home" && brands && brands.length > 0) go({ kind: "brand", brand: brands[0].brand, tab: "overview" }, true);
  }, [route.kind, brands]);

  useEffect(() => {
    getHierarchySummary().then(setSummary).catch(() => undefined);
  }, [treeVersion]);

  useEffect(() => {
    if (!brand) { setTree(null); return; }
    let live = true;
    setTreeError(null);
    getBrandTree(brand).then((t) => { if (live) setTree(t); }).catch((e) => { if (live) { setTree(null); setTreeError(String(e)); } });
    return () => { live = false; };
  }, [brand, treeVersion]);

  const summaryOf = brands?.find((b) => b.brand.toLowerCase() === (brand ?? "").toLowerCase()) ?? null;
  const activeTerritory = brand ? (territory[brand] ?? summaryOf?.territories[0] ?? null) : null;
  const onWorkspace = route.kind === "brand" && route.tab === "workspace";
  // The overview tab wants the kit too -- it's the only source of the brand's brief and
  // message context (indication, objective, positioning), which an engagement plan has
  // none of its own.
  const wantsKit = route.kind === "brand";
  useEffect(() => {
    if (!brand || !wantsKit) return;
    setKit(null);
    getBrandKit(brand, activeTerritory ?? undefined).then((r) => setKit(r.kit)).catch((e) => setError(String(e)));
  }, [brand, wantsKit, activeTerritory, kitVersion]);

  const onNewBrandComplete = async (created: string, step: import("./types").JourneyStepId) => {
    await loadBrands();
    refreshTree();
    go({ kind: "journey", brand: created, step });
  };

  // What the rail expands: the brand, plan and campaign on the current path (S-R3).
  const planId = "planId" in route ? route.planId : null;
  const campaignId = "campaignId" in route ? route.campaignId : null;
  const flowId = route.kind === "flow" ? route.flowId : null;
  const plan = tree?.engagement_plans.find((p) => p.id === planId) ?? null;
  const campaign = plan?.campaigns.find((c) => c.id === campaignId) ?? null;
  const flowMeta = campaign?.flows.find((f) => f.id === flowId) ?? null;
  const brandTab = route.kind === "journey" ? "journey" : route.kind === "brand" ? route.tab : null;

  const main = () => {
    switch (route.kind) {
      case "agents": return <AgentLibrary />;
      case "new-brand":
        return <JourneyScreen key="new" brand={null} initialStep="brief" onBrandCreated={onNewBrandComplete}
          onKitChanged={() => setKitVersion((v) => v + 1)} onClose={() => go({ kind: "home" })} />;
      case "home": return brands && brands.length === 0 ? <div className="loading">No brand kits configured yet.</div> : <div className="loading">Loading&hellip;</div>;
      case "journey":
        return <JourneyScreen key={`${route.brand}-${route.step}`} brand={route.brand} initialStep={route.step}
          onBrandCreated={onNewBrandComplete}
          onKitChanged={() => { setKitVersion((v) => v + 1); refreshTree(); }}
          onClose={() => { refreshTree(); go({ kind: "brand", brand: route.brand, tab: "overview" }); }} />;
      case "brand":
        if (route.tab === "workspace") {
          if (error) return <div className="error-banner">Couldn't load brand data: {error}</div>;
          if (!kit) return <div className="loading">Loading brand workspace&hellip;</div>;
          return <BrandWorkspace brand={route.brand} kit={kit} onUpdate={(step) => go({ kind: "journey", brand: route.brand, step })} />;
        }
        if (treeError) return <div className="error-banner">Couldn't load {route.brand}: {treeError}</div>;
        return tree ? <BrandOverview key={tree.brand} brand={tree.brand} tree={tree} kit={kit} onChanged={refreshTree} /> : <div className="loading">Loading&hellip;</div>;
      default:
        if (treeError) return <div className="error-banner">{treeError}</div>;
        if (!tree) return <div className="loading">Loading&hellip;</div>;
        if (!plan) return <div className="error-banner">That engagement plan isn't in {tree.brand}.</div>;
        if (route.kind === "plan") return <EngagementPlanPage key={plan.id} brand={tree.brand} plan={plan} onChanged={refreshTree} />;
        if (!campaign) return <div className="error-banner">That campaign isn't in {plan.name}.</div>;
        if (route.kind === "campaign") return <CampaignPage key={campaign.id} brand={tree.brand} planId={plan.id} campaign={campaign} onChanged={refreshTree} />;
        if (route.kind === "campaign-plan") {
          return campaign.project_id
            ? <CampaignPlanPage key={campaign.project_id} campaign={campaign} />
            : <div className="hier-page"><div className="jc-empty">This campaign has no Campaign Plan yet.</div></div>;
        }
        if (!flowMeta) return <div className="error-banner">That flow isn't in {campaign.name}.</div>;
        return <FlowPage key={flowMeta.id} brand={tree.brand} planId={plan.id} campaignId={campaign.id} meta={flowMeta} onChanged={refreshTree} />;
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
          <a className={`rail-item ${route.kind === "agents" ? "active" : ""}`} href={href({ kind: "agents" })}>Agent Library</a>

          <div className="rail-section-row" style={{ marginTop: 24 }}>
            <span className="rail-section-label" style={{ marginTop: 0 }}>Brands</span>
            <a className="rail-add-brand" title="Set up a new brand" aria-label="Set up a new brand" href={href({ kind: "new-brand" })}>
              <Icon name="plus" size={14} />
            </a>
          </div>
          {brands?.map((b) => {
            const selected = brand?.toLowerCase() === b.brand.toLowerCase();
            const counts = summary[b.brand];
            return (
              <div key={b.brand} className="rail-brand-block">
                <a className={`rail-item rail-brand-item ${selected && brandTab === "overview" && !planId ? "active" : ""}`}
                  href={href({ kind: "brand", brand: b.brand, tab: "overview" })}>
                  <span className="rail-brand-name">
                    {b.brand}{selected && activeTerritory ? ` (${activeTerritory})` : ""}
                    {counts && counts.active_plans > 0 && (
                      <span className="rail-badge" title={`${counts.active_plans} active engagement plan${counts.active_plans === 1 ? "" : "s"}`}>{counts.active_plans}</span>
                    )}
                  </span>
                  <span className="rail-brand-sub">{b.indication || b.therapy_area}</span>
                </a>
                {selected && (
                  <div className="rail-tree">
                    <a className={`rail-tree-item ${brandTab === "workspace" ? "active" : ""}`} href={href({ kind: "brand", brand: b.brand, tab: "workspace" })}>Brief &amp; kit</a>
                    <a className={`rail-tree-item ${brandTab === "journey" ? "active" : ""}`} href={href({ kind: "journey", brand: b.brand, step: "brief" })}>Brand journey</a>
                    {onWorkspace && (
                      <div className="territory-row">
                        {knownTerritories.map((t) => {
                          const configured = b.territories.includes(t);
                          return (
                            <button key={t} type="button" disabled={!configured}
                              className={`territory-pill ${activeTerritory === t ? "active" : ""} ${!configured ? "disabled" : ""}`}
                              title={configured ? `Switch to ${t}` : `Not configured for ${t} yet`}
                              onClick={() => configured && setTerritory((m) => ({ ...m, [b.brand]: t }))}>
                              {t}
                            </button>
                          );
                        })}
                      </div>
                    )}
                    {(tree?.engagement_plans ?? []).length > 0 && <div className="rail-tree-label">Engagement plans</div>}
                    {tree?.engagement_plans.map((p) => (
                      <div key={p.id}>
                        <a className={`rail-tree-item ${p.status === "closed" ? "is-closed" : ""} ${route.kind === "plan" && p.id === planId ? "active" : ""}`}
                          href={href({ kind: "plan", brand: b.brand, planId: p.id })}>{p.name}</a>
                        {p.id === planId && p.campaigns.map((c) => (
                          <div key={c.id} className="rail-tree-nest">
                            <a className={`rail-tree-item ${c.status === "closed" ? "is-closed" : ""} ${route.kind === "campaign" && c.id === campaignId ? "active" : ""}`}
                              href={href({ kind: "campaign", brand: b.brand, planId: p.id, campaignId: c.id })}>{c.name}</a>
                            {c.id === campaignId && (
                              <div className="rail-tree-nest">
                                {c.has_campaign_plan && (
                                  <a className={`rail-tree-item ${route.kind === "campaign-plan" ? "active" : ""}`}
                                    href={href({ kind: "campaign-plan", brand: b.brand, planId: p.id, campaignId: c.id })}>Campaign Plan</a>
                                )}
                                {c.flows.map((f) => (
                                  <a key={f.id} className={`rail-tree-item ${f.id === flowId ? "active" : ""}`}
                                    href={href({ kind: "flow", brand: b.brand, planId: p.id, campaignId: c.id, flowId: f.id })}>{f.name}</a>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
          {brands && brands.length === 0 && <div className="rail-empty">No brand kits configured yet.</div>}
        </aside>

        <main className="main">
          <Breadcrumb crumbs={crumbsFor(route, tree)} />
          {main()}
        </main>
      </div>
    </div>
  );
}
