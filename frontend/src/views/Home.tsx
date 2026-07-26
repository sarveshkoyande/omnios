import { useEffect, useMemo, useState } from "react";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { fetchHome, listProjects, type HomePayload } from "../api";
import { STAGE_AGENTS, type ProjectSummary } from "../workspace/types";
import { tokens, shade } from "../theme/tokens";

type Specialist = {
  id: "planning" | "orchestration" | "operations" | "reporting";
  name: string;
  description: string;
  icon: string;
  stage: number;
  accent: string;
  accentDark: string;
  tint: string;
};

const SPECIALISTS: Specialist[] = [
  {
    id: "planning",
    name: "Planning Agent",
    description: "Turn strategy into execution-ready campaign plans.",
    icon: "track_changes",
    stage: 1,
    accent: STAGE_AGENTS.planning.c1,
    accentDark: "#0B4DA2",
    tint: "#EEF6FF",
  },
  {
    id: "orchestration",
    name: "Engagement Agent",
    description: "Design omnichannel journeys that engage the right HCPs.",
    icon: "groups",
    stage: 2,
    accent: STAGE_AGENTS.orchestration.c1,
    accentDark: "#065F46",
    tint: "#ECFDF5",
  },
  {
    id: "operations",
    name: "Campaign Agent",
    description: "Create assets, activities and deliver seamless campaign execution.",
    icon: "fact_check",
    stage: 3,
    accent: STAGE_AGENTS.operations.c1,
    accentDark: "#9F1239",
    tint: "#FFF1F5",
  },
  {
    id: "reporting",
    name: "Insights Agent",
    description: "Measure performance and uncover actionable insights.",
    icon: "monitoring",
    stage: 4,
    accent: STAGE_AGENTS.reporting.c1,
    accentDark: "#C2410C",
    tint: "#FFF3EA",
  },
];

const stageMeta: Record<string, { label: string; accent: string; tint: string }> = {
  planning: { label: "Planning & Strategy", accent: STAGE_AGENTS.planning.c1, tint: "#EEF6FF" },
  orchestration: { label: "Engagement Orchestration", accent: STAGE_AGENTS.orchestration.c1, tint: "#ECFDF5" },
  operations: { label: "Campaign Operations", accent: STAGE_AGENTS.operations.c1, tint: "#FFF1F5" },
  reporting: { label: "Reporting & Insights", accent: STAGE_AGENTS.reporting.c1, tint: "#FFF3EA" },
};

type BriefItem = { agent: string; text: string; action: string; icon: string; accent: string; stage: number };

function progressFor(project: ProjectSummary, index: number) {
  if (project.phase === "done" || project.has_result) return 90;
  if (project.phase === "running") return 48;
  return [76, 58, 34][index % 3];
}

function statusFor(project: ProjectSummary) {
  if (project.phase === "done" || project.has_result) return { label: "Review", icon: "rate_review" };
  if (project.phase === "running") return { label: "In progress", icon: "sync" };
  return { label: "Drafting brief", icon: "edit_note" };
}

