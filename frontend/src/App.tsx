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
import { tokens, shade, light, pressedShadow } from "./theme/tokens";

type View = "home" | "workspace" | "library";

/**
 * Shell — a brushed-steel console header. Nav keys are physical toggles: the
 * active view's key sits pressed INTO the panel (inset + 1px down), inactive
 * keys sit raised.
 */
const NavKey = styled(Button)(() => ({
  "&.active": {
    boxShadow: pressedShadow,
    transform: "translateY(1px)",
    background: `linear-gradient(180deg, ${shade(0.1)}, ${light(0.2)}), ${tokens.color.surface}`,
    cursor: "default",
  },
}));

const StatusLed = styled("span")(({ theme }) => ({
  display: "inline-flex",
  alignItems: "center",
  gap: theme.spacing(2),
  fontFamily: tokens.font.mono,
  fontSize: tokens.fontSize.xs,
  color: shade(0.7),
  "&::before": {
    content: '""',
    width: 8,
    height: 8,
    borderRadius: "50%",
    background: tokens.color.success,
    boxShadow: `0 0 5px ${tokens.color.success}, inset 0 1px 1px ${light(0.6)}`,
  },
}));

export default function App() {
  const [view, setView] = useState<View>("home");
  const [prefillBrand, setPrefillBrand] = useState<string | null>(null);

  const goWorkspace = (brand?: string) => {
    setPrefillBrand(brand ?? null);
    setView("workspace");
  };

  return (
    <>
      <AppBar position="sticky">
        <Toolbar sx={{ gap: 3, minHeight: 56 }}>
          <Typography
            variant="h2"
            component="span"
            sx={{ fontSize: tokens.fontSize.lg, letterSpacing: "0.04em", textShadow: `0 1px 0 ${light(0.9)}` }}
          >
            OMNI OS
          </Typography>
          <Typography variant="caption" sx={{ color: "text.secondary", mr: 2 }}>
            Omnichannel Activation
          </Typography>
          <NavKey variant="outlined" size="small" className={view === "home" ? "active" : ""} onClick={() => setView("home")}>
            Home
          </NavKey>
          <NavKey variant="outlined" size="small" className={view === "workspace" ? "active" : ""} onClick={() => goWorkspace()}>
            Workspace
          </NavKey>
          <NavKey variant="outlined" size="small" className={view === "library" ? "active" : ""} onClick={() => setView("library")}>
            Claims Library
          </NavKey>
          <Box sx={{ flex: 1 }} />
          <StatusLed>agents online</StatusLed>
        </Toolbar>
      </AppBar>
      {view === "home" && <Home onPlanBrand={(brand) => goWorkspace(brand)} onStartProject={() => goWorkspace()} />}
      {view === "workspace" && <Workspace prefillBrand={prefillBrand} />}
      {view === "library" && <Library />}
    </>
  );
}
