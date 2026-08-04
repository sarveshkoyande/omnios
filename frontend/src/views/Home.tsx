import { useEffect, useMemo, useState } from "react";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import useMediaQuery from "@mui/material/useMediaQuery";
import { fetchHome, listProjects, type HomePayload } from "../api";
import { STAGE_AGENTS, type ProjectSummary, type StageAgentId } from "../workspace/types";
import { tokens, motion, hoverOnly, light, focusRing, focusRingOnBrand } from "../theme/tokens";

/**
 * Hero artwork. Drop the file at app/static/home/home-hero-bg.png — FastAPI already
 * serves app/static at /static, so swapping the image needs no rebuild (see the
 * MANIFEST in that folder). A missing file degrades to the flat `heroInk` panel
 * rather than a broken image, because the colour is painted underneath it.
 */
const HERO_IMAGE = "/static/home/home-hero-bg.png";

/**
 * The artwork is left-weighted — dense dashboard illustration across its left third, near-empty
 * navy through the middle. The copy is left-weighted too, so painted as-is the two collide and
 * the scrim has to bury the best part of the image just to keep 28px white text legible.
 * Mirroring puts the dense side under the translucent stat tiles, which read fine over detail,
 * and leaves the quiet middle under the headline and composer.
 */
const HERO_IMAGE_TRANSFORM = "scaleX(-1)";

/**
 * Scrim over the artwork. Text contrast can't depend on what the image contains, so the panel
 * keeps its own floor — heaviest under the copy, lightest across the middle where the mirrored
 * illustration should actually show.
 */
const HERO_SCRIM =
  "linear-gradient(90deg, rgba(4,33,74,0.92) 0%, rgba(4,33,74,0.80) 34%, rgba(4,33,74,0.44) 62%, rgba(4,33,74,0.58) 100%)";

/**
 * The four workspace stages, in workspace order. `stage` is the 1-based tab index the
 * Workspace opens on, so every card and pipeline node here is a real navigation, not a
 * decoration. Names come from STAGE_AGENTS so Home can never drift from the chat header.
 *
 * `short` is the pipeline label — the pipeline is a picture of the four stages, so it
 * uses the stage's own name ("Insights"), not the agent's ("Reporting & Insights Agent").
 */
type Stage = {
  id: StageAgentId;
  name: string;
  short: string;
  blurb: string;
  icon: string;
  stage: number;
  accent: string;
  accentLight: string;
  accentDark: string;
  tint: string;
};

const STAGES: Stage[] = [
  {
    id: "planning",
    name: STAGE_AGENTS.planning.name,
    short: "Planning",
    blurb: "Turn brand strategy into execution-ready campaign plans.",
    icon: "track_changes",
    stage: 1,
    accent: STAGE_AGENTS.planning.c1,
    accentLight: STAGE_AGENTS.planning.c2,
    accentDark: "#0B4DA2",
    tint: "#EEF6FF",
  },
  {
    id: "orchestration",
    name: STAGE_AGENTS.orchestration.name,
    short: "Orchestration",
    blurb: "Design omnichannel journeys that reach the right HCPs.",
    icon: "hub",
    stage: 2,
    accent: STAGE_AGENTS.orchestration.c1,
    accentLight: STAGE_AGENTS.orchestration.c2,
    accentDark: "#065F46",
    tint: "#ECFDF5",
  },
  {
    id: "operations",
    name: STAGE_AGENTS.operations.name,
    short: "Operations",
    blurb: "Build the assets and activities that put the plan into market.",
    icon: "fact_check",
    stage: 3,
    accent: STAGE_AGENTS.operations.c1,
    accentLight: STAGE_AGENTS.operations.c2,
    accentDark: "#9F1239",
    tint: "#FFF1F5",
  },
  {
    id: "reporting",
    name: STAGE_AGENTS.reporting.name,
    short: "Insights",
    blurb: "Measure performance and surface the next best action.",
    icon: "monitoring",
    stage: 4,
    accent: STAGE_AGENTS.reporting.c1,
    accentLight: STAGE_AGENTS.reporting.c2,
    accentDark: "#C2410C",
    tint: "#FFF3EA",
  },
];

const STAGE_BY_ID = Object.fromEntries(STAGES.map((item) => [item.id, item])) as Record<StageAgentId, Stage>;

/**
 * Plans shown before "View all" is pressed. It has to track the grid's column count,
 * not sit at a constant: a fixed 4 leaves one orphaned card on a second row as soon as
 * the grid drops to 3 columns below xl. Keyed off the same 1536px breakpoint the grid uses.
 */
const XL_QUERY = "(min-width:1536px)";
const COLLAPSED_PROJECTS_XL = 4;
const COLLAPSED_PROJECTS = 3;