function buildBriefItems(projects: ProjectSummary[], assets: number, brands: number): BriefItem[] {
  const items: BriefItem[] = projects.slice(0, 3).map((project) => {
    const stage = project.stage ?? "planning";
    const meta = stageMeta[stage] ?? stageMeta.planning;
    const specialist = SPECIALISTS.find((agent) => agent.id === stage) ?? SPECIALISTS[0];
    const title = project.campaign_name || project.name || project.brand || project.id;
    const status = statusFor(project);
    return {
      agent: specialist.name,
      text: `${title} is in ${meta.label.toLowerCase()}.`,
      action: status.label === "Review" ? "Review" : "Continue",
      icon: specialist.icon,
      accent: meta.accent,
      stage: specialist.stage,
    };
  });

  if (assets > 0) {
    items.push({
      agent: "Campaign Agent",
      text: `${assets} content asset${assets === 1 ? "" : "s"} available in the library.`,
      action: "View assets",
      icon: "fact_check",
      accent: STAGE_AGENTS.operations.c1,
      stage: 3,
    });
  }

  if (brands > 0) {
    items.push({
      agent: "Planning Agent",
      text: `${brands} brand${brands === 1 ? "" : "s"} available for campaign planning.`,
      action: "Plan next",
      icon: "track_changes",
      accent: STAGE_AGENTS.planning.c1,
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
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchHome().then(setData).catch((e) => setError(String(e)));
    listProjects().then(setProjects).catch(() => {});
  }, []);

  const dash = data?.dashboard ?? {};
  const totals = dash.totals ?? {};
  const lib = dash.library ?? {};
  const clients = dash.clients ?? [];
  const brands = totals.brands ?? clients.reduce((sum, client) => sum + client.brands.length, 0);
  const visibleProjects = projects.slice(0, 3);
  const activePlans = projects.length;
  const briefItems = useMemo(
    () => buildBriefItems(projects, lib.content_assets ?? 0, brands),
    [brands, lib.content_assets, projects],
  );

  const portfolio = useMemo(
    () => [
      { label: "Brands", value: brands, icon: "business_center", accent: STAGE_AGENTS.planning.c1, tint: "#EEF6FF" },
      { label: "Clients", value: totals.clients ?? clients.length, icon: "groups", accent: STAGE_AGENTS.orchestration.c1, tint: "#ECFDF5" },
      { label: "Active Plans", value: activePlans, icon: "description", accent: STAGE_AGENTS.operations.c1, tint: "#FFF1F5" },
      { label: "Running Campaigns", value: totals.campaigns ?? 0, icon: "campaign", accent: STAGE_AGENTS.reporting.c1, tint: "#FFF3EA" },
      { label: "Content Assets", value: lib.content_assets ?? 0, icon: "folder", accent: STAGE_AGENTS.planning.c1, tint: "#EEF6FF" },
    ],
    [activePlans, brands, clients.length, lib.content_assets, totals.campaigns, totals.clients],
  );

  const startQuick = () => {
    const text = quick.trim();
    setQuick("");
    onStartNew(text || undefined);
  };

  return (
    <Box sx={{ minHeight: "calc(100vh - 56px)", background: "#FBFCFF", color: "#111827" }}>
      <Box
        sx={{
          maxWidth: 1240,
          mx: "auto",
          px: { xs: 2, md: 4 },
          py: { xs: 3, md: 4 },
          display: "flex",
          flexDirection: "column",
          gap: 4,
        }}
      >
        {error && (
          <Typography variant="body2" sx={{ color: "error.main" }}>
            Could not reach /api/home. Is the FastAPI server running? ({error})
          </Typography>
        )}

        <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2 }}>
          <Box>
            <Typography sx={{ fontSize: { xs: 24, md: 32 }, fontWeight: 800, letterSpacing: 0, lineHeight: 1.2 }}>
              Good morning, Shaswata!
            </Typography>
            <Typography sx={{ mt: 1.25, fontSize: 15, color: "#344054" }}>
              What would you like CampAgent to help you accomplish today?
            </Typography>
          </Box>
          <Box
            role="button"
            tabIndex={0}
            onClick={() => onStartNew()}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onStartNew();
              }
            }}
            sx={{
              display: { xs: "none", sm: "inline-flex" },
              alignItems: "center",
              gap: 0.75,
              height: 44,
              px: 2,
              borderRadius: 2,
              color: "#fff",
              fontWeight: 800,
              cursor: "pointer",
              background: `linear-gradient(135deg, ${STAGE_AGENTS.planning.c1}, #0B4DA2)`,
              boxShadow: "0 14px 28px rgba(23, 104, 209, 0.24)",
            }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 20 }}>add</span>
            New
            <span className="material-symbols-outlined" style={{ fontSize: 18 }}>expand_more</span>
          </Box>
        </Box>

        <Box
          sx={{
            borderRadius: 3,
            border: "1px solid rgba(23, 104, 209, 0.32)",
            background: "rgba(255,255,255,0.92)",
            boxShadow: "0 22px 54px rgba(23, 104, 209, 0.12)",
            minHeight: 210,
            p: { xs: 2.25, md: 3 },
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
          }}
        >
          <Box>
            <Typography sx={{ fontSize: 16, fontWeight: 700, color: "#667085" }}>
              Describe what you want to achieve...
            </Typography>
            <Box
              component="textarea"
              value={quick}
              onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setQuick(e.target.value)}
              onKeyDown={(e: React.KeyboardEvent<HTMLTextAreaElement>) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  startQuick();
                }
              }}
              placeholder="Ask anything about your campaigns, plans, assets or performance."
              sx={{
                mt: 1,
                width: "100%",
                minHeight: 76,
                resize: "vertical",
                border: 0,
                outline: 0,
                p: 0,
                fontFamily: tokens.font.primary,
                fontSize: 15,
                lineHeight: 1.6,
                color: "#101828",
                background: "transparent",
                "&::placeholder": { color: "#667085", opacity: 1 },
              }}
            />
          </Box>

          <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2, flexWrap: "wrap" }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, flexWrap: "wrap" }}>
              <Box
                sx={{
                  width: 44,
                  height: 44,
                  borderRadius: "50%",
                  display: "grid",
                  placeItems: "center",
                  background: "#EEF6FF",
                  color: STAGE_AGENTS.planning.c1,
                }}
              >
                <span className="material-symbols-outlined" style={{ fontSize: 23 }}>auto_awesome</span>
              </Box>
              <ActionButton icon="upload_file" label="Import brand plan" onClick={() => document.getElementById("home-brand-plan-input")?.click()} />
            </Box>
            <Box
              role="button"
              tabIndex={0}
              aria-label="Send request"
              onClick={startQuick}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  startQuick();
                }
              }}
              sx={{
                width: 48,
                height: 48,
                borderRadius: "50%",
                display: "grid",
                placeItems: "center",
                cursor: "pointer",
                color: "#fff",
                background: `linear-gradient(135deg, ${STAGE_AGENTS.planning.c1}, #0B4DA2)`,
                boxShadow: "0 12px 26px rgba(23, 104, 209, 0.28)",
              }}
            >
              <span className="material-symbols-outlined" style={{ fontSize: 24 }}>send</span>
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
        </Box>

        <SectionHeader title="Choose a specialist" subtitle="Jump into a conversation with one of our AI agents" />
        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, minmax(0, 1fr))", lg: "repeat(4, minmax(0, 1fr))" }, gap: 2 }}>
          {SPECIALISTS.map((agent) => (
            <SpecialistCard key={agent.id} agent={agent} onOpen={() => onStartNew(undefined, agent.stage)} />
          ))}
        </Box>

        <SectionHeader title="Continue working" subtitle="Pick up where you left off" action="View all campaigns" />
        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "repeat(3, minmax(0, 1fr))" }, gap: 2 }}>
          {visibleProjects.length > 0 ? (
            visibleProjects.map((project, index) => (
              <WorkCard key={project.id} project={project} index={index} onOpen={() => onOpenPlan(project.id)} />
            ))
          ) : (
            <EmptyPanel text="No saved campaign plans yet." />
          )}
        </Box>

        <SectionHeader title="Today's brief" subtitle="Important updates and actions" />
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: { xs: "1fr", md: "repeat(4, minmax(0, 1fr))" },
            gap: 2,
            p: 2,
            borderRadius: 2,
            border: `1px solid ${tokens.color.outline}`,
            background: "#FFFFFF",
            boxShadow: `0 8px 22px ${shade(0.04)}`,
          }}
        >
          {briefItems.length > 0 ? briefItems.map((item) => (
            <Box key={`${item.agent}-${item.text}`} sx={{ display: "grid", gridTemplateColumns: "44px 1fr", gap: 1.5, alignItems: "start" }}>
              <Box sx={{ width: 44, height: 44, borderRadius: "50%", display: "grid", placeItems: "center", color: "#fff", background: item.accent }}>
                <span className="material-symbols-outlined" style={{ fontSize: 22 }}>{item.icon}</span>
              </Box>
              <Box>
                <Typography sx={{ fontSize: 13, fontWeight: 800 }}>{item.agent}</Typography>
                <Typography sx={{ mt: 0.5, fontSize: 12.5, color: "#344054", lineHeight: 1.35 }}>{item.text}</Typography>
                <Typography sx={{ mt: 1.25, fontSize: 12.5, fontWeight: 800, color: item.accent }}>{item.action} &rarr;</Typography>
              </Box>
            </Box>
          )) : (
            <Typography sx={{ gridColumn: "1 / -1", py: 2, textAlign: "center", fontSize: 14, color: "#667085" }}>
              No active updates yet.
            </Typography>
          )}
        </Box>

        <SectionHeader title="Portfolio overview" subtitle="A snapshot of your environment" />
        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, minmax(0, 1fr))", lg: "repeat(5, minmax(0, 1fr))" }, gap: 2 }}>
          {portfolio.map((item) => (
            <Box key={item.label} sx={{ p: 2, minHeight: 126, borderRadius: 2, border: `1px solid ${tokens.color.outline}`, background: "#fff", display: "flex", alignItems: "center", gap: 2 }}>
              <Box sx={{ width: 52, height: 52, borderRadius: "50%", display: "grid", placeItems: "center", color: item.accent, background: item.tint }}>
                <span className="material-symbols-outlined" style={{ fontSize: 24 }}>{item.icon}</span>
              </Box>
              <Box>
                <Typography sx={{ fontSize: 28, fontWeight: 800, lineHeight: 1 }}>{item.value}</Typography>
                <Typography sx={{ mt: 0.75, fontSize: 12.5, color: "#344054" }}>{item.label}</Typography>
              </Box>
            </Box>
          ))}
        </Box>
      </Box>
    </Box>
  );
}

