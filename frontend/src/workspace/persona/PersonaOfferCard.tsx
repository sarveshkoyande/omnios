import { useState } from "react";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Checkbox from "@mui/material/Checkbox";
import Chip from "@mui/material/Chip";
import IconButton from "@mui/material/IconButton";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import { AgentBubble } from "../ChatBubble";
import { PersonaAvatar } from "./PersonaAvatar";
import type { PersonaOffer, PersonaSummary } from "../types";
import { indigoTint } from "../../theme/tokens";

const Row = styled("label")<{ checked: boolean }>(({ theme, checked }) => ({
  display: "flex",
  alignItems: "center",
  gap: theme.spacing(2),
  padding: theme.spacing(1.5, 2),
  borderRadius: 10,
  border: `1px solid ${checked ? indigoTint(0.3) : indigoTint(0.12)}`,
  marginBottom: theme.spacing(1),
  cursor: "pointer",
  background: checked ? indigoTint(0.08) : "rgba(255,255,255,0.4)",
}));

export function PersonaOfferCard({
  offer,
  onRun,
  onSkip,
  onOpenProfile,
}: {
  offer: PersonaOffer;
  onRun: (ids: string[]) => void;
  onSkip: () => void;
  onOpenProfile: (id: string) => void;
}) {
  const matchedIds = new Set(offer.matched.map((p) => p.id));
  const all: PersonaSummary[] = [...offer.matched, ...offer.others];
  const [selected, setSelected] = useState<Set<string>>(new Set(offer.matched.map((p) => p.id)));
  const [running, setRunning] = useState(false);

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <AgentBubble sx={{ maxWidth: 640 }}>
      <Typography sx={{ fontWeight: 700, mb: 0.5 }}>Pressure-test this plan with synthetic personas?</Typography>
      <Typography variant="body2" sx={{ color: "text.secondary", mb: 2 }}>
        I can run the plan past prescribers from your target audience — they'll react honestly and tell
        you what's missing and what would make them engage. The ones matching this plan's specialty are
        pre-selected; pick (or deselect) who should review it:
      </Typography>
      <Box>
        {all.map((p) => (
          <Row key={p.id} checked={selected.has(p.id)}>
            <Checkbox size="small" checked={selected.has(p.id)} onChange={() => toggle(p.id)} sx={{ p: 0 }} />
            <PersonaAvatar name={p.name} />
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography sx={{ fontWeight: 700, fontSize: 13 }}>
                {p.name}
                {matchedIds.has(p.id) && <Chip size="small" label="match" sx={{ ml: 1, height: 16, fontSize: 9 }} />}
              </Typography>
              <Typography variant="caption" sx={{ color: "text.secondary" }}>
                {p.who} · {p.age ? `${p.age} · ` : ""}{p.segment_name}
              </Typography>
            </Box>
            <IconButton
              size="small"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onOpenProfile(p.id);
              }}
              title="View full persona profile"
            >
              <span className="material-symbols-outlined" style={{ fontSize: 18 }}>info</span>
            </IconButton>
          </Row>
        ))}
      </Box>
      <Box sx={{ display: "flex", gap: 2, mt: 2, alignItems: "center" }}>
        <Button
          variant="contained"
          color="primary"
          disabled={selected.size === 0 || running}
          onClick={() => {
            setRunning(true);
            onRun([...selected]);
          }}
        >
          {running ? `Running… asking ${selected.size} persona${selected.size > 1 ? "s" : ""}` : "Run persona review"}
        </Button>
        <Button variant="text" onClick={onSkip} disabled={running}>
          Not now
        </Button>
      </Box>
    </AgentBubble>
  );
}