const stageOf = (project: ProjectSummary): Stage => STAGE_BY_ID[project.stage ?? "planning"] ?? STAGE_BY_ID.planning;

/** Single classification per project — a plan is drafting, running, or ready, never two at once. */
type StatusKey = "drafting" | "running" | "review";

const STATUS_META: Record<StatusKey, { label: string; icon: string; ink: string; soft: string }> = {
  drafting: { label: "Drafting brief", icon: "edit_note", ink: tokens.color.infoInk, soft: tokens.color.infoSoft },
  running: { label: "In progress", icon: "sync", ink: tokens.color.successInk, soft: tokens.color.successSoft },
  review: { label: "Ready to review", icon: "rate_review", ink: tokens.color.warningInk, soft: tokens.color.warningSoft },
};

function statusOf(project: ProjectSummary): StatusKey {
  if (project.phase === "done" || project.has_result) return "review";
  if (project.phase === "running") return "running";
  return "drafting";
}

function progressFor(project: ProjectSummary, index: number) {
  if (project.phase === "done" || project.has_result) return 90;
  if (project.phase === "running") return 48;
  return [76, 58, 34][index % 3];
}

type BriefItem = { agent: string; text: string; action: string; icon: string; accent: string; stage: number };

function buildBriefItems(projects: ProjectSummary[], assets: number, brands: number): BriefItem[] {
  const items: BriefItem[] = projects.slice(0, 3).map((project) => {
    const stage = stageOf(project);
    const title = project.campaign_name || project.name || project.brand || project.id;
    return {
      agent: stage.name,
      text: `${title} is in ${stage.short.toLowerCase()}.`,
      action: statusOf(project) === "review" ? "Review" : "Continue",
      icon: stage.icon,
      accent: stage.accent,
      stage: stage.stage,
    };
  });

  if (assets > 0) {
    items.push({
      agent: STAGE_BY_ID.operations.name,
      text: `${assets} content asset${assets === 1 ? "" : "s"} available in the library.`,
      action: "View assets",
      icon: "fact_check",
      accent: STAGE_BY_ID.operations.accent,
      stage: 3,
    });
  }

  if (brands > 0) {
    items.push({
      agent: STAGE_BY_ID.planning.name,
      text: `${brands} brand${brands === 1 ? "" : "s"} available for campaign planning.`,
      action: "Plan next",
      icon: "track_changes",
      accent: STAGE_BY_ID.planning.accent,
      stage: 1,
    });
  }

  return items.slice(0, 4);
}

