import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { AgentAvatar } from "../Avatar";
import { STAGE_AGENTS, type StageAgentId } from "../types";
import { tokens, indigoTint } from "../../theme/tokens";

export function StageHead({ icon, title, blurb, agent }: { icon: string; title: string; blurb: string; agent?: StageAgentId }) {
  return (
    <Box sx={{ display: "flex", gap: 2, alignItems: "flex-start", mb: 4 }}>
      <span className="material-symbols-outlined" style={{ fontSize: 26, color: tokens.color.primary }}>{icon}</span>
      <Box sx={{ flex: 1 }}>
        <Typography variant="h2" sx={{ fontSize: tokens.fontSize.lg }}>{title}</Typography>
        <Typography variant="body2" sx={{ color: "text.secondary", mt: 0.5 }}>{blurb}</Typography>
      </Box>
      {agent && (
        <Box
          sx={{
            display: "flex", alignItems: "center", gap: 1, flex: "0 0 auto", alignSelf: "center",
            border: `1px solid ${indigoTint(0.14)}`, borderRadius: tokens.radius.pill, pl: 0.5, pr: 1.5, py: 0.5,
          }}
        >
          <AgentAvatar id={agent} size={24} />
          <Box>
            <Typography sx={{ fontSize: 9, color: "text.secondary", letterSpacing: "0.04em", textTransform: "uppercase", lineHeight: 1.2 }}>
              Prepared by
            </Typography>
            <Typography sx={{ fontSize: 11, fontWeight: 700, lineHeight: 1.2 }}>{STAGE_AGENTS[agent].name}</Typography>
          </Box>
        </Box>
      )}
    </Box>
  );
}
