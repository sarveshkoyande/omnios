import { useState } from "react";
import AppBar from "@mui/material/AppBar";
import Box from "@mui/material/Box";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import { Library } from "./library/Library";
import { Artefacts } from "./views/Artefacts";
import { Home } from "./views/Home";
import { PromptLibrary } from "./views/PromptLibrary";
import { Workspace } from "./workspace/Workspace";
import { tokens } from "./theme/tokens";

// "planning-v2" retired 2026-07-19: the planning_v2 engine now powers the Workspace
// Planning & Strategy stage (decision spine + Campaign Strategy/Brief artifacts); the
// separate surface is gone. Backend engine survives in strategy/planning_v2/.
// "prompts" added 2026-07-28: TEMPORARY tab to browse the app's LLM system prompts
// (strategy/prompt_library.py) -- remove the nav entry below (and this view) once no
// longer needed; the backend endpoint is harmless to leave either way.
type View = "home" | "workspace" | "library" | "artefacts" | "prompts";
type WorkspaceStartMode = "flow" | "direct";

const NavList = styled("ul")({
  display: "flex",
  alignItems: "center",
  gap: 4,
  listStyle: "none",
  margin: 0,
  padding: 0,
});

const NavItem = styled("li")<{ active?: boolean }>(({ active }) => ({
  display: "inline-flex",
  alignItems: "center",
  gap: 7,
  color: active ? "#FFFFFF" : "rgba(255,255,255,0.72)",
  fontSize: tokens.fontSize.sm,
  fontWeight: active ? 700 : 600,
  cursor: "pointer",
  padding: "7px 16px",
  borderRadius: tokens.radius.pill,
  background: active ? "rgba(255,255,255,0.18)" : "transparent",
  boxShadow: active ? "inset 0 0 0 1px rgba(255,255,255,0.28)" : "none",
  transition: "color 160ms ease, background 160ms ease",
  "& .material-symbols-outlined": { fontSize: 19 },
  "&:hover": { color: "#FFFFFF", background: active ? "rgba(255,255,255,0.18)" : "rgba(255,255,255,0.12)" },
  "&:focus-visible": { outline: "2px solid #fff", outlineOffset: 3, borderRadius: tokens.radius.pill },
}));

// The Cockpit frames one project's Campaign Plan workspace at /campaign-plan-view
// ?project=<id>&embed=1 (hierarchy plan KTD10): open it straight away, without this app's chrome.
const launch = new URLSearchParams(window.location.search);
const EMBED_PROJECT = launch.get("embed") === "1" ? launch.get("project") : null;