export function Home({
  onOpenPlan,
  onStartNew,
  onImportFile,
}: {
  onOpenPlan: (id: string) => void;
  onStartNew: (seed?: string, initialStage?: number) => void;
  onImportFile: (file: File) => void;
}) {
  const [data, setData] = useState<HomePayload | null>(null);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [quick, setQuick] = useState("");
  const [showAllProjects, setShowAllProjects] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isXl = useMediaQuery(XL_QUERY);

  useEffect(() => {
    fetchHome().then(setData).catch((e) => setError(String(e)));
    listProjects().then(setProjects).catch(() => {});
  }, []);

  const dash = data?.dashboard ?? {};
  const totals = dash.totals ?? {};
  const lib = dash.library ?? {};
  const clients = dash.clients ?? [];
  const brands = totals.brands ?? clients.reduce((sum, client) => sum + client.brands.length, 0);
  const collapsedCount = isXl ? COLLAPSED_PROJECTS_XL : COLLAPSED_PROJECTS;
  const visibleProjects = showAllProjects ? projects : projects.slice(0, collapsedCount);

  /** Pipeline counts are the real distribution of saved plans across the four stages. */
  const pipeline = useMemo(() => {
    const counts: Record<StageAgentId, number> = { planning: 0, orchestration: 0, operations: 0, reporting: 0 };
    projects.forEach((project) => {
      counts[stageOf(project).id] += 1;
    });
    return counts;
  }, [projects]);

  const statusCounts = useMemo(() => {
    const counts: Record<StatusKey, number> = { drafting: 0, running: 0, review: 0 };
    projects.forEach((project) => {
      counts[statusOf(project)] += 1;
    });
    return counts;
  }, [projects]);

  const heroStats = useMemo(
    () => [
      { label: "Active plans", value: projects.length, icon: "description", accent: STAGE_BY_ID.planning.accentLight },
      { label: "In progress", value: statusCounts.running, icon: "sync", accent: STAGE_BY_ID.orchestration.accentLight },
      { label: "Ready to review", value: statusCounts.review, icon: "rate_review", accent: STAGE_BY_ID.reporting.accentLight },
      { label: "Content assets", value: lib.content_assets ?? 0, icon: "folder", accent: STAGE_BY_ID.operations.accentLight },
    ],
    [lib.content_assets, projects.length, statusCounts.review, statusCounts.running],
  );

  const briefItems = useMemo(
    () => buildBriefItems(projects, lib.content_assets ?? 0, brands),
    [brands, lib.content_assets, projects],
  );

  const startQuick = () => {
    const text = quick.trim();
    setQuick("");
    onStartNew(text || undefined);
  };

  const pickBrandPlan = () => document.getElementById("home-brand-plan-input")?.click();

  return (
    <Box
      component="main"
      sx={{ minHeight: `calc(100vh - ${tokens.layout.topBarHeight}px)`, background: tokens.color.bgBase, color: tokens.color.ink }}
    >
      <Box
        sx={{
          // Widens past the standard 1240 on xl (>=1536px). At 1920 the old cap left
          // ~340px of dead margin either side and the page read as half-empty.
          maxWidth: { xs: 1240, xl: 1600 },
          mx: "auto",
          px: { xs: 2, md: 4 },
          py: { xs: 3, md: 4 },
          display: "flex",
          flexDirection: "column",
          gap: 4,
        }}
      >
        {error && (
          <Typography variant="body2" sx={{ color: tokens.color.danger }}>
            Could not reach /api/home. Is the FastAPI server running? ({error})
          </Typography>
        )}

        {/* ---------------------------------------------------------------- hero */}
        <Box
          component="section"
          aria-label="Start a campaign"
          sx={{
            position: "relative",
            overflow: "hidden",
            borderRadius: `${tokens.radius.lg}px`,
            backgroundColor: tokens.color.heroInk,
            p: { xs: 2.5, md: 4 },
            display: "grid",
            gridTemplateColumns: { xs: "1fr", lg: "minmax(0, 1fr) 392px" },
            gap: { xs: 3, lg: 4 },
            alignItems: "center",
          }}
        >
          {/* Artwork and scrim are absolutely positioned rather than background layers so the
              image can be mirrored — background-image has no transform. Both are out of grid
              flow, so the two content children below still lay out as the declared 2 columns. */}
          <Box
            component="img"
            src={HERO_IMAGE}
            alt=""
            aria-hidden
            sx={{
              position: "absolute",
              inset: 0,
              width: "100%",
              height: "100%",
              objectFit: "cover",
              objectPosition: "center",
              transform: HERO_IMAGE_TRANSFORM,
            }}
          />
          <Box aria-hidden sx={{ position: "absolute", inset: 0, background: HERO_SCRIM }} />

          <Box sx={{ position: "relative", zIndex: 1, minWidth: 0 }}>
            <Typography
              component="h1"
              sx={{
                fontSize: { xs: tokens.fontSize.xxl, md: tokens.fontSize.display },
                fontWeight: 800,
                letterSpacing: "-0.01em",
                lineHeight: 1.2,
                color: tokens.color.surface,
              }}
            >
              Good morning, Shaswata
            </Typography>
            <Typography sx={{ mt: 1, fontSize: tokens.fontSize.md, color: light(0.78), maxWidth: "58ch" }}>
              What would you like the campaign agents to help you with today?
            </Typography>

            <Box
              sx={{
                mt: 3,
                // Capped: on xl the hero column is ~1100px and an uncapped input reads
                // as a stretched bar rather than a composer.
                maxWidth: 760,
                display: "grid",
                gridTemplateColumns: "44px minmax(0, 1fr) 44px",
                alignItems: "center",
                gap: 1.5,
                p: 1.25,
                borderRadius: `${tokens.radius.lg}px`,
                background: tokens.color.surface,
              }}
            >
              <Box
                aria-hidden
                sx={{
                  width: 44,
                  height: 44,
                  borderRadius: "50%",
                  display: "grid",
                  placeItems: "center",
                  background: STAGE_BY_ID.planning.tint,
                  color: STAGE_BY_ID.planning.accent,
                }}
              >
                <span className="material-symbols-outlined" style={{ fontSize: 22 }}>auto_awesome</span>
              </Box>
              <Box
                component="textarea"
                rows={1}
                value={quick}
                aria-label="Ask the campaign agents anything"
                onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setQuick(e.target.value)}
                onKeyDown={(e: React.KeyboardEvent<HTMLTextAreaElement>) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    startQuick();
                  }
                }}
                placeholder="Ask about your campaigns, plans, assets or performance"
                sx={{
                  minWidth: 0,
                  width: "100%",
                  minHeight: 26,
                  maxHeight: 104,
                  resize: "none",
                  border: 0,
                  outline: 0,
                  p: 0,
                  fontFamily: tokens.font.primary,
                  fontSize: tokens.fontSize.md,
                  lineHeight: 1.6,
                  color: tokens.color.ink,
                  background: "transparent",
                  "&::placeholder": { color: tokens.color.inkSecondary, opacity: 1 },
                  "&:focus-visible": focusRing,
                }}
              />
              <Box
                role="button"
                tabIndex={0}
                aria-label="Send request"
                onClick={startQuick}
                onKeyDown={onActivate(startQuick)}
                sx={{
                  width: 44,
                  height: 44,
                  borderRadius: "50%",
                  display: "grid",
                  placeItems: "center",
                  cursor: "pointer",
                  color: tokens.color.surface,
                  background: tokens.color.primary,
                  transition: `background ${motion.duration.hover} ${motion.easeOut}, transform ${motion.duration.press} ${motion.easeOut}`,
                  [hoverOnly]: { "&:hover": { background: tokens.color.primaryDark } },
                  "&:active": { transform: "scale(0.94)" },
                  "&:focus-visible": focusRing,
                }}
              >
                <span className="material-symbols-outlined" style={{ fontSize: 22 }}>send</span>
              </Box>
            </Box>

            <Box sx={{ mt: 2, display: "flex", flexWrap: "wrap", gap: 1 }}>
              <HeroChip icon="upload_file" label="Import brand plan" onClick={pickBrandPlan} />
              <HeroChip icon="edit_note" label="Create brief" onClick={() => onStartNew(undefined, 1)} />
              <HeroChip icon="monitoring" label="Analyse performance" onClick={() => onStartNew(undefined, 4)} />
            </Box>

            <input
              id="home-brand-plan-input"
              type="file"
              accept=".pdf,.docx,.txt,.md"
              style={{ display: "none" }}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) onImportFile(file);
                e.target.value = "";
              }}
            />
          </Box>

          <Box sx={{ position: "relative", zIndex: 1, display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 1.5 }}>
            {heroStats.map((stat) => (
              <Box
                key={stat.label}
                sx={{
                  minWidth: 0,
                  p: 2,
                  borderRadius: `${tokens.radius.md}px`,
                  // Opaque enough to sit over the mirrored illustration without the
                  // value and label competing with it. A light() wash was legible at
                  // 1920 but went busy at 1280, where the art crowds the tile column.
                  background: "rgba(4, 33, 74, 0.62)",
                  border: `1px solid ${light(0.22)}`,
                }}
              >
                <Box
                  aria-hidden
                  sx={{
                    width: 34,
                    height: 34,
                    borderRadius: "50%",
                    display: "grid",
                    placeItems: "center",
                    background: light(0.14),
                    color: stat.accent,
                  }}
                >
                  <span className="material-symbols-outlined" style={{ fontSize: 19 }}>{stat.icon}</span>
                </Box>
                <Typography
                  sx={{
                    mt: 1.5,
                    fontSize: tokens.fontSize.xxl,
                    fontWeight: 800,
                    lineHeight: 1,
                    color: tokens.color.surface,
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {stat.value}
                </Typography>
                <Typography sx={{ mt: 0.75, fontSize: tokens.fontSize.xs, color: light(0.76) }}>{stat.label}</Typography>
              </Box>
            ))}
          </Box>
        </Box>

        {/* ------------------------------------------------------------- agents */}
        <Box component="section" aria-label="Agents">
          <SectionHeader title="Choose an agent" subtitle="Jump straight into one of the four campaign stages" />
          <Box
            sx={{
              mt: 2,
              display: "grid",
              gridTemplateColumns: { xs: "1fr", sm: "repeat(2, minmax(0, 1fr))", lg: "repeat(4, minmax(0, 1fr))" },
              gap: 2,
            }}
          >
            {STAGES.map((stage) => (
              <AgentCard key={stage.id} stage={stage} onOpen={() => onStartNew(undefined, stage.stage)} />
            ))}
          </Box>
        </Box>

        {/* ---------------------------------------------------- continue working */}
        <Box component="section" aria-label="Continue working">
          <SectionHeader
            title="Continue working"
            subtitle={showAllProjects ? `All ${projects.length} saved plans` : "Pick up where you left off"}
            action={
              projects.length > collapsedCount ? (
                <GhostButton
                  icon={showAllProjects ? "expand_less" : "expand_more"}
                  label={showAllProjects ? "Show less" : `View all ${projects.length}`}
                  onClick={() => setShowAllProjects((open) => !open)}
                />
              ) : undefined
            }
          />
          <Box
            sx={{
              mt: 2,
              display: "grid",
              gridTemplateColumns: {
                xs: "1fr",
                sm: "repeat(2, minmax(0, 1fr))",
                lg: "repeat(3, minmax(0, 1fr))",
                xl: "repeat(4, minmax(0, 1fr))",
              },
              gap: 2,
              alignItems: "stretch",
            }}
          >
            {visibleProjects.length > 0 ? (
              visibleProjects.map((project, index) => (
                <WorkCard key={project.id} project={project} index={index} onOpen={() => onOpenPlan(project.id)} />
              ))
            ) : (
              <EmptyPanel text="No saved campaign plans yet. Start one from the box above." />
            )}
          </Box>
        </Box>

        {/* ----------------------------------------------------------- pipeline */}
        <Box component="section" aria-label="Campaign pipeline">
          <SectionHeader title="Campaign pipeline" subtitle="Where your plans sit across the four stages" />
          <Pipeline
            counts={pipeline}
            total={projects.length}
            brands={brands}
            clients={totals.clients ?? clients.length}
            campaigns={totals.campaigns ?? 0}
            onOpenStage={(stage) => onStartNew(undefined, stage)}
          />
        </Box>

        {/* -------------------------------------------------------------- brief */}
        {briefItems.length > 0 && (
          <Box component="section" aria-label="Today's brief">
            <SectionHeader title="Today's brief" subtitle="Updates worth acting on" />
            <Box
              sx={{
                mt: 2,
                display: "grid",
                gridTemplateColumns: { xs: "1fr", sm: "repeat(2, minmax(0, 1fr))", lg: "repeat(4, minmax(0, 1fr))" },
                gap: 2,
                p: 2.5,
                borderRadius: `${tokens.radius.md}px`,
                border: `1px solid ${tokens.color.outline}`,
                background: tokens.color.surface,
              }}
            >
              {briefItems.map((item) => (
                <Box
                  key={`${item.agent}-${item.text}`}
                  sx={{ display: "grid", gridTemplateColumns: "40px minmax(0, 1fr)", gap: 1.5, alignItems: "start" }}
                >
                  <Box
                    aria-hidden
                    sx={{
                      width: 40,
                      height: 40,
                      borderRadius: "50%",
                      display: "grid",
                      placeItems: "center",
                      color: tokens.color.surface,
                      background: item.accent,
                    }}
                  >
                    <span className="material-symbols-outlined" style={{ fontSize: 20 }}>{item.icon}</span>
                  </Box>
                  <Box sx={{ minWidth: 0 }}>
                    <Typography sx={{ fontSize: tokens.fontSize.xs, fontWeight: 700 }}>{item.agent}</Typography>
                    <Typography sx={{ mt: 0.5, fontSize: tokens.fontSize.xs, color: tokens.color.inkSecondary, lineHeight: 1.45 }}>
                      {item.text}
                    </Typography>
                    <Box
                      role="button"
                      tabIndex={0}
                      onClick={() => onStartNew(undefined, item.stage)}
                      onKeyDown={onActivate(() => onStartNew(undefined, item.stage))}
                      sx={{
                        mt: 1.25,
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 0.5,
                        fontSize: tokens.fontSize.xs,
                        fontWeight: 700,
                        color: item.accent,
                        cursor: "pointer",
                        "&:focus-visible": focusRing,
                      }}
                    >
                      {item.action}
                      <span className="material-symbols-outlined" style={{ fontSize: 16, verticalAlign: "middle" }}>
                        arrow_forward
                      </span>
                    </Box>
                  </Box>
                </Box>
              ))}
            </Box>
          </Box>
        )}
      </Box>
    </Box>
  );
}

