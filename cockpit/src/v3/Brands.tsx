import { useEffect, useState } from "react";
import { getBrandTree } from "../api";
import type { BrandSummary, BrandTree } from "../types";

/** Brands & Campaigns (Phase 7): the planning hierarchy for the active brand, with each campaign's
 *  next steps handed to the agents and its full record still on the classic detail pages. */
export function Brands({ brands, activeBrand }: { brands: BrandSummary[]; activeBrand: string | null }) {
  const brand = activeBrand ?? brands[0]?.brand ?? null;
  const [tree, setTree] = useState<BrandTree | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!brand) return;
    setTree(null); setError(null);
    getBrandTree(brand).then(setTree).catch((e) => setError(String(e)));
  }, [brand]);

  const e = encodeURIComponent;
  return (
    <div className="v3-brands">
      <h1 className="v3-page-title">Brands &amp; Campaigns</h1>
      <p className="v3-page-sub">
        {brand ? <>Engagement plans and campaigns for <b>{brand}</b>. Switch brand in the rail.</> : "No brands yet."}
        {brand && <> · <a href={`#/b/${e(brand)}`}>Open the classic brand overview</a></>}
      </p>
      {error && <p className="v3-empty">Couldn't load {brand}: {error}</p>}
      {brand && !tree && !error && <p className="v3-empty">Loading…</p>}
      {tree && tree.engagement_plans.length === 0 && (
        <p className="v3-empty">No engagement plans for {brand} yet.</p>
      )}
      {tree?.engagement_plans.map((p) => (
        <section key={p.id} className="v3-brands-plan">
          <header>
            <a href={`#/b/${e(brand!)}/p/${p.id}`}><b>{p.name}</b></a>
            <span>{[p.period_start, p.period_end].filter(Boolean).join(" – ") || "No period set"} · {p.status}</span>
          </header>
          {p.campaigns.length === 0 ? <p className="v3-empty">No campaigns in this plan.</p> : (
            <table className="v3-brands-table">
              <thead><tr><th>Campaign</th><th>Status</th><th>Flows</th><th>Next</th></tr></thead>
              <tbody>
                {p.campaigns.map((c) => {
                  const scope = `for/${e(brand!)}/${p.id}/${c.id}`;
                  return (
                    <tr key={c.id}>
                      <td><a href={`#/b/${e(brand!)}/p/${p.id}/c/${c.id}`}>{c.name}</a></td>
                      <td>{c.status}</td>
                      <td>{c.flows.length}</td>
                      <td className="v3-brands-next">
                        <a href={`#/v3/agent/campaign-planner/${scope}`}>Plan</a>
                        <a href={`#/v3/agent/flow-planner/${scope}`}>Flow</a>
                        <a href={`#/v3/agent/briefing-agent/${scope}`}>Brief</a>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </section>
      ))}
    </div>
  );
}
