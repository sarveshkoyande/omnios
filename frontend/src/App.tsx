import { useState } from "react";
import AppBar from "@mui/material/AppBar";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import { Library } from "./library/Library";
import { Home } from "./views/Home";
import { Workspace } from "./workspace/Workspace";
import { Atmosphere } from "./theme/Atmosphere";
import { tokens } from "./theme/tokens";

type View = "home" | "workspace" | "library";

/**
 * Shell — the gradient app bar is the ONE saturated moment. Nav items are
 * transparent-text-on-gradient; the active item is a white pill with indigo
 * text. Right side carries translucent white status pills.
 */
const NavItem = styled(Button)(() => ({
  color: "rgba(255,255,255,0.86)",
  background: "transparent",
  border: "none",
  boxShadow: "none",
  borderRadius: tokens.radius.pill,
  padding: "6px 16px",
  fontWeight: 600,
  "&:hover": { background: "rgba(255,255,255,0.14)", color: "#fff", boxShadow: "none", transform: "none" },
  "&.Mui-focusVisible": { outline: "2px solid #fff", outlineOffset: 2 },
  "&.active": {
    background: "#fff",
    color: tokens.color.primary,
    boxShadow: "0 2px 8px rgba(30,27,51,0.18)",
    cursor: "default",
  },
}));

const StatusPill = styled("span")({
  display: "inline-flex",
  alignItems: "center",
  gap: 8,
  padding: "6px 14px",
  borderRadius: tokens.radius.pill,
  background: "rgba(255,255,255,0.22)",
  border: "1px solid rgba(255,255,255,0.45)",
  color: "#fff",
  fontSize: tokens.fontSize.xs,
  fontWeight: 600,
  lineHeight: 1,
});

const GreenDot = styled("span")({
  width: 8,
  height: 8,
  borderRadius: "50%",
  background: tokens.color.success,
  boxShadow: `0 0 6px ${tokens.color.success}`,
});

export default function App() {
  const [view, setView] = useState<View>("home");
  const [prefillBrand, setPrefillBrand] = useState<string | null>(null);

  const goWorkspace = (brand?: string) => {
    setPrefillBrand(brand ?? null);
    setView("workspace");
  };

  return (
    <>
      <Atmosphere />
      <Box sx={{ position: "relative", zIndex: 1 }}>
        <AppBar position="sticky">
          <Toolbar sx={{ gap: 1.5, minHeight: 56 }}>
            <span className="material-symbols-outlined" style={{ fontSize: 26, color: "#fff" }}>
              hub
            </span>
            <Typography component="span" sx={{ fontSize: tokens.fontSize.xl, fontWeight: 700, color: "#fff", letterSpacing: "-0.01em" }}>
              Omni OS
            </Typography>
            <Typography component="span" sx={{ color: "rgba(255,255,255,0.88)", fontSize: tokens.fontSize.md, mr: 2 }}>
              · Omnichannel Activation
            </Typography>
            <NavItem
              className={view === "home" ? "active" : ""}
              onClick={() => setView("home")}
              startIcon={<span className="material-symbols-outlined" style={{ fontSize: 18 }}>grid_view</span>}
            >
              Home
            </NavItem>
            <NavItem
              className={view === "workspace" ? "active" : ""}
              onClick={() => goWorkspace()}
              startIcon={<span className="material-symbols-outlined" style={{ fontSize: 18 }}>edit_note</span>}
            >
              Workspace
            </NavItem>
            <NavItem
              className={view === "library" ? "active" : ""}
              onClick={() => setView("library")}
              startIcon={<span className="material-symbols-outlined" style={{ fontSize: 18 }}>menu_book</span>}
            >
              Claims Library
            </NavItem>
            <Box sx={{ flex: 1 }} />
            <StatusPill>
              <span className="material-symbols-outlined" style={{ fontSize: 14, color: "#fff" }}>
                radio_button_unchecked
              </span>
              chat: rules
            </StatusPill>
            <StatusPill>
              <GreenDot />
              agents online
            </StatusPill>
          </Toolbar>
        </AppBar>
        {view === "home" && <Home onPlanBrand={(brand) => goWorkspace(brand)} onStartProject={() => goWorkspace()} />}
        {view === "workspace" && <Workspace prefillBrand={prefillBrand} />}
        {view === "library" && <Library />}
      </Box>
    </>
  );
}