/** Enter/Space handler for the div-as-button pattern this file uses throughout. */
function onActivate(run: () => void) {
  return (event: React.KeyboardEvent) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      run();
    }
  };
}

function HeroChip({ icon, label, onClick }: { icon: string; label: string; onClick: () => void }) {
  return (
    <Box
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={onActivate(onClick)}
      sx={{
        display: "inline-flex",
        alignItems: "center",
        gap: 0.75,
        height: 38,
        px: 1.75,
        borderRadius: `${tokens.radius.pill}px`,
        border: `1px solid ${light(0.28)}`,
        background: light(0.08),
        color: tokens.color.surface,
        fontSize: tokens.fontSize.xs,
        fontWeight: 700,
        cursor: "pointer",
        whiteSpace: "nowrap",
        transition: `background ${motion.duration.hover} ${motion.easeOut}, transform ${motion.duration.press} ${motion.easeOut}`,
        [hoverOnly]: { "&:hover": { background: light(0.18) } },
        "&:active": { transform: "scale(0.97)" },
        "&:focus-visible": focusRingOnBrand,
      }}
    >
      <span className="material-symbols-outlined" style={{ fontSize: 18, verticalAlign: "middle" }}>{icon}</span>
      {label}
    </Box>
  );
}

function SectionHeader({ title, subtitle, action }: { title: string; subtitle: string; action?: React.ReactNode }) {
  return (
    <Box sx={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 2 }}>
      <Box sx={{ minWidth: 0 }}>
        <Typography component="h2" sx={{ fontSize: tokens.fontSize.xl, fontWeight: 700, lineHeight: 1.2 }}>
          {title}
        </Typography>
        <Typography sx={{ mt: 0.5, fontSize: tokens.fontSize.sm, color: tokens.color.inkSecondary }}>{subtitle}</Typography>
      </Box>
      {action}
    </Box>
  );
}

