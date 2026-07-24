import { useCallback, useEffect, useRef, useState } from "react";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Typography from "@mui/material/Typography";
import Button from "@mui/material/Button";
import Tooltip from "@mui/material/Tooltip";
import CircularProgress from "@mui/material/CircularProgress";
import { PlanTable } from "./PlanTable";
import { ConsolePanel } from "../../components/ConsolePanel";
import { indigoTint, tokens } from "../../theme/tokens";
import IconButton from "@mui/material/IconButton";
import { getOrchestrationBindings, pushOrchestration, simulateExternalChange, syncOrchestration } from "../../api";
import type { ExternalBinding, OrchestrationTask, SyncResponse } from "../types";

const SYSTEM_LABEL: Record<string, string> = {
  stub: "Sandbox (stub)", monday: "Monday.com", smartsheet: "Smartsheet", jira: "Jira",
};

function stateChip(s: string) {
  if (s === "synced") return <Chip size="small" color="success" label="synced" sx={{ height: 20 }} />;
  if (s === "unconfigured") return <Chip size="small" color="warning" variant="outlined" label="needs credentials" sx={{ height: 20 }} />;
  return <Chip size="small" variant="outlined" label={s} sx={{ height: 20 }} />;
}

export function OrchestrationDownstream({
  projectId,
  tasks,
}: {
  projectId: string | null;
  tasks: OrchestrationTask[] | null;
}) {
  const [bindings, setBindings] = useState<ExternalBinding[] | null>(null);
  const [routes, setRoutes] = useState<Record<string, { system: string; board: string }>>({});
  const [pushing, setPushing] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [summary, setSummary] = useState<Record<string, number> | null>(null);
  const [syncResult, setSyncResult] = useState<SyncResponse | null>(null);

  const refresh = useCallback(() => {
    if (!projectId) return;
    getOrchestrationBindings(projectId)
      .then((r) => {
        setBindings(r.bindings);
        setRoutes(r.routing?.routes ?? {});
      })
      .catch(() => setBindings([]));
  }, [projectId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Populate on load rather than sitting empty until someone presses "Push to systems":
  // once tasks exist but nothing has been routed yet, do that first push automatically.
  // Guarded per project so it runs once and never fights a user who cleared the bindings.
  const autoPushed = useRef<string | null>(null);
  useEffect(() => {
    if (!projectId || !tasks?.length) return;
    if (bindings === null || bindings.length > 0) return; // not loaded yet, or already populated
    if (autoPushed.current === projectId) return;
    autoPushed.current = projectId;
    setPushing(true);
    pushOrchestration(projectId)
      .then((r) => {
        setSummary(r.counts);
        setBindings(r.bindings);
      })
      .catch(() => {})
      .finally(() => setPushing(false));
  }, [projectId, tasks, bindings]);

  const doPush = useCallback(() => {
    if (!projectId) return;
    setPushing(true);
    pushOrchestration(projectId)
      .then((r) => {
        setSummary(r.counts);
        setBindings(r.bindings);
      })
      .catch(() => {})
      .finally(() => setPushing(false));
  }, [projectId]);

  const doSync = useCallback(() => {
    if (!projectId) return;
    setSyncing(true);
    syncOrchestration(projectId)
      .then((r) => {
        setSyncResult(r);
        refresh();
      })
      .catch(() => {})
      .finally(() => setSyncing(false));
  }, [projectId, refresh]);

  const simulate = useCallback(
    (activityId: string) => {
      if (!projectId) return;
      simulateExternalChange(projectId, activityId, "Done").then(doSync).catch(() => {});
    },
    [projectId, doSync],
  );

  if (!projectId) return null;
  const taskCount = tasks?.length ?? 0;
  const activeSystems = [...new Set(Object.values(routes).map((r) => r.system))];

  return (
    <ConsolePanel
      title="Downstream systems"
      icon="sync_alt"
      sx={{ mb: 3 }}
      action={
        <Box sx={{ display: "flex", gap: 1 }}>
          <Button size="small" onClick={doSync} disabled={syncing || !(bindings && bindings.length)}>
            {syncing ? <CircularProgress size={16} /> : "Sync now"}
          </Button>
          <Button size="small" variant="contained" onClick={doPush} disabled={pushing || taskCount === 0}>
            {pushing ? <CircularProgress size={16} sx={{ color: "#fff" }} /> : "Push activities"}
          </Button>
        </Box>
      }
    >
      <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mb: 1.5 }}>
        Activities are pushed to each team's routed system of work and kept idempotent — re-pushing updates existing items, never duplicates.
        Routing: {activeSystems.map((s) => SYSTEM_LABEL[s] ?? s).join(", ") || "stub"}.
      </Typography>

      {summary && (
        <Box sx={{ display: "flex", gap: 0.75, flexWrap: "wrap", mb: 2 }}>
          {Object.entries(summary)
            .filter(([, n]) => n > 0)
            .map(([k, n]) => (
              <Chip key={k} size="small" label={`${n} ${k}`} color={k === "error" ? "error" : k === "unconfigured" ? "warning" : "default"} />
            ))}
        </Box>
      )}

      {syncResult && (
        <Box sx={{ display: "flex", gap: 0.75, flexWrap: "wrap", mb: 2, alignItems: "center" }}>
          <span className="material-symbols-outlined" style={{ fontSize: 16, color: tokens.color.primary }}>sync</span>
          <Typography variant="caption" sx={{ color: "text.secondary" }}>
            {syncResult.applied.length
              ? `${syncResult.applied.length} inbound change${syncResult.applied.length === 1 ? "" : "s"} applied`
              : "In sync — no inbound changes"}
            {syncResult.conflicts.length ? ` · ${syncResult.conflicts.length} conflict(s) held for review` : ""}
          </Typography>
          {syncResult.applied.map((c, i) => (
            <Chip key={i} size="small" color="success" variant="outlined" label={`${c.title ?? c.activity_id}: ${c.field}=${String(c.value)}`} sx={{ height: 20 }} />
          ))}
        </Box>
      )}

      {bindings === null ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 2 }}>
          <CircularProgress size={20} />
        </Box>
      ) : bindings.length === 0 ? (
        <Typography sx={{ color: "text.secondary", fontStyle: "italic" }}>
          Nothing pushed yet. Push the activities to create tracked items in the routed systems.
        </Typography>
      ) : (
        <Box sx={{ border: `1px solid ${indigoTint(0.12)}`, borderRadius: tokens.radius.sm, overflow: "hidden" }}>
          <PlanTable>
            <thead>
              <tr><th>Activity</th><th>System</th><th>State</th><th>Link</th><th>Simulate</th></tr>
            </thead>
            <tbody>
              {bindings.map((b) => (
                <tr key={`${b.activity_id}-${b.system}`}>
                  <td style={{ fontFamily: "monospace", fontSize: 12 }}>{b.activity_id}</td>
                  <td>{SYSTEM_LABEL[b.system] ?? b.system}</td>
                  <td>{stateChip(b.sync_state)}</td>
                  <td>
                    {b.external_url ? (
                      <Tooltip title={b.external_url}>
                        <span style={{ fontFamily: "monospace", fontSize: 11, color: tokens.color.primary }}>{b.external_id}</span>
                      </Tooltip>
                    ) : (
                      <span style={{ color: "#888", fontSize: 12 }}>—</span>
                    )}
                  </td>
                  <td>
                    {b.system === "stub" && b.external_id ? (
                      <Tooltip title="Simulate a teammate marking this Done in the downstream tool, then sync it back">
                        <IconButton size="small" onClick={() => simulate(b.activity_id)} aria-label="Simulate external completion">
                          <span className="material-symbols-outlined" style={{ fontSize: 16 }}>task_alt</span>
                        </IconButton>
                      </Tooltip>
                    ) : (
                      <span style={{ color: "#888", fontSize: 12 }}>—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </PlanTable>
        </Box>
      )}
    </ConsolePanel>
  );
}
