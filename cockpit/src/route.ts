import { useEffect, useState } from "react";
import type { JourneyStepId } from "./types";

/** Hash routes for Brand > Engagement Plan > Campaign > Flow (hierarchy plan KTD9). The hash
 *  keeps deep links and the back button working without a router dependency. */
export type Route =
  | { kind: "home" }
  | { kind: "agents" }
  | { kind: "new-brand" }
  | { kind: "brand"; brand: string; tab: "overview" | "workspace" }
  | { kind: "journey"; brand: string; step: JourneyStepId }
  | { kind: "plan"; brand: string; planId: number }
  | { kind: "campaign"; brand: string; planId: number; campaignId: number }
  | { kind: "flow"; brand: string; planId: number; campaignId: number; flowId: number }
  | { kind: "campaign-plan"; brand: string; planId: number; campaignId: number };

const STEPS: JourneyStepId[] = ["brief", "audience", "message", "kit", "flow"];

export function parseRoute(hash: string): Route {
  const parts = hash.replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
  if (parts[0] === "agents") return { kind: "agents" };
  if (parts[0] === "new-brand") return { kind: "new-brand" };
  if (parts[0] !== "b" || !parts[1]) return { kind: "home" };
  const brand = parts[1];
  if (parts[2] === "workspace") return { kind: "brand", brand, tab: "workspace" };
  if (parts[2] === "journey") {
    const step = STEPS.includes(parts[3] as JourneyStepId) ? (parts[3] as JourneyStepId) : "brief";
    return { kind: "journey", brand, step };
  }
  if (parts[2] !== "p" || !Number(parts[3])) return { kind: "brand", brand, tab: "overview" };
  const planId = Number(parts[3]);
  if (parts[4] !== "c" || !Number(parts[5])) return { kind: "plan", brand, planId };
  const campaignId = Number(parts[5]);
  if (parts[6] === "plan") return { kind: "campaign-plan", brand, planId, campaignId };
  if (parts[6] === "f" && Number(parts[7])) return { kind: "flow", brand, planId, campaignId, flowId: Number(parts[7]) };
  return { kind: "campaign", brand, planId, campaignId };
}

export function href(r: Route): string {
  const e = encodeURIComponent;
  switch (r.kind) {
    case "home": return "#/";
    case "agents": return "#/agents";
    case "new-brand": return "#/new-brand";
    case "brand": return r.tab === "workspace" ? `#/b/${e(r.brand)}/workspace` : `#/b/${e(r.brand)}`;
    case "journey": return `#/b/${e(r.brand)}/journey/${r.step}`;
    case "plan": return `#/b/${e(r.brand)}/p/${r.planId}`;
    case "campaign": return `#/b/${e(r.brand)}/p/${r.planId}/c/${r.campaignId}`;
    case "flow": return `#/b/${e(r.brand)}/p/${r.planId}/c/${r.campaignId}/f/${r.flowId}`;
    case "campaign-plan": return `#/b/${e(r.brand)}/p/${r.planId}/c/${r.campaignId}/plan`;
  }
}

export function go(r: Route, replace = false): void {
  const target = href(r);
  if (replace) window.history.replaceState(null, "", target);
  else window.location.hash = target;
  if (replace) window.dispatchEvent(new HashChangeEvent("hashchange"));
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.hash));
  useEffect(() => {
    const on = () => setRoute(parseRoute(window.location.hash));
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return route;
}

export function routeBrand(r: Route): string | null {
  return "brand" in r ? r.brand : null;
}