function ActionButton({ icon, label, onClick }: { icon: string; label: string; onClick: () => void }) {
  return (
    <Box
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick();
        }
      }}
      sx={{
        display: "inline-flex",
        alignItems: "center",
        gap: 0.75,
        minHeight: 38,
        px: 1.5,
        borderRadius: 1.5,
        border: `1px solid ${tokens.color.outline}`,
        background: "#fff",
        cursor: "pointer",
        fontSize: 13,
        fontWeight: 800,
        color: "#253858",
        whiteSpace: "nowrap",
        "&:hover": { borderColor: "#B8C0CC", background: "#F8FAFC" },
      }}
    >
      <span className="material-symbols-outlined" style={{ fontSize: 18 }}>{icon}</span>
      {label}
    </Box>
  );
}

function SectionHeader({ title, subtitle, action }: { title: string; subtitle: string; action?: string }) {
  return (
    <Box sx={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 2, mt: 1 }}>
      <Box>
        <Typography sx={{ fontSize: 22, fontWeight: 800, lineHeight: 1.15 }}>{title}</Typography>
        <Typography sx={{ mt: 0.75, fontSize: 14, color: "#475467" }}>{subtitle}</Typography>
      </Box>
      {action && (
        <Box sx={{ display: { xs: "none", sm: "inline-flex" }, alignItems: "center", gap: 0.5, px: 1.5, height: 42, borderRadius: 1.5, border: `1px solid ${tokens.color.outline}`, background: "#fff", color: "#253858", fontSize: 13.5, fontWeight: 800 }}>
          {action}
          <span className="material-symbols-outlined" style={{ fontSize: 18 }}>chevron_right</span>
        </Box>
      )}
    </Box>
  );
}

