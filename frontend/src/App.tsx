import { useState } from "react";
import AppBar from "@mui/material/AppBar";
import Box from "@mui/material/Box";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import { Library } from "./library/Library";
import { Artefacts } from "./views/Artefacts";
import { Home } from "./views/Home";
import { Workspace } from "./workspace/Workspace";
import { tokens } from "./theme/tokens";

// "planning-v2" retired 2026-07-19: the planning_v2 engine now powers the Workspace
// Planning & Strategy stage (decision spine + Campaign Strategy/Brief artifacts); the
// separate surface is gone. Backend engine survives in strategy/planning_v2/.
type View = "home" | "workspace" | "library" | "artefacts";

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

export default function App() {
  const [view, setView] = useState<View>("home");
  const [prefillBrand, setPrefillBrand] = useState<string | null>(null);
  const [openProjectId, setOpenProjectId] = useState<string | null>(null);
  const [seedMessage, setSeedMessage] = useState<string | null>(null);
  const [seedFile, setSeedFile] = useState<File | null>(null);

  // Open an existing plan straight from a Home card.
  const goOpenPlan = (id: string) => {
    setPrefillBrand(null);
    setSeedMessage(null);
    setSeedFile(null);
    setOpenProjectId(id);
    setView("workspace");
  };

  // Start a fresh plan — lands directly on the briefing intake (optionally seeded
  // with a one-line requirement typed on Home). No "click to begin" gate.
  const goStartNew = (seed?: string) => {
    setPrefillBrand(null);
    setOpenProjectId(null);
    setSeedFile(null);
    setSeedMessage(seed ?? null);
    setView("workspace");
  };

  // Import a brand plan straight from Home — fresh plan that uploads the file on entry.
  const goImportFile = (file: File) => {
    setPrefillBrand(null);
    setOpenProjectId(null);
    setSeedMessage(null);
    setSeedFile(file);
    setView("workspace");
  };

  return (
    <>
      <Box sx={{ position: "relative", zIndex: 1 }}>
        <AppBar position="sticky">
          <Toolbar sx={{ gap: 1.5, minHeight: 56 }}>
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
                { key: "workspace", label: "Workspace", icon: "space_dashboard", onSelect: () => goStartNew() },
                { key: "artefacts", label: "Artefacts", icon: "folder_open", onSelect: () => setView("artefacts") },
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
          </Toolbar>
        </AppBar>
        {view === "home" && <Home onOpenPlan={goOpenPlan} onStartNew={goStartNew} onImportFile={goImportFile} />}
        {view === "workspace" && <Workspace prefillBrand={prefillBrand} openProjectId={openProjectId} seedMessage={seedMessage} seedFile={seedFile} />}
        {view === "library" && <Library />}
        {view === "artefacts" && <Artefacts />}
      </Box>
    </>
  );
}
