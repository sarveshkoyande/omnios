import { useEffect, useMemo, useState } from "react";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { fetchHome, listProjects, type HomePayload } from "../api";
import { FloatingGradient } from "../components/FloatingGradient";
import { PlanCard } from "../components/PlanCard";
import { StatOdometer } from "../components/StatOdometer";
import { TickerStrip } from "../components/TickerStrip";
import { HomeIntakeCard } from "./HomeIntakeCard";
import type { ProjectSummary } from "../workspace/types";
import { tokens, indigoTint, light, shade } from "../theme/tokens";

/** Compose a plain-English read of the plan portfolio — no LLM, derived from data. */
function planSummary(projects: ProjectSummary[], brands: number, campaigns: number): string {
  if (!projects.length) {
    return `No plans yet. Your portfolio has ${brands} brand${brands === 1 ? "" : "s"} onboarded and ${campaigns} campaign${campaigns === 1 ? "" : "s"} on record — start a new requirement above to build your first plan.`;
  }
  const ready = projects.filter((p) => p.has_result || p.phase === "done").length;
  const building = projects.filter((p) => p.phase === "running").length;
  const drafting = projects.length - ready - building;
  const brandSet = new Set(projects.map((p) => (p.brand || "").trim()).filter(Boolean));
  const parts: string[] = [];
  parts.push(
    `You have ${projects.length} plan${projects.length === 1 ? "" : "s"} in flight across ${brandSet.size || brands} brand${(brandSet.size || brands) === 1 ? "" : "s"}.`,
  );
  const state: string[] = [];
  if (ready) state.push(`${ready} plan-ready`);
  if (building) state.push(`${building} building`);
  if (drafting) state.push(`${drafting} still in brief`);
  if (state.length) parts.push(`${state.join(", ")}.`);
  parts.push(`${brands} brand${brands === 1 ? "" : "s"} onboarded, ${campaigns} campaign${campaigns === 1 ? "" : "s"} on record.`);
  return parts.join(" ");
}

/** The four workspace stages a plan can sit in — colors mirror STAGE_AGENTS. */
type StageId = "planning" | "orchestration" | "operations" | "reporting";
const STAGE_TABS: { id: StageId; label: string; color: string }[] = [
  { id: "planning", label: "Planning & Strategy", color: "#1768D1" },
  { id: "orchestration", label: "Engagement Orchestration", color: "#22B36B" },
  { id: "operations", label: "Campaign Operations", color: "#D1341C" },
  { id: "reporting", label: "Reporting & Insights", color: "#F5730A" },
];

