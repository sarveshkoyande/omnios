import { useCallback, useEffect, useState } from "react";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Typography from "@mui/material/Typography";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import { styled } from "@mui/material/styles";
import { ConsolePanel } from "../../components/ConsolePanel";
import { indigoTint, tokens } from "../../theme/tokens";
import { ackNotification, getNotifications, runNudges } from "../../api";
import type { Notification, OrchestrationTask } from "../types";

const SEV_COLOR: Record<string, string> = {
  urgent: "#A11F35", high: "#D6304A", warning: "#C2760A", info: "#2451C4",
};
const SEV_ICON: Record<string, string> = {
  urgent: "e_mobiledata", high: "priority_high", warning: "warning", info: "notifications",
};
const CHANNEL_ICON: Record<string, string> = {
  slack: "tag", teams: "groups", email: "mail",
};

const Card = styled(Box)<{ sev: string }>(({ theme, sev }) => ({
  display: "flex",
  gap: theme.spacing(1.25),
  padding: theme.spacing(1.25, 1.5),
  marginBottom: theme.spacing(1),
  borderRadius: tokens.radius.sm,
  border: `1px solid ${indigoTint(0.12)}`,
  borderLeft: `4px solid ${SEV_COLOR[sev] ?? "#888"}`,
  background: "rgba(255,255,255,0.5)",
}));

export function OrchestrationNudge({
  projectId,
  tasks,
}: {
  projectId: string | null;
  tasks: OrchestrationTask[] | null;
}) {
  const [notes, setNotes] = useState<Notification[] | null>(null);
  const [running, setRunning] = useState(false);
  const [escalatedCount, setEscalatedCount] = useState<number | null>(null);

  const load = useCallback(() => {
    if (!projectId) return;
    getNotifications(projectId)
      .then((r) => setNotes(r.notifications.filter((n) => !n.acked)))
      .catch(() => setNotes([]));
  }, [projectId]);

  useEffect(() => {
    load();
  }, [load]);

  const run = useCallback(() => {
    if (!projectId) return;
    setRunning(true);
    runNudges(projectId)
      .then((r) => {
        setNotes(r.open.filter((n) => !n.acked));
        setEscalatedCount(r.escalated.length);
      })
      .catch(() => {})
      .finally(() => setRunning(false));
  }, [projectId]);

  const ack = useCallback(
    (key: string) => {
      if (!projectId) return;
      setNotes((prev) => (prev ? prev.filter((n) => n.dedupe_key !== key) : prev));
      ackNotification(projectId, key).catch(() => load());
    },
    [projectId, load],
  );

  if (!projectId) return null;
  const taskCount = tasks?.length ?? 0;

  return (
    <ConsolePanel
      title="Nudge agent"
      icon="notifications_active"
      sx={{ mb: 3 }}
      action={
        <Button size="small" variant="contained" onClick={run} disabled={running || taskCount === 0}>
          {running ? <CircularProgress size={16} sx={{ color: "#fff" }} /> : "Run nudge agent"}
        </Button>
      }
    >
      <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mb: 1.5 }}>
        Notifies each team of new, upcoming, at-risk and overdue activities and auto-escalates repeated overdues to the conductor.
        Hard gates (MLR, consent, ISI, AFU, AE/MIR) are routed &amp; tracked, never auto-closed.
        {escalatedCount != null && escalatedCount > 0 ? ` · ${escalatedCount} escalated this run.` : ""}
      </Typography>

      {notes === null ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 2 }}>
          <CircularProgress size={20} />
        </Box>
      ) : notes.length === 0 ? (
        <Typography sx={{ color: "text.secondary", fontStyle: "italic" }}>
          No open notifications. Run the nudge agent to evaluate the current schedule.
        </Typography>
      ) : (
        notes.map((n) => (
          <Card key={n.dedupe_key} sev={n.severity}>
            <span className="material-symbols-outlined" style={{ fontSize: 20, color: SEV_COLOR[n.severity] ?? "#888" }}>
              {SEV_ICON[n.severity] ?? "notifications"}
            </span>
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Box sx={{ display: "flex", gap: 0.75, alignItems: "center", flexWrap: "wrap" }}>
                <Typography variant="body2" sx={{ fontWeight: 700 }}>{n.title}</Typography>
                {n.escalated ? <Chip size="small" color="error" label="escalated" sx={{ height: 18, fontSize: 10 }} /> : null}
                {n.gate ? <Chip size="small" color="error" variant="outlined" label={`gate: ${n.gate}`} sx={{ height: 18, fontSize: 10 }} /> : null}
                {n.fire_count > 1 ? <Chip size="small" variant="outlined" label={`×${n.fire_count}`} sx={{ height: 18, fontSize: 10 }} /> : null}
              </Box>
              <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mt: 0.25 }}>{n.body}</Typography>
              <Box sx={{ display: "flex", gap: 0.5, alignItems: "center", mt: 0.5 }}>
                <span className="material-symbols-outlined" style={{ fontSize: 14, color: tokens.color.primary }}>
                  {CHANNEL_ICON[n.channel] ?? "send"}
                </span>
                <Typography variant="caption" sx={{ color: "text.secondary" }}>
                  {n.channel} → {n.recipient}
                </Typography>
              </Box>
            </Box>
            <Button size="small" onClick={() => ack(n.dedupe_key)} sx={{ flex: "0 0 auto", alignSelf: "center" }}>
              Acknowledge
            </Button>
          </Card>
        ))
      )}
    </ConsolePanel>
  );
}
