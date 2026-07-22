import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { keyframes } from "@emotion/react";
import { styled } from "@mui/material/styles";
import { AgentAvatar } from "./Avatar";
import { STAGE_AGENTS } from "./types";
import { tokens, shade, indigoTint } from "../theme/tokens";

// One agent, one card. It still does its work as several internal steps server-side
// (see STAGE_AGENTS in types.ts) but there is exactly one identity to show here — no
// badge rail, no per-step cards.

export interface AgentEntry {
  id: string;
  name: string;
  role?: string;
  status: "standby" | "running" | "done";
  summary?: string;
  detail?: { bullets: string[] };
}

const pulse = keyframes`
  0% { box-shadow: 0 0 0 0 currentColor; }
  70% { box-shadow: 0 0 0 6px transparent; }
  100% { box-shadow: 0 0 0 0 transparent; }
`;

const StatusLight = styled("i")<{ status: AgentEntry["status"] }>(({ status }) => ({
  position: "absolute",
  right: -1,
  bottom: -1,
  width: 12,
  height: 12,
  borderRadius: "50%",
  border: `2px solid ${tokens.color.surface}`,
  background: status === "running" ? tokens.color.secondary : status === "done" ? tokens.color.success : shade(0.3),
  color: status === "running" ? tokens.color.secondary : "transparent",
  animation: status === "running" ? `${pulse} 1.4s infinite` : "none",
}));

const shimmerMove = keyframes`
  0% { background-position: 100% 0; }
  100% { background-position: 0 0; }
`;

const Shimmer = styled("div")({
  height: 3,
  borderRadius: 3,
  marginTop: 10,
  backgroundImage: `linear-gradient(90deg, ${shade(0.06)} 25%, ${tokens.color.secondary} 37%, ${shade(0.06)} 63%)`,
  backgroundSize: "400% 100%",
  animation: `${shimmerMove} 1.3s ease infinite`,
});

function StatusDot({ status }: { status: AgentEntry["status"] }) {
  const color = status === "running" ? tokens.color.secondary : status === "done" ? tokens.color.success : shade(0.25);
  return <Box component="span" sx={{ width: 8, height: 8, borderRadius: "50%", background: color, flex: "0 0 auto" }} />;
}

export function AgentTeamPanel({ agents, caption }: { agents: AgentEntry[]; caption: string }) {
  const agent = agents[0];
  // No placeholder: parents hide the whole panel until there is an agent to show.
  if (!agent) return null;
  return (
    <Box
      sx={{
        display: "flex", gap: 2.5, alignItems: "flex-start", p: 3,
        background: agent.status === "running" ? indigoTint(0.06) : indigoTint(0.03),
        border: `1px solid ${indigoTint(0.12)}`, borderRadius: tokens.radius.md,
      }}
    >
      <Box sx={{ position: "relative", flex: "0 0 auto" }}>
        <AgentAvatar id={STAGE_AGENTS.planning.id} size={46} />
        <StatusLight status={agent.status} />
      </Box>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <Typography variant="subtitle1" sx={{ fontSize: tokens.fontSize.sm, fontWeight: 700 }}>
            {STAGE_AGENTS.planning.name}
          </Typography>
          <StatusDot status={agent.status} />
        </Box>
        <Typography
          variant="body2"
          dangerouslySetInnerHTML={{
            __html:
              agent.status === "standby"
                ? "Standing by"
                : agent.status === "running"
                  ? caption
                  : agent.summary || caption,
          }}
          sx={{ color: agent.status === "running" ? "secondary.main" : "text.secondary", mt: 0.5, fontStyle: agent.status === "running" ? "italic" : "normal" }}
        />
        {agent.status === "running" && <Shimmer />}
        {agent.status === "done" && agent.detail?.bullets?.length ? (
          <Box component="details" sx={{ mt: 1.5, fontSize: tokens.fontSize.xs, color: "text.secondary" }}>
            <Box component="summary" sx={{ cursor: "pointer", fontWeight: 700, color: "primary.main" }}>
              {agent.detail.bullets.length} detail{agent.detail.bullets.length > 1 ? "s" : ""}
            </Box>
            <Box component="ul" sx={{ m: "4px 0 0", pl: 2 }}>
              {agent.detail.bullets.map((b, i) => (
                <li key={i}>{b}</li>
              ))}
            </Box>
          </Box>
        ) : null}
      </Box>
    </Box>
  );
}