/** Outline button used for section-level actions such as "View all". */
function GhostButton({ icon, label, onClick }: { icon: string; label: string; onClick: () => void }) {
  return (
    <Box
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={onActivate(onClick)}
      sx={{
        display: "inline-flex",
        alignItems: "center",
        gap: 0.75,
        height: 38,
        px: 1.75,
        flexShrink: 0,
        borderRadius: `${tokens.radius.sm}px`,
        border: `1px solid ${tokens.color.outline}`,
        background: tokens.color.surface,
        color: tokens.color.primary,
        fontSize: tokens.fontSize.xs,
        fontWeight: 700,
        cursor: "pointer",
        whiteSpace: "nowrap",
        transition: `background ${motion.duration.hover} ${motion.easeOut}, border-color ${motion.duration.hover} ${motion.easeOut}, transform ${motion.duration.press} ${motion.easeOut}`,
        [hoverOnly]: { "&:hover": { background: tokens.color.infoSoft, borderColor: tokens.color.primary } },
        "&:active": { transform: "scale(0.97)" },
        "&:focus-visible": focusRing,
      }}
    >
      {label}
      <span className="material-symbols-outlined" style={{ fontSize: 18, verticalAlign: "middle" }}>{icon}</span>
    </Box>
  );
}

function EmptyPanel({ text }: { text: string }) {
  return (
    <Box
      sx={{
        gridColumn: "1 / -1",
        p: 4,
        borderRadius: `${tokens.radius.md}px`,
        border: `1px dashed ${tokens.color.outline}`,
        background: tokens.color.surface,
        textAlign: "center",
      }}
    >
      <Typography sx={{ fontSize: tokens.fontSize.sm, color: tokens.color.inkSecondary }}>{text}</Typography>
    </Box>
  );
}