function EmptyPanel({ text }: { text: string }) {
  return (
    <Box sx={{ gridColumn: "1 / -1", p: 4, borderRadius: 2, border: `1px dashed ${tokens.color.outline}`, background: "#fff", textAlign: "center" }}>
      <Typography sx={{ fontSize: 14, color: "#667085" }}>{text}</Typography>
    </Box>
  );
}

function SpecialistCard({ agent, onOpen }: { agent: Specialist; onOpen: () => void }) {
  const image = STAGE_AGENTS[agent.id].photo;
  return (
    <Box
      sx={{
        minHeight: 360,
        borderRadius: 2,
        overflow: "hidden",
        border: `1px solid ${agent.accent}55`,
        background: "#FFFFFF",
        boxShadow: `0 12px 24px ${agent.accent}12`,
      }}
    >
      <Box sx={{ position: "relative", height: 158, background: `linear-gradient(135deg, ${agent.tint}, #FFFFFF)` }}>
        <Box sx={{ position: "absolute", top: 20, left: 20, width: 48, height: 48, borderRadius: 2, display: "grid", placeItems: "center", color: agent.accent, background: "#fff", boxShadow: `0 10px 22px ${agent.accent}1F` }}>
          <span className="material-symbols-outlined" style={{ fontSize: 24 }}>{agent.icon}</span>
        </Box>
        <Box component="img" src={image} alt="" sx={{ position: "absolute", right: 10, bottom: -6, height: 145, maxWidth: "75%", objectFit: "contain" }} />
      </Box>
      <Box sx={{ p: 2, display: "flex", flexDirection: "column", gap: 1.25 }}>
        <Typography sx={{ fontSize: 17, fontWeight: 800 }}>{agent.name}</Typography>
        <Typography sx={{ minHeight: 62, fontSize: 14, color: "#475467", lineHeight: 1.45 }}>{agent.description}</Typography>
        <Box
          role="button"
          tabIndex={0}
          onClick={onOpen}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              onOpen();
            }
          }}
          sx={{
            mt: 0.5,
            height: 44,
            borderRadius: 1.5,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 1,
            border: `1px solid ${agent.accent}44`,
            color: agent.accentDark,
            background: `${agent.tint}AA`,
            fontSize: 13.5,
            fontWeight: 800,
            cursor: "pointer",
          }}
        >
          Open chat
          <span className="material-symbols-outlined" style={{ fontSize: 18 }}>arrow_forward</span>
        </Box>
      </Box>
    </Box>
  );
}

