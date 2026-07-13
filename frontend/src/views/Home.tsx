import { useEffect, useState } from "react";
import Box from "@mui/material/Box";
import LinearProgress from "@mui/material/LinearProgress";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import { fetchHome, type HomePayload } from "../api";
import { BrandPlate } from "../components/BrandPlate";
import { ConsolePanel } from "../components/ConsolePanel";
import { StatOdometer } from "../components/StatOdometer";
import { StatesShowcase } from "../components/StatesShowcase";
import { TactileButton, KeycapSublabel } from "../components/TactileButton";
import { TickerStrip } from "../components/TickerStrip";
import { tokens, shade, light, insetShadow, enamelFace } from "../theme/tokens";

const LIFE_META: Record<string, { label: string; color: string }> = {
  launch: { label: "Launch", color: tokens.color.primary },
  growth: { label: "Growth", color: tokens.color.success },
  mature: { label: "Mature", color: tokens.color.secondary },
  loe: { label: "Loss of exclusivity", color: tokens.color.warning },
};

/** Recessed channel holding enamel lifecycle segments. */
const MixGroove = styled("div")({
  display: "flex",
  height: 16,
  borderRadius: tokens.radius.sm,
  overflow: "hidden",
  background: shade(0.12),
  boxShadow: insetShadow,
});

export function Home({
  onPlanBrand,
  onStartProject,
}: {
  onPlanBrand: (brand: string) => void;
  onStartProject: () => void;
}) {
  const [data, setData] = useState<HomePayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchHome().then(setData).catch((e) => setError(String(e)));
  }, []);

  const dash = data?.dashboard ?? {};
  const totals = dash.totals ?? {};
  const lib = dash.library ?? {};
  const clients = dash.clients ?? [];
  const allBrands = clients.flatMap((c) => c.brands);
  const mix = allBrands.reduce<Record<string, number>>((acc, b) => {
    acc[b.lifecycle_key] = (acc[b.lifecycle_key] ?? 0) + 1;
    return acc;
  }, {});
  const approvedPct = lib.claims ? Math.round(((lib.approved_claims ?? 0) / lib.claims) * 100) : 0;

  return (
    <>
      <TickerStrip feed={data?.feed ?? []} />
      <Box sx={{ maxWidth: 1240, mx: "auto", px: 6, py: 6, display: "flex", flexDirection: "column", gap: 6 }}>
        <Box>
          <Typography variant="h1">Brand Command Center</Typography>
          <Typography variant="body2" sx={{ color: "text.secondary", mt: 1 }}>
            Live performance read across your client portfolio, grounded in indexed public evidence.
          </Typography>
          {error && (
            <Typography variant="body2" sx={{ color: "error.main", mt: 2 }}>
              Could not reach /api/home — is the FastAPI server running? ({error})
            </Typography>
          )}
        </Box>

        <Box sx={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
          <StatOdometer value={totals.brands ?? 0} label="Brands" />
          <StatOdometer value={totals.clients ?? 0} label="Clients" />
          <StatOdometer value={totals.recruiting_trials ?? 0} label="Recruiting trials" />
          <StatOdometer value={totals.campaigns ?? 0} label="Campaigns" />
          <StatOdometer value={lib.claims ?? 0} label="Claims in library" />
          <StatOdometer value={lib.content_assets ?? 0} label="Content assets" />
          {lib.unsubstantiated_claims ? (
            <StatOdometer value={lib.unsubstantiated_claims} label="Unsubstantiated" alert />
          ) : null}
        </Box>

        <TactileButton variant="contained" onClick={onStartProject} fullWidth>
          <span>
            Start new project
            <KeycapSublabel>PLANNING → ORCHESTRATION → OPERATIONS → REPORTING</KeycapSublabel>
          </span>
        </TactileButton>

        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 4 }}>
          <ConsolePanel title="Lifecycle mix">
            <MixGroove role="img" aria-label="Portfolio lifecycle mix">
              {Object.entries(LIFE_META)
                .filter(([k]) => mix[k])
                .map(([k, meta]) => (
                  <Box
                    key={k}
                    title={`${meta.label}: ${mix[k]}`}
                    sx={{
                      width: `${((mix[k] ?? 0) / (allBrands.length || 1)) * 100}%`,
                      background: enamelFace(meta.color),
                      borderRight: `1px solid ${shade(0.3)}`,
                    }}
                  />
                ))}
            </MixGroove>
            <Box sx={{ display: "flex", gap: 4, flexWrap: "wrap", mt: 3 }}>
              {Object.entries(LIFE_META)
                .filter(([k]) => mix[k])
                .map(([k, meta]) => (
                  <Typography key={k} variant="caption" sx={{ display: "inline-flex", alignItems: "center", gap: 1 }}>
                    <Box component="i" sx={{
                      width: 10, height: 10, borderRadius: "50%",
                      background: enamelFace(meta.color),
                      border: `1px solid ${shade(0.3)}`,
                      boxShadow: `inset 0 1px 0 ${light(0.5)}`,
                    }} />
                    {meta.label} <b>{mix[k]}</b>
                  </Typography>
                ))}
            </Box>
          </ConsolePanel>

          <ConsolePanel title="Content library health">
            <Box sx={{ display: "flex", alignItems: "center", gap: 3 }}>
              <Box sx={{ flex: 1 }}>
                <LinearProgress variant="determinate" value={approvedPct} color="success" />
              </Box>
              <Typography sx={{ fontFamily: tokens.font.mono, fontWeight: 700 }}>{approvedPct}%</Typography>
            </Box>
            <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mt: 1 }}>
              MLR-approved claims: {lib.approved_claims ?? 0} / {lib.claims ?? 0} · Assets: {lib.content_assets ?? 0} ·
              Modules: {lib.modules ?? 0}
            </Typography>
          </ConsolePanel>
        </Box>

        {clients.map((group) => (
          <Box key={group.client}>
            <Box sx={{ display: "flex", alignItems: "baseline", gap: 2, mb: 3 }}>
              <Typography variant="h2">{group.client}</Typography>
              <Typography variant="caption" sx={{ color: "text.secondary" }}>
                {group.brands.length} brand{group.brands.length === 1 ? "" : "s"}
              </Typography>
            </Box>
            <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr", lg: "1fr 1fr 1fr" }, gap: 4 }}>
              {group.brands.map((b) => (
                <BrandPlate key={b.brand} brand={b} onPlan={onPlanBrand} />
              ))}
            </Box>
          </Box>
        ))}

        <StatesShowcase />
      </Box>
    </>
  );
}