/**
 * Agent entry card. No artwork: the robot avatars read as clip-art at this size and
 * bled out of the card frame. Identity here is carried by the stage colour and icon,
 * which is the same language the workspace tabs and the top bar already use.
 */
function AgentCard({ stage, onOpen }: { stage: Stage; onOpen: () => void }) {
  return (
    <Box
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={onActivate(onOpen)}
      sx={{
        display: "grid",
        gridTemplateColumns: "48px minmax(0, 1fr) 20px",
        alignItems: "start",
        gap: 1.75,
        p: 2,
        minHeight: 132,
        borderRadius: `${tokens.radius.md}px`,
        border: `1px solid ${tokens.color.outline}`,
        borderLeft: `3px solid ${stage.accent}`,
        background: `linear-gradient(180deg, ${stage.tint} 0%, ${tokens.color.surface} 62%)`,
        cursor: "pointer",
        transition: `border-color ${motion.duration.hover} ${motion.easeOut}, transform ${motion.duration.press} ${motion.easeOut}`,
        [hoverOnly]: { "&:hover": { borderColor: stage.accent } },
        "&:active": { transform: "scale(0.995)" },
        "&:focus-visible": focusRing,
      }}
    >
      <Box
        aria-hidden
        sx={{
          width: 48,
          height: 48,
          borderRadius: `${tokens.radius.md}px`,
          display: "grid",
          placeItems: "center",
          color: stage.accent,
          background: tokens.color.surface,
          border: `1px solid ${stage.accent}33`,
        }}
      >
        <span className="material-symbols-outlined" style={{ fontSize: 24 }}>{stage.icon}</span>
      </Box>
      <Box sx={{ minWidth: 0 }}>
        <Typography sx={{ fontSize: tokens.fontSize.md, fontWeight: 700, lineHeight: 1.3, textWrap: "balance" }}>
          {stage.name}
        </Typography>
        <Typography sx={{ mt: 0.75, fontSize: tokens.fontSize.xs, color: tokens.color.inkSecondary, lineHeight: 1.45 }}>
          {stage.blurb}
        </Typography>
      </Box>
      <span className="material-symbols-outlined" style={{ fontSize: 20, color: stage.accent, marginTop: 14 }}>
        arrow_forward
      </span>
    </Box>
  );
}