export function Home({
  onOpenPlan,
  onStartNew,
  onImportFile,
}: {
  onOpenPlan: (id: string) => void;
  onStartNew: (seed?: string) => void;
  onImportFile: (file: File) => void;
}) {
  const [data, setData] = useState<HomePayload | null>(null);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [quick, setQuick] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [stageTab, setStageTab] = useState<StageId | null>(null);

  useEffect(() => {
    fetchHome().then(setData).catch((e) => setError(String(e)));
    listProjects().then(setProjects).catch(() => {});
  }, []);

  const dash = data?.dashboard ?? {};
  const totals = dash.totals ?? {};
  const lib = dash.library ?? {};
  const clients = dash.clients ?? [];
  const allBrands = clients.flatMap((c) => c.brands);
  const summary = useMemo(
    () => planSummary(projects, totals.brands ?? allBrands.length, totals.campaigns ?? 0),
    [projects, totals.brands, totals.campaigns, allBrands.length],
  );

  const stageCounts = useMemo(() => {
    const counts: Record<StageId, number> = { planning: 0, orchestration: 0, operations: 0, reporting: 0 };
    for (const p of projects) counts[(p.stage ?? "planning") as StageId] += 1;
    return counts;
  }, [projects]);

  // Default to the first stage that actually has plans, until the user picks one.
  const activeStage: StageId = stageTab ?? STAGE_TABS.find((t) => stageCounts[t.id] > 0)?.id ?? "planning";
  const stagePlans = useMemo(
    () => projects.filter((p) => (p.stage ?? "planning") === activeStage),
    [projects, activeStage],
  );

  const startQuick = () => {
    const text = quick.trim();
    setQuick("");
    onStartNew(text || undefined);
  };

  return (
    <>
      <TickerStrip feed={data?.feed ?? []} />

      {/* Full-page soft glow — the animated gradient blobs, now a light-theme
          wash pinned behind the whole dashboard instead of a dark hero band.
          Fixed so it spans the entire viewport as the page scrolls. */}
      <Box
        aria-hidden
        sx={{
          position: "fixed",
          inset: 0,
          zIndex: 0,
          pointerEvents: "none",
          overflow: "hidden",
          background: tokens.color.bgBase,
        }}
      >
        <FloatingGradient light style={{ zIndex: 0 }} />
      </Box>

      <Box
        sx={{
          position: "relative",
          zIndex: 1,
          maxWidth: 1240,
          mx: "auto",
          px: 6,
          pt: 4,
          pb: 6,
          display: "flex",
          flexDirection: "column",
          gap: 5,
        }}
      >
        {error && (
          <Typography variant="body2" sx={{ color: "error.main" }}>
            Could not reach /api/home. Is the FastAPI server running? ({error})
          </Typography>
        )}

        {/* Greeting — circular avatar placeholder + a personal hello above the composer. */}
        <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", gap: 2, mt: 1 }}>
          <Box
            aria-hidden
            sx={{
              width: 80,
              height: 80,
              borderRadius: "50%",
              overflow: "hidden",
              display: "grid",
              placeItems: "center",
              background: `linear-gradient(135deg, ${indigoTint(0.16)}, ${tokens.color.primaryContainer})`,
              border: `2px solid ${tokens.color.surface}`,
              boxShadow: `0 6px 18px ${shade(0.14)}`,
              color: tokens.color.primary,
            }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 44 }}>person</span>
          </Box>
          <Typography sx={{ fontSize: { xs: 22, md: 27 }, fontWeight: 700, color: "text.primary", lineHeight: 1.2 }}>
            Hi Shaswata!{" "}
            <Box component="span" sx={{ color: tokens.color.primary }}>
              What's on your mind today?
            </Box>
          </Typography>
        </Box>

        {/* Quick-start — the dynamic brief intake, straight into a fresh brief. */}
        <HomeIntakeCard value={quick} onChange={setQuick} onSubmit={startQuick} onImport={onImportFile} />

        {/* Dashboard numbers. */}
        <Box sx={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
          <StatOdometer value={totals.brands ?? 0} label="Brands" />
          <StatOdometer value={totals.clients ?? 0} label="Clients" />
          <StatOdometer value={projects.length} label="Plans in flight" />
          <StatOdometer value={totals.campaigns ?? 0} label="Campaigns" />
          <StatOdometer value={lib.content_assets ?? 0} label="Content assets" />
        </Box>

        {/* AI summary — a plain-English read of the portfolio. */}
        <Box
          sx={{
            display: "flex",
            gap: 2.5,
            p: 3,
            borderRadius: tokens.radius.lg,
            background: tokens.color.infoSoft,
            border: `1px solid ${indigoTint(0.18)}`,
          }}
        >
          <Box
            sx={{
              flex: "0 0 auto",
              width: 38,
              height: 38,
              borderRadius: "50%",
              display: "grid",
              placeItems: "center",
              background: tokens.color.primary,
            }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 22, color: "#fff" }}>auto_awesome</span>
          </Box>
          <Box>
            <Typography sx={{ fontSize: tokens.fontSize.xs, fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase", color: tokens.color.onPrimaryContainer, mb: 0.5 }}>
              AI summary
            </Typography>
            <Typography sx={{ fontSize: tokens.fontSize.md, color: "text.primary", lineHeight: 1.55 }}>
              {summary}
            </Typography>
          </Box>
        </Box>

        {/* Your plans — bucketed by the workspace stage each plan currently sits in. */}
        <Box>
          <Box sx={{ display: "flex", alignItems: "baseline", gap: 2, mb: 2.5 }}>
            <Typography variant="h2">Your plans</Typography>
            <Typography variant="caption" sx={{ color: "text.secondary" }}>
              {projects.length} saved
            </Typography>
          </Box>

          {projects.length === 0 ? (
            <Box sx={{ p: 5, textAlign: "center", borderRadius: tokens.radius.lg, border: `1.5px dashed ${indigoTint(0.3)}`, background: light(0.4) }}>
              <Typography variant="body2" sx={{ color: "text.secondary" }}>
                No plans yet. Type a requirement above, or pick a brand below to begin.
              </Typography>
            </Box>
          ) : (
            <>
              {/* Stage tabs — one per workspace stage, with a live count. */}
              <Box
                role="tablist"
                aria-label="Plans by stage"
                sx={{ display: "flex", flexWrap: "wrap", gap: 1, mb: 2.5 }}
              >
                {STAGE_TABS.map((t) => {
                  const active = t.id === activeStage;
                  const count = stageCounts[t.id];
                  return (
                    <Box
                      key={t.id}
                      role="tab"
                      tabIndex={0}
                      aria-selected={active}
                      onClick={() => setStageTab(t.id)}
                      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setStageTab(t.id); } }}
                      sx={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 1,
                        height: 40,
                        px: 2,
                        borderRadius: tokens.radius.pill,
                        cursor: "pointer",
                        userSelect: "none",
                        fontSize: tokens.fontSize.sm,
                        fontWeight: 700,
                        color: active ? t.color : "text.secondary",
                        background: active ? `${t.color}14` : tokens.color.surface,
                        border: `1px solid ${active ? t.color : tokens.color.outline}`,
                        transition: "color 140ms ease, background 140ms ease, border-color 140ms ease",
                        "&:hover": { borderColor: t.color, color: t.color },
                        "&:focus-visible": { outline: `2px solid ${t.color}`, outlineOffset: 2 },
                      }}
                    >
                      {t.label}
                      <Box
                        component="span"
                        sx={{
                          minWidth: 20,
                          height: 20,
                          px: 0.5,
                          borderRadius: tokens.radius.pill,
                          display: "inline-grid",
                          placeItems: "center",
                          fontSize: 11,
                          fontWeight: 800,
                          fontVariantNumeric: "tabular-nums",
                          color: active ? "#fff" : "text.secondary",
                          background: active ? t.color : tokens.color.canvas,
                        }}
                      >
                        {count}
                      </Box>
                    </Box>
                  );
                })}
              </Box>

              {stagePlans.length === 0 ? (
                <Box sx={{ p: 4, textAlign: "center", borderRadius: tokens.radius.lg, border: `1px dashed ${tokens.color.outline}`, background: light(0.4) }}>
                  <Typography variant="body2" sx={{ color: "text.secondary" }}>
                    No plans in {STAGE_TABS.find((t) => t.id === activeStage)?.label} right now.
                  </Typography>
                </Box>
              ) : (
                <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  {stagePlans.map((p) => (
                    <PlanCard key={p.id} plan={p} onOpen={onOpenPlan} />
                  ))}
                </Box>
              )}
            </>
          )}
        </Box>
      </Box>
    </>
  );
}