export default function App() {
  const [view, setView] = useState<View>(EMBED_PROJECT ? "workspace" : "home");
  const [prefillBrand, setPrefillBrand] = useState<string | null>(null);
  const [openProjectId, setOpenProjectId] = useState<string | null>(EMBED_PROJECT);
  const [seedMessage, setSeedMessage] = useState<string | null>(null);
  const [seedFile, setSeedFile] = useState<File | null>(null);
  const [initialWorkspaceStage, setInitialWorkspaceStage] = useState(1);
  const [workspaceStartMode, setWorkspaceStartMode] = useState<WorkspaceStartMode>("direct");
  // The top bar is Omni blue in every view and every stage — it is the one thing on screen that
  // says "you are in Omni OS". It used to wear the active stage's colour, which made moving from
  // Planning to Reporting read as switching applications. Stage identity now lives in the marker
  // slots (theme/stageTheme.ts), never in the chrome.

  // Open an existing plan straight from a Home card.
  const goOpenPlan = (id: string) => {
    setPrefillBrand(null);
    setSeedMessage(null);
    setSeedFile(null);
    setInitialWorkspaceStage(1);
    setWorkspaceStartMode("direct");
    setOpenProjectId(id);
    setView("workspace");
  };

  // Start a fresh plan — lands directly on the briefing intake (optionally seeded
  // with a one-line requirement typed on Home). No "click to begin" gate.
  const goStartNew = (seed?: string, initialStage = 1, mode: WorkspaceStartMode = "flow") => {
    setPrefillBrand(null);
    setOpenProjectId(null);
    setSeedFile(null);
    setSeedMessage(seed ?? null);
    setInitialWorkspaceStage(initialStage);
    setWorkspaceStartMode(mode);
    setView("workspace");
  };

  // Import a brand plan straight from Home — fresh plan that uploads the file on entry.
  const goImportFile = (file: File) => {
    setPrefillBrand(null);
    setOpenProjectId(null);
    setSeedMessage(null);
    setSeedFile(file);
    setInitialWorkspaceStage(1);
    setWorkspaceStartMode("flow");
    setView("workspace");
  };

  if (EMBED_PROJECT) {
    return (
      <Box sx={{ position: "relative", zIndex: 1 }}>
        <Workspace openProjectId={EMBED_PROJECT} initialStage={1} startMode="direct" chromeHeight={0} />
      </Box>
    );
  }

  return (
    <>
      <Box sx={{ position: "relative", zIndex: 1 }}>
        <AppBar position="sticky" sx={{ backgroundColor: tokens.color.primary }}>
          {/* Pinned at both breakpoints: a bare `minHeight` loses to MuiToolbar's own
              `@media (min-width:600px)` rule, which is how the bar ended up 64px tall
              while the workspace below was sized as if it were 56px. */}
          <Toolbar sx={{ gap: 1.5, minHeight: { xs: tokens.layout.topBarHeight, sm: tokens.layout.topBarHeight } }}>
            <span className="material-symbols-outlined" style={{ fontSize: 26, color: "#fff" }}>
              hub
            </span>
            <Typography component="span" sx={{ fontSize: tokens.fontSize.xl, fontWeight: 700, color: "#fff", letterSpacing: "-0.01em" }}>
              Omni OS
            </Typography>
            <Typography component="span" sx={{ color: "#FFFFFF", fontSize: tokens.fontSize.md, mr: 2 }}>
              · Omnichannel Activation
            </Typography>
            <NavList>
              {([
                { key: "home", label: "Home", icon: "home", onSelect: () => setView("home") },
                { key: "workspace", label: "Workspace", icon: "space_dashboard", onSelect: () => goStartNew(undefined, 1, "direct") },
                // "Artefacts" tab hidden 2026-07-27 (per request). The <Artefacts /> view and its
                // /api/pharma-intel routes still exist and render if `view` is set to "artefacts"
                // some other way, but it's no longer reachable from the nav.
                // "Prompt Library" added 2026-07-28, TEMPORARY -- remove this entry (and the
                // "prompts" View case below) once no longer needed.
                { key: "prompts", label: "Prompt Library", icon: "psychology", onSelect: () => setView("prompts") },
              ] as const).map((item) => (
                <NavItem
                  key={item.key}
                  active={view === item.key}
                  role="button"
                  tabIndex={0}
                  aria-current={view === item.key ? "page" : undefined}
                  onClick={item.onSelect}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); item.onSelect(); }
                  }}
                >
                  <span className="material-symbols-outlined">{item.icon}</span>
                  {item.label}
                </NavItem>
              ))}
            </NavList>
            <Box sx={{ flex: 1 }} />
            <Box
              sx={{
                display: "inline-flex",
                alignItems: "center",
                gap: 1,
                minWidth: 0,
                color: "#FFFFFF",
                fontSize: tokens.fontSize.sm,
                fontWeight: 700,
              }}
            >
              <Box
                sx={{
                  width: 30,
                  height: 30,
                  borderRadius: "50%",
                  display: "grid",
                  placeItems: "center",
                  background: "rgba(255,255,255,0.18)",
                  boxShadow: "inset 0 0 0 1px rgba(255,255,255,0.28)",
                }}
              >
                <span className="material-symbols-outlined" style={{ fontSize: 18 }}>
                  person
                </span>
              </Box>
              <Typography component="span" sx={{ display: { xs: "none", sm: "inline" }, color: "#FFFFFF", fontSize: tokens.fontSize.sm, fontWeight: 700 }}>
                Shaswata
              </Typography>
            </Box>
          </Toolbar>
        </AppBar>
        {view === "home" && <Home onOpenPlan={goOpenPlan} onStartNew={goStartNew} onImportFile={goImportFile} />}
        {view === "workspace" && <Workspace prefillBrand={prefillBrand} openProjectId={openProjectId} seedMessage={seedMessage} seedFile={seedFile} initialStage={initialWorkspaceStage} startMode={workspaceStartMode} />}
        {view === "library" && <Library />}
        {view === "artefacts" && <Artefacts />}
        {view === "prompts" && <PromptLibrary />}
      </Box>
    </>
  );
}