function WorkCard({ project, index, onOpen }: { project: ProjectSummary; index: number; onOpen: () => void }) {
  const stage = stageOf(project);
  const status = STATUS_META[statusOf(project)];
  const progress = progressFor(project, index);
  const title = project.campaign_name || project.name || `CMP-${String(index + 1).padStart(4, "0")}`;
  const objective = project.objective || project.brand || "Campaign work in progress";

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        p: 2,
        borderRadius: `${tokens.radius.md}px`,
        border: `1px solid ${tokens.color.outline}`,
        background: tokens.color.surface,
      }}
    >
      {/* Title owns a full row. Sharing it with the status chip left ~120px for the
          name, which truncated every real campaign title to "Oncomyra 2026 Bra...". */}
      <Box sx={{ display: "grid", gridTemplateColumns: "44px minmax(0, 1fr)", alignItems: "center", gap: 1.5 }}>
        <Box
          aria-hidden
          sx={{
            width: 44,
            height: 44,
            borderRadius: "50%",
            display: "grid",
            placeItems: "center",
            background: stage.tint,
            color: stage.accent,
          }}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 22 }}>{stage.icon}</span>
        </Box>
        <Typography
          title={title}
          sx={{ fontSize: tokens.fontSize.md, fontWeight: 700, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
        >
          {title}
        </Typography>
      </Box>

      <Box sx={{ mt: 1.5, display: "flex", flexWrap: "wrap", alignItems: "center", gap: 0.75 }}>
        <Box
          sx={{
            display: "inline-flex",
            px: 1,
            py: 0.4,
            borderRadius: `${tokens.radius.sm}px`,
            background: stage.tint,
            color: stage.accentDark,
            fontSize: tokens.fontSize.xs,
            fontWeight: 700,
            whiteSpace: "nowrap",
          }}
        >
          {stage.short}
        </Box>
        <Box
          sx={{
            display: "inline-flex",
            alignItems: "center",
            gap: 0.5,
            px: 1,
            py: 0.4,
            borderRadius: `${tokens.radius.sm}px`,
            background: status.soft,
            color: status.ink,
            fontSize: tokens.fontSize.xs,
            fontWeight: 700,
            whiteSpace: "nowrap",
          }}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 15, verticalAlign: "middle" }}>{status.icon}</span>
          {status.label}
        </Box>
      </Box>

      <Typography
        sx={{
          mt: 2,
          fontSize: tokens.fontSize.xs,
          color: tokens.color.inkSecondary,
          lineHeight: 1.5,
          display: "-webkit-box",
          WebkitLineClamp: 2,
          WebkitBoxOrient: "vertical",
          overflow: "hidden",
        }}
      >
        {objective}
      </Typography>

      {/* Spacer keeps the footer pinned to the bottom so the three cards' CTAs line up. */}
      <Box sx={{ flex: 1, minHeight: 16 }} />

      <Box sx={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) auto", gap: 1.5, alignItems: "center" }}>
        <Box
          role="progressbar"
          aria-valuenow={progress}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`${title} progress`}
          sx={{ height: 6, borderRadius: `${tokens.radius.pill}px`, background: tokens.color.canvas, overflow: "hidden" }}
        >
          <Box sx={{ width: `${progress}%`, height: "100%", borderRadius: `${tokens.radius.pill}px`, background: stage.accent }} />
        </Box>
        <Typography sx={{ fontSize: tokens.fontSize.xs, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>
          {progress}%
        </Typography>
      </Box>

      <Box sx={{ mt: 2, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 1.5 }}>
        <Box sx={{ display: "inline-flex", alignItems: "center", gap: 0.75, color: tokens.color.inkSecondary, fontSize: tokens.fontSize.xs }}>
          <span className="material-symbols-outlined" style={{ fontSize: 16, verticalAlign: "middle" }}>calendar_today</span>
          {project.updated_at ? `Updated ${new Date(project.updated_at).toLocaleDateString()}` : "Not yet updated"}
        </Box>
        <Box
          role="button"
          tabIndex={0}
          onClick={onOpen}
          onKeyDown={onActivate(onOpen)}
          sx={{
            height: 36,
            px: 1.5,
            borderRadius: `${tokens.radius.sm}px`,
            display: "inline-flex",
            alignItems: "center",
            gap: 0.75,
            border: `1px solid ${stage.accent}44`,
            color: stage.accentDark,
            fontSize: tokens.fontSize.xs,
            fontWeight: 700,
            cursor: "pointer",
            whiteSpace: "nowrap",
            transition: `background ${motion.duration.hover} ${motion.easeOut}, transform ${motion.duration.press} ${motion.easeOut}`,
            [hoverOnly]: { "&:hover": { background: stage.tint } },
            "&:active": { transform: "scale(0.97)" },
            "&:focus-visible": focusRing,
          }}
        >
          Continue
          <span className="material-symbols-outlined" style={{ fontSize: 17, verticalAlign: "middle" }}>arrow_forward</span>
        </Box>
      </Box>
    </Box>
  );
}

/**
 * Four stage nodes on one connector, plus the real distribution underneath. Counts are
 * saved plans grouped by `project.stage`, so the bar is a picture of actual work in
 * flight — nothing here is a placeholder number.
 */