function WorkCard({ project, index, onOpen }: { project: ProjectSummary; index: number; onOpen: () => void }) {
  const stage = stageMeta[project.stage ?? "planning"] ?? stageMeta.planning;
  const progress = progressFor(project, index);
  const status = statusFor(project);
  const title = project.campaign_name || project.name || `CMP-${String(index + 1).padStart(4, "0")}`;
  const objective = project.objective || project.brand || "Campaign work in progress";

  return (
    <Box sx={{ p: 2, minHeight: 214, borderRadius: 2, border: `1px solid ${tokens.color.outline}`, background: "#fff", boxShadow: `0 8px 22px ${shade(0.04)}` }}>
      <Box sx={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 1.5 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, minWidth: 0 }}>
          <Box sx={{ width: 44, height: 44, borderRadius: "50%", display: "grid", placeItems: "center", background: stage.tint, color: stage.accent, fontWeight: 900 }}>C</Box>
          <Box sx={{ minWidth: 0 }}>
            <Typography sx={{ fontSize: 16, fontWeight: 800, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{title}</Typography>
            <Box sx={{ display: "inline-flex", mt: 0.75, px: 1, py: 0.4, borderRadius: 1, background: stage.tint, color: stage.accent, fontSize: 11.5, fontWeight: 800 }}>
              {stage.label}
            </Box>
          </Box>
        </Box>
        <span className="material-symbols-outlined" style={{ fontSize: 21, color: "#344054" }}>more_vert</span>
      </Box>
      <Box sx={{ mt: 2.5, display: "flex", justifyContent: "flex-end" }}>
        <Box sx={{ display: "inline-flex", alignItems: "center", gap: 0.4, px: 1, py: 0.45, borderRadius: 1, background: status.label === "In progress" ? "#ECFDF5" : stage.tint, color: status.label === "In progress" ? "#047857" : stage.accent, fontSize: 11.5, fontWeight: 800 }}>
          <span className="material-symbols-outlined" style={{ fontSize: 14 }}>{status.icon}</span>
          {status.label}
        </Box>
      </Box>
      <Box sx={{ mt: 2.5, display: "grid", gridTemplateColumns: "1fr auto", gap: 1.5, alignItems: "center" }}>
        <Box sx={{ height: 6, borderRadius: 999, background: "#EAECF0", overflow: "hidden" }}>
          <Box sx={{ width: `${progress}%`, height: "100%", borderRadius: 999, background: stage.accent }} />
        </Box>
        <Typography sx={{ fontSize: 12, fontWeight: 800, color: "#344054" }}>{progress}%</Typography>
      </Box>
      <Typography sx={{ mt: 1.5, fontSize: 13, color: "#344054" }}>{objective}</Typography>
      <Box sx={{ mt: 2.5, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 1.5 }}>
        <Box sx={{ display: "inline-flex", alignItems: "center", gap: 0.75, color: "#667085", fontSize: 12 }}>
          <span className="material-symbols-outlined" style={{ fontSize: 17 }}>calendar_today</span>
          {project.updated_at ? `Updated ${new Date(project.updated_at).toLocaleDateString()}` : "Updated"}
        </Box>
        <Box role="button" tabIndex={0} onClick={onOpen} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onOpen(); } }} sx={{ height: 38, px: 1.5, borderRadius: 1.5, display: "inline-flex", alignItems: "center", gap: 0.75, border: `1px solid ${stage.accent}33`, color: stage.accent, fontSize: 13, fontWeight: 800, cursor: "pointer" }}>
          Continue
          <span className="material-symbols-outlined" style={{ fontSize: 18 }}>arrow_forward</span>
        </Box>
      </Box>
    </Box>
  );
}
