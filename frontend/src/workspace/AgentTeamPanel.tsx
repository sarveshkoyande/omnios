import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { keyframes } from "@emotion/react";
import { styled } from "@mui/material/styles";
import { AgentAvatar } from "./Avatar";
import { AGENT_PEOPLE } from "./types";
import { tokens, shade, indigoTint } from "../theme/tokens";

export interface AgentEntry {
  id: string;
  name: string;
  role?: string;
  status: "standby" | "running" | "done";
  summary?: string;
  detail?: { bullets: string[] };
}

/** Badge rail: a laminated ID clipped to a lanyard rail, lit when working. */
const Badge = styled("div")<{ status: AgentEntry["status"] }>(({ theme, status }) => ({
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  gap: theme.spacing(1.5),
  flex: "1 1 0",
  minWidth: 0,
  textAlign: "center",
  transition: "transform 200ms ease",
  transform: status === "running" ? "translateY(-3px)" : "none",
  opacity: status === "standby" ? 0.55 : 1,
  filter: status === "standby" ? "grayscale(0.8)" : "none",
}));

const BadgeRing = styled("div")<{ status: AgentEntry["status"] }>(({ status }) => ({
  position: "relative",
  display: "inline-flex",
  borderRadius: "50%",
  boxShadow:
    status === "running"
      ? `0 0 0 3px ${tokens.color.secondary}`
      : status === "done"
        ? `0 0 0 3px ${tokens.color.success}`
        : "none",
}));

const pulse = keyframes`
  0% { box-shadow: 0 0 0 0 currentColor; }
  70% { box-shadow: 0 0 0 6px transparent; }
  100% { box-shadow: 0 0 0 0 transparent; }
`;

const StatusLight = styled("i")<{ status: AgentEntry["status"] }>(({ status }) => ({
  position: "absolute",
  right: -1,
  bottom: -1,
  width: 11,
  height: 11,
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
  marginTop: 8,
  backgroundImage: `linear-gradient(90deg, ${shade(0.06)} 25%, ${tokens.color.secondary} 37%, ${shade(0.06)} 63%)`,
  backgroundSize: "400% 100%",
  animation: `${shimmerMove} 1.3s ease infinite`,
});

const TeamCaption = styled(Typography)(({ theme }) => ({
  textAlign: "center",
  marginTop: theme.spacing(3),
  paddingTop: theme.spacing(2),
  borderTop: `1px dashed ${indigoTint(0.18)}`,
  minHeight: 20,
  "& b": { color: tokens.color.text },
}));

const AgentCard = styled("div")<{ status: AgentEntry["status"] }>(({ theme, status }) => ({
  display: "flex",
  gap: theme.spacing(2.5),
  alignItems: "flex-start",
  padding: theme.spacing(2.5),
  marginBottom: theme.spacing(1),
  borderRadius: tokens.radius.sm,
  borderBottom: `1px solid ${indigoTint(0.1)}`,
  opacity: status === "standby" ? 0.55 : 1,
  background: status === "running" ? indigoTint(0.07) : "transparent",
}));

function StatusDot({ status }: { status: AgentEntry["status"] }) {
  const color = status === "running" ? tokens.color.secondary : status === "done" ? tokens.color.success : shade(0.25);
  return (
    <Box
      component="span"
      sx={{ width: 8, height: 8, borderRadius: "50%", background: color, flex: "0 0 auto", ml: "auto" }}
    />
  );
}

export function AgentTeamPanel({ agents, caption }: { agents: AgentEntry[]; caption: string }) {
  if (!agents.length) {
    return (
      <Typography variant="body2" sx={{ color: "text.secondary", fontStyle: "italic" }}>
        The agent team appears here and works in real time once the brief is complete.
      </Typography>
    );
  }
  return (
    <Box>
      <Box
        sx={{
          background: indigoTint(0.05),
          border: `1px solid ${indigoTint(0.12)}`,
          borderRadius: tokens.radius.md,
          p: 3,
          mb: 3,
        }}
      >
        <Box sx={{ display: "flex", gap: 1.5, justifyContent: "space-between" }}>
          {agents.map((a) => (
            <Badge key={a.id} status={a.status}>
              <BadgeRing status={a.status}>
                <AgentAvatar id={a.id} size={46} />
                <StatusLight status={a.status} />
              </BadgeRing>
              <Typography variant="caption" sx={{ fontWeight: 700, color: a.status === "running" ? "secondary.main" : "text.primary" }}>
                {AGENT_PEOPLE[a.id]?.name.split(" ")[0] ?? a.name}
              </Typography>
            </Badge>
          ))}
        </Box>
        <TeamCaption variant="caption" dangerouslySetInnerHTML={{ __html: caption }} />
      </Box>

      {agents.map((a) => (
        <AgentCard key={a.id} status={a.status}>
          <AgentAvatar id={a.id} size={38} />
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              <Typography variant="subtitle1" sx={{ fontSize: tokens.fontSize.sm, fontWeight: 700 }}>
                {AGENT_PEOPLE[a.id]?.name ?? a.name}
              </Typography>
              <StatusDot status={a.status} />
            </Box>
            <Typography
              variant="body2"
              sx={{ color: a.status === "running" ? "secondary.main" : "text.secondary", mt: 0.5 }}
            >
              {a.status === "standby" ? "Standing by" : a.status === "running" ? "Working…" : a.summary || "Done"}
            </Typography>
            {a.status === "running" && <Shimmer />}
            {a.status === "done" && a.detail?.bullets?.length ? (
              <Box component="details" sx={{ mt: 1, fontSize: tokens.fontSize.xs, color: "text.secondary" }}>
                <Box component="summary" sx={{ cursor: "pointer", fontWeight: 700, color: "primary.main" }}>
                  {a.detail.bullets.length} detail{a.detail.bullets.length > 1 ? "s" : ""}
                </Box>
                <Box component="ul" sx={{ m: "4px 0 0", pl: 2 }}>
                  {a.detail.bullets.map((b, i) => (
                    <li key={i}>{b}</li>
                  ))}
                </Box>
              </Box>
            ) : null}
          </Box>
        </AgentCard>
      ))}
    </Box>
  );
}