function Pipeline({
  counts,
  total,
  brands,
  clients,
  campaigns,
  onOpenStage,
}: {
  counts: Record<StageAgentId, number>;
  total: number;
  brands: number;
  clients: number;
  campaigns: number;
  onOpenStage: (stage: number) => void;
}) {
  const meta = [
    { label: "Total plans", value: total },
    { label: "Brands", value: brands },
    { label: "Clients", value: clients },
    { label: "Running campaigns", value: campaigns },
  ];

  return (
    <Box
      sx={{
        mt: 2,
        p: { xs: 2, md: 3 },
        borderRadius: `${tokens.radius.md}px`,
        border: `1px solid ${tokens.color.outline}`,
        background: tokens.color.surface,
      }}
    >
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "repeat(2, minmax(0, 1fr))", md: "repeat(4, minmax(0, 1fr))" }, gap: { xs: 2, md: 0 } }}>
        {STAGES.map((stage, index) => (
          <Box
            key={stage.id}
            role="button"
            tabIndex={0}
            onClick={() => onOpenStage(stage.stage)}
            onKeyDown={onActivate(() => onOpenStage(stage.stage))}
            sx={{
              position: "relative",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 1,
              px: 1,
              py: 1,
              borderRadius: `${tokens.radius.md}px`,
              cursor: "pointer",
              transition: `background ${motion.duration.hover} ${motion.easeOut}, transform ${motion.duration.press} ${motion.easeOut}`,
              [hoverOnly]: { "&:hover": { background: stage.tint } },
              "&:active": { transform: "scale(0.98)" },
              "&:focus-visible": focusRing,
            }}
          >
            {/* Connector sits behind the node and is clipped to a half-segment at each
                end, so the track starts and stops at the first/last circle rather than
                running off into the card padding. Hidden below md, where the nodes wrap
                to two rows and a horizontal line would connect nothing. */}
            <Box
              aria-hidden
              sx={{
                display: { xs: "none", md: "block" },
                position: "absolute",
                top: 33,
                left: 0,
                right: 0,
                height: 2,
                background: tokens.color.outline,
                clipPath: index === 0 ? "inset(0 0 0 50%)" : index === STAGES.length - 1 ? "inset(0 50% 0 0)" : undefined,
              }}
            />
            <Box
              aria-hidden
              sx={{
                position: "relative",
                width: 52,
                height: 52,
                borderRadius: "50%",
                display: "grid",
                placeItems: "center",
                color: tokens.color.surface,
                background: stage.accent,
              }}
            >
              <span className="material-symbols-outlined" style={{ fontSize: 25 }}>{stage.icon}</span>
            </Box>
            <Typography sx={{ fontSize: tokens.fontSize.sm, fontWeight: 700, textAlign: "center" }}>{stage.short}</Typography>
            <Typography
              sx={{ fontSize: tokens.fontSize.xxl, fontWeight: 800, lineHeight: 1, color: stage.accentDark, fontVariantNumeric: "tabular-nums" }}
            >
              {counts[stage.id]}
            </Typography>
          </Box>
        ))}
      </Box>

      {total > 0 ? (
        <Box
          aria-hidden
          sx={{ mt: 3, display: "flex", height: 8, borderRadius: `${tokens.radius.pill}px`, overflow: "hidden", background: tokens.color.canvas }}
        >
          {STAGES.filter((stage) => counts[stage.id] > 0).map((stage) => (
            <Box key={stage.id} sx={{ flexGrow: counts[stage.id], flexBasis: 0, background: stage.accent }} />
          ))}
        </Box>
      ) : (
        <Typography sx={{ mt: 3, fontSize: tokens.fontSize.sm, color: tokens.color.inkSecondary, textAlign: "center" }}>
          No plans in the pipeline yet. Pick an agent above to start one.
        </Typography>
      )}

      <Box
        sx={{
          mt: 2.5,
          pt: 2.5,
          borderTop: `1px solid ${tokens.color.outline}`,
          display: "grid",
          gridTemplateColumns: { xs: "repeat(2, minmax(0, 1fr))", md: "repeat(4, minmax(0, 1fr))" },
          gap: 2,
        }}
      >
        {meta.map((item) => (
          <Box key={item.label} sx={{ display: "flex", alignItems: "baseline", gap: 1, minWidth: 0 }}>
            <Typography sx={{ fontSize: tokens.fontSize.lg, fontWeight: 800, fontVariantNumeric: "tabular-nums" }}>
              {item.value}
            </Typography>
            <Typography sx={{ fontSize: tokens.fontSize.xs, color: tokens.color.inkSecondary }}>{item.label}</Typography>
          </Box>
        ))}
      </Box>
    </Box>
  );
}
