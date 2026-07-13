import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import LinearProgress from "@mui/material/LinearProgress";
import Typography from "@mui/material/Typography";
import { ConsolePanel } from "./ConsolePanel";
import { InsetTextField } from "./InsetTextField";
import { TactileButton, KeycapSublabel } from "./TactileButton";
import { pressedShadow, raisedShadowHover, focusRing } from "../theme/tokens";

/**
 * Design-system reference: every interactive component in its explicit states.
 * Live samples respond to real hover/tab/press; the "forced" column pins each
 * state with one-off sx (the correct layer for demo-only overrides) so states
 * are reviewable without interaction.
 */
const Row = ({ label, children }: { label: string; children: React.ReactNode }) => (
  <Box sx={{ display: "flex", alignItems: "center", gap: 3, flexWrap: "wrap" }}>
    <Typography variant="overline" sx={{ width: 96, flexShrink: 0 }}>{label}</Typography>
    {children}
  </Box>
);

export function StatesShowcase() {
  return (
    <ConsolePanel title="Design system — component states (hover, tab and press the live samples)">
      <Box sx={{ display: "flex", flexDirection: "column", gap: 4 }}>
        <Row label="Default">
          <Button variant="contained">Primary key</Button>
          <Button variant="contained" color="secondary">Secondary</Button>
          <Button variant="outlined">Aluminium</Button>
          <Button variant="text">Engraved</Button>
          <Chip size="small" color="success" label="Growth" />
        </Row>
        <Row label="Hover">
          <Button variant="contained" sx={{ boxShadow: raisedShadowHover, transform: "translateY(-1px)" }}>
            Lifted +1px
          </Button>
        </Row>
        <Row label="Focus">
          <Button variant="contained" sx={{ ...focusRing }}>2px ring, 2px offset</Button>
        </Row>
        <Row label="Active">
          <Button variant="contained" sx={{ boxShadow: pressedShadow, transform: "translateY(1px)" }}>
            Depressed −travel
          </Button>
        </Row>
        <Row label="Disabled">
          <Button variant="contained" disabled>Unplugged</Button>
        </Row>
        <Row label="Inputs">
          <InsetTextField size="small" label="Search well" defaultValue="oncology" />
          <InsetTextField size="small" label="Disabled" disabled defaultValue="—" />
          <InsetTextField size="small" label="Error" error defaultValue="bad value" />
        </Row>
        <Row label="Hero key">
          <TactileButton variant="contained">
            <span>
              Start new project
              <KeycapSublabel>PLAN → ORCHESTRATE → RUN → REPORT</KeycapSublabel>
            </span>
          </TactileButton>
        </Row>
        <Row label="Meter">
          <Box sx={{ width: 240 }}><LinearProgress variant="determinate" value={31} /></Box>
        </Row>
      </Box>
    </ConsolePanel>
  );
}
