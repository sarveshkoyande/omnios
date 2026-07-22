import { useCallback, useEffect, useState } from "react";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Typography from "@mui/material/Typography";
import Accordion from "@mui/material/Accordion";
import AccordionSummary from "@mui/material/AccordionSummary";
import AccordionDetails from "@mui/material/AccordionDetails";
import Dialog from "@mui/material/Dialog";
import IconButton from "@mui/material/IconButton";
import TextField from "@mui/material/TextField";
import Select from "@mui/material/Select";
import MenuItem from "@mui/material/MenuItem";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Tooltip from "@mui/material/Tooltip";
import { styled } from "@mui/material/styles";
import { PlanTable } from "./PlanTable";
import { StageHead } from "./StageHead";
import { OrchestrationTimeline } from "./OrchestrationTimeline";
import { OrchestrationDownstream } from "./OrchestrationDownstream";
import { OrchestrationNudge } from "./OrchestrationNudge";
import { ConsolePanel } from "../../components/ConsolePanel";
import { glass, indigoTint, shade, tokens } from "../../theme/tokens";
import { getProject, generateOrchestrationTasks, saveOrchestrationTasks } from "../../api";
import { ORCHESTRATION_TEAMS } from "../types";
import type { OrchestrationTask, PlanResult } from "../types";

const TEAM_ICON: Record<string, string> = {
  "Web team": "language",
  "Content & derivative assets team": "perm_media",
  "Campaign operations team": "account_tree",
  "Data & data cloud team": "storage",
  "Reporting & insights team": "insights",
};

const TaskCard = styled(Box)(({ theme }) => ({
  display: "flex",
  alignItems: "center",
  gap: theme.spacing(1.5),
  padding: theme.spacing(1.25, 1.5),
  marginBottom: theme.spacing(1),
  background: glass.content,
  border: `1px solid ${indigoTint(0.12)}`,
  borderRadius: tokens.radius.sm,
  "&:hover": { borderColor: indigoTint(0.32) },
}));

const DetailRow = styled(Box)(({ theme }) => ({
  display: "flex",
  justifyContent: "space-between",
  padding: theme.spacing(1, 0),
  borderBottom: `1px dashed ${shade(0.1)}`,
  fontSize: 13,
}));

const BeliefShift = styled(Box)(({ theme }) => ({
  display: "flex",
  alignItems: "center",
  gap: theme.spacing(2),
  flexWrap: "wrap",
  marginTop: theme.spacing(1),
}));

const BeliefPill = styled("span")<{ tone: "a" | "b" }>(({ tone }) => ({
  padding: "5px 12px",
  borderRadius: 8,
  fontSize: 12,
  background: tone === "a" ? "#FDEAEA" : "#E3F6EC",
  color: tone === "a" ? "#9C3232" : "#1B7A34",
}));

const JourneyCard = styled(Box)(({ theme }) => ({
  border: `1px solid ${indigoTint(0.12)}`,
  borderRadius: tokens.radius.md,
  padding: theme.spacing(2.5),
  marginBottom: theme.spacing(2),
  background: "rgba(255,255,255,0.4)",
}));

const FlowNode = styled(Box)<{ accent: string }>(({ theme, accent }) => ({
  display: "flex",
  gap: theme.spacing(1),
  alignItems: "flex-start",
  background: glass.content,
  border: `1px solid ${indigoTint(0.12)}`,
  borderLeft: `3px solid ${accent}`,
  borderRadius: tokens.radius.sm,
  padding: theme.spacing(1.5, 2),
  flex: "1 1 0",
  minWidth: 130,
}));

const PRIO_COLOR: Record<string, "success" | "secondary" | "default"> = { High: "success", Medium: "secondary", Low: "default" };

export function StageOrchestration({
  result,
  projectId,
  refreshToken = 0,
}: {
  result: PlanResult | null;
  projectId: string | null;
  refreshToken?: number;
}) {
  const [tasks, setTasks] = useState<OrchestrationTask[] | null>(null);
  const [loadingTasks, setLoadingTasks] = useState(false);
  const [newTaskText, setNewTaskText] = useState("");
  const [newTaskTeam, setNewTaskTeam] = useState<string>(ORCHESTRATION_TEAMS[2]);
  const [detailTask, setDetailTask] = useState<OrchestrationTask | null>(null);
  const [hydratedResult, setHydratedResult] = useState<PlanResult | null>(null);
  const effectiveResult = result ?? hydratedResult;

  const persist = useCallback(
    (next: OrchestrationTask[]) => {
      setTasks(next);
      if (projectId) saveOrchestrationTasks(projectId, next).catch(() => {});
    },
    [projectId],
  );

  const regenerate = useCallback(() => {
    if (!projectId) return;
    setLoadingTasks(true);
    generateOrchestrationTasks(projectId)
      .then(setTasks)
      .catch(() => setTasks([]))
      .finally(() => setLoadingTasks(false));
  }, [projectId]);

  // If the user kicked off generation from chat, the artifact can be saved before the
  // parent workspace's result state catches up. Hydrate locally so the tab opens cleanly.
  useEffect(() => {
    if (result || !projectId) {
      setHydratedResult(null);
      return;
    }
    let cancelled = false;
    getProject(projectId)
      .then((proj) => {
        if (!cancelled) setHydratedResult(proj.result ?? null);
      })
      .catch(() => {
        if (!cancelled) setHydratedResult(null);
      });
    return () => {
      cancelled = true;
    };
  }, [result, projectId, refreshToken]);

  // Loads whatever's already saved -- never auto-generates. The checklist only gets built
  // from an explicit action: the chat kickoff card on this tab's first open (see
  // useWorkspace's applyKickoffContext), or the "Regenerate from plan" button below.
  // refreshToken bumps after a kickoff-triggered generation so this refetches.
  useEffect(() => {
    if (!effectiveResult || !projectId) return;
    let cancelled = false;
    setLoadingTasks(true);
    getProject(projectId)
      .then((proj) => {
        if (!cancelled) setTasks(proj.orchestration_tasks ?? []);
      })
      .catch(() => {
        if (!cancelled) setTasks([]);
      })
      .finally(() => {
        if (!cancelled) setLoadingTasks(false);
      });
    return () => {
      cancelled = true;
    };
  }, [effectiveResult, projectId, refreshToken]);

  const toggleTask = (id: string) => {
    if (!tasks) return;
    persist(tasks.map((t) => (t.id === id ? { ...t, done: !t.done } : t)));
  };

  const deleteTask = (id: string) => {
    if (!tasks) return;
    persist(tasks.filter((t) => t.id !== id));
  };

  const addTask = () => {
    if (!tasks || !newTaskText.trim()) return;
    const task: OrchestrationTask = {
      id: `custom-${Date.now()}`,
      category: "Custom",
      title: newTaskText.trim(),
      channel: null,
      done: false,
      team: newTaskTeam,
      sla: null,
      assigned_to: null,
      source: "Manually added task.",
    };
    persist([...tasks, task]);
    setNewTaskText("");
  };

  if (!effectiveResult) {
    return <ConsolePanel><Typography sx={{ color: "text.secondary", fontStyle: "italic" }}>Complete Stage 1 to orchestrate engagement.</Typography></ConsolePanel>;
  }
  const mj = effectiveResult.stage_2_4_micro_journeys ?? { journeys: [] };
  const bam = effectiveResult.stage_2_4_bam_chart ?? {};
  const m = effectiveResult.stage_2_4_strategy?.messaging_architecture ?? {};
  const mf = effectiveResult.stage_2_4_message_flow ?? { key_messages: [] };
  const ppnpp = effectiveResult.stage_2_4_pp_npp ?? [];
  const chsel = effectiveResult.stage_5_channel_selection?.channels ?? [];

  const prioRank: Record<string, number> = { High: 0, Medium: 1, Low: 2 };
  const nbc = [...chsel].sort((a, b) => (prioRank[a.brand_priority ?? ""] ?? 3) - (prioRank[b.brand_priority ?? ""] ?? 3));

  const grouped: Record<string, OrchestrationTask[]> = {};
  for (const t of tasks ?? []) {
    (grouped[t.team] ??= []).push(t);
  }
  const teamOrder = [...ORCHESTRATION_TEAMS, ...Object.keys(grouped).filter((t) => !(ORCHESTRATION_TEAMS as readonly string[]).includes(t))];

  return (
    <Box>
      <StageHead
        icon="account_tree"
        title="Engagement Orchestration"
        blurb="The plan becomes activity: touchpoints, entry/exit criteria, decision logic, segmentation and the tactical plan turned into a setup checklist you can track."
        agent="orchestration"
      />

      <ConsolePanel
        title="Activities & setup tasks"
        icon="checklist"
        sx={{ mb: 3 }}
        action={
          <Button size="small" onClick={regenerate} disabled={loadingTasks || !projectId}>
            Regenerate from plan
          </Button>
        }
      >
        {loadingTasks && tasks === null ? (
          <Box sx={{ display: "flex", justifyContent: "center", py: 3 }}>
            <CircularProgress size={22} />
          </Box>
        ) : tasks && tasks.length > 0 ? (
          teamOrder
            .filter((team) => grouped[team]?.length)
            .map((team) => (
              <Box key={team} sx={{ mb: 3 }}>
                <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}>
                  <span className="material-symbols-outlined" style={{ fontSize: 18, color: tokens.color.primary }}>
                    {TEAM_ICON[team] ?? "group"}
                  </span>
                  <Typography variant="overline" sx={{ fontWeight: 700, color: tokens.color.primary }}>
                    {team}
                  </Typography>
                  <Chip size="small" label={`${grouped[team].length} task${grouped[team].length === 1 ? "" : "s"}`} sx={{ ml: "auto" }} />
                </Box>
                {grouped[team].map((t) => (
                  <TaskCard key={t.id}>
                    <Chip
                      size="small"
                      clickable
                      onClick={() => toggleTask(t.id)}
                      label={t.done ? "Done" : "To do"}
                      color={t.done ? "success" : "default"}
                      sx={{ flex: "0 0 auto" }}
                    />
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Typography
                        variant="body2"
                        sx={{ fontWeight: 600, textDecoration: t.done ? "line-through" : "none", opacity: t.done ? 0.55 : 1 }}
                      >
                        {t.title}
                      </Typography>
                      <Box sx={{ display: "flex", gap: 0.75, mt: 0.25, flexWrap: "wrap", alignItems: "center" }}>
                        <Typography variant="caption" sx={{ color: "text.secondary" }}>{t.category}</Typography>
                        {t.channel && <Chip size="small" variant="outlined" label={t.channel} sx={{ height: 18, fontSize: 11 }} />}
                        {t.gate && (
                          <Tooltip title="Hard compliance gate — routed & tracked, never auto-closed by an agent">
                            <Chip size="small" color="error" label={`Gate: ${t.gate}`} sx={{ height: 18, fontSize: 11 }} />
                          </Tooltip>
                        )}
                        {t.compliance_tier && t.compliance_tier !== "none" && (
                          <Chip size="small" color="warning" variant="outlined" label={t.compliance_tier} sx={{ height: 18, fontSize: 11 }} />
                        )}
                        {t.automation_class && (
                          <Chip size="small" variant="outlined" label={t.automation_class} sx={{ height: 18, fontSize: 11, opacity: 0.8 }} />
                        )}
                      </Box>
                    </Box>
                    <Box sx={{ flex: "0 0 140px", textAlign: "right" }}>
                      <Typography variant="caption" sx={{ display: "block", color: "text.secondary" }}>
                        SLA: {t.sla ?? "TBD"}
                      </Typography>
                      <Typography variant="caption" sx={{ display: "block", color: "text.secondary" }}>
                        {t.assigned_to ?? "Unassigned"}
                      </Typography>
                    </Box>
                    <IconButton size="small" onClick={() => setDetailTask(t)} aria-label="View task detail">
                      <span className="material-symbols-outlined" style={{ fontSize: 16 }}>open_in_new</span>
                    </IconButton>
                    <IconButton size="small" onClick={() => deleteTask(t.id)} aria-label="Remove task">
                      <span className="material-symbols-outlined" style={{ fontSize: 16 }}>close</span>
                    </IconButton>
                  </TaskCard>
                ))}
              </Box>
            ))
        ) : (
          <Typography sx={{ color: "text.secondary", fontStyle: "italic" }}>
            No setup tasks yet. Use the chat on the left to build the checklist from the Stage 1 plan, or
            regenerate it below.
          </Typography>
        )}
        <Box sx={{ display: "flex", gap: 1, mt: 2 }}>
          <TextField
            size="small"
            placeholder="Add a custom task"
            value={newTaskText}
            onChange={(e) => setNewTaskText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") addTask();
            }}
            sx={{ flex: 1 }}
          />
          <Select size="small" value={newTaskTeam} onChange={(e) => setNewTaskTeam(e.target.value)} sx={{ minWidth: 220 }}>
            {ORCHESTRATION_TEAMS.map((team) => (
              <MenuItem key={team} value={team}>{team}</MenuItem>
            ))}
          </Select>
          <Button size="small" variant="outlined" onClick={addTask} disabled={!tasks}>
            Add
          </Button>
        </Box>
      </ConsolePanel>

      <OrchestrationTimeline projectId={projectId} tasks={tasks} />

      <OrchestrationDownstream projectId={projectId} tasks={tasks} />

      <OrchestrationNudge projectId={projectId} tasks={tasks} />

      <Dialog open={!!detailTask} onClose={() => setDetailTask(null)} maxWidth="sm" fullWidth>
        {detailTask && (
          <Box sx={{ p: 4, position: "relative" }}>
            <IconButton onClick={() => setDetailTask(null)} sx={{ position: "absolute", top: 12, right: 12 }} aria-label="Close">
              <span className="material-symbols-outlined">close</span>
            </IconButton>
            <Typography variant="overline" sx={{ color: tokens.color.primary, fontWeight: 700 }}>{detailTask.team}</Typography>
            <Typography variant="h3" sx={{ fontSize: 18, mb: 1 }}>{detailTask.title}</Typography>
            <Chip
              size="small"
              label={detailTask.done ? "Done" : "To do"}
              color={detailTask.done ? "success" : "default"}
              sx={{ mb: 2 }}
            />
            <DetailRow><span>Category</span><b>{detailTask.category}</b></DetailRow>
            {detailTask.channel && <DetailRow><span>Channel</span><b>{detailTask.channel}</b></DetailRow>}
            <DetailRow>
              <span>SLA</span>
              <b>
                {detailTask.sla_meta
                  ? `${detailTask.sla_meta.target_days} business days (was ${detailTask.sla_meta.baseline_days} manual)`
                  : detailTask.sla ?? "TBD"}
              </b>
            </DetailRow>
            {detailTask.compliance_tier && detailTask.compliance_tier !== "none" && (
              <DetailRow><span>Compliance tier</span><b>{detailTask.compliance_tier}</b></DetailRow>
            )}
            {detailTask.gate && (
              <DetailRow>
                <span>Hard gate</span>
                <b style={{ color: "#A11F35" }}>{detailTask.gate} — human-cleared only</b>
              </DetailRow>
            )}
            {detailTask.automation_class && (
              <DetailRow><span>Automation</span><b>{detailTask.automation_class}</b></DetailRow>
            )}
            {detailTask.definition_of_done && (
              <DetailRow><span>Done when</span><b style={{ maxWidth: 280, textAlign: "right" }}>{detailTask.definition_of_done}</b></DetailRow>
            )}
            {detailTask.gating_input && (
              <DetailRow><span>Waiting on</span><b style={{ maxWidth: 280, textAlign: "right" }}>{detailTask.gating_input}</b></DetailRow>
            )}
            <DetailRow><span>Assigned to</span><b>{detailTask.assigned_to ?? "Unassigned"}</b></DetailRow>
            {detailTask.source && (
              <Typography variant="body2" sx={{ color: "text.secondary", fontStyle: "italic", mt: 2 }}>
                {detailTask.source}
              </Typography>
            )}
            <Box sx={{ display: "flex", gap: 1, mt: 3 }}>
              <Button
                size="small"
                variant="contained"
                onClick={() => {
                  toggleTask(detailTask.id);
                  setDetailTask({ ...detailTask, done: !detailTask.done });
                }}
              >
                Mark as {detailTask.done ? "to do" : "done"}
              </Button>
              <Button
                size="small"
                variant="outlined"
                color="error"
                onClick={() => {
                  deleteTask(detailTask.id);
                  setDetailTask(null);
                }}
              >
                Remove task
              </Button>
            </Box>
          </Box>
        )}
      </Dialog>

      <Accordion
        sx={{
          background: glass.panel,
          border: `1px solid ${indigoTint(0.12)}`,
          borderRadius: tokens.radius.md,
          mb: 3,
          "&:before": { display: "none" },
          "&.Mui-expanded": { margin: 0, marginBottom: 3 },
        }}
      >
        <AccordionSummary expandIcon={<span className="material-symbols-outlined">expand_more</span>}>
          <Typography sx={{ fontWeight: 700, fontSize: 13 }}>Previous orchestration view</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <ConsolePanel sx={{ mb: 3 }}>
            <Typography variant="overline">Orchestration objective: belief shift</Typography>
            <BeliefShift>
              <BeliefPill tone="a">{m.current_belief || "N/A"}</BeliefPill>
              <span className="material-symbols-outlined">east</span>
              <BeliefPill tone="b">{m.desired_belief || "N/A"}</BeliefPill>
            </BeliefShift>
            {bam.a_to_b_shift && <Typography variant="body2" sx={{ color: "text.secondary", mt: 1.5 }}>{bam.a_to_b_shift}</Typography>}
          </ConsolePanel>

          <ConsolePanel title="Journey orchestration" sx={{ mb: 3 }}>
            {mj.journeys.length ? (
              mj.journeys.map((j, i) => (
                <JourneyCard key={i}>
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, mb: 1.5 }}>
                    <Box sx={{ width: 20, height: 20, borderRadius: "50%", background: "primary.main", color: tokens.color.text, fontSize: 11, display: "flex", alignItems: "center", justifyContent: "center", bgcolor: "primary.main" }}>{i + 1}</Box>
                    <Typography sx={{ fontWeight: 700 }}>{j.name}</Typography>
                  </Box>
                  <Box sx={{ display: "flex", gap: 1, alignItems: "stretch", flexWrap: "wrap" }}>
                    <FlowNode accent={tokens.color.warning}>
                      <span className="material-symbols-outlined" style={{ fontSize: 16 }}>bolt</span>
                      <Box><Typography variant="overline" sx={{ display: "block" }}>Trigger</Typography><Typography variant="body2">{j.trigger}</Typography></Box>
                    </FlowNode>
                    <FlowNode accent={tokens.color.primary}>
                      <span className="material-symbols-outlined" style={{ fontSize: 16 }}>send</span>
                      <Box><Typography variant="overline" sx={{ display: "block" }}>Channel</Typography><Typography variant="body2">{j.primary_touchpoint}</Typography></Box>
                    </FlowNode>
                    <FlowNode accent={tokens.color.success}>
                      <span className="material-symbols-outlined" style={{ fontSize: 16 }}>inventory_2</span>
                      <Box><Typography variant="overline" sx={{ display: "block" }}>Content</Typography><Typography variant="body2">{j.content_readiness}</Typography></Box>
                    </FlowNode>
                  </Box>
                </JourneyCard>
              ))
            ) : (
              <Typography sx={{ color: "text.secondary", fontStyle: "italic" }}>No micro-journeys generated.</Typography>
            )}
            {mj.interim_check && <Typography variant="caption" sx={{ color: "text.secondary", fontStyle: "italic", display: "block", mt: 1 }}>Governance: {mj.interim_check}</Typography>}
          </ConsolePanel>

          <ConsolePanel title="Next-best-channel ranking" sx={{ mb: 3 }}>
            <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mb: 1 }}>
              Ranked by brand priority: the orchestration engine's channel-selection order.
            </Typography>
            <PlanTable>
              <thead><tr><th>#</th><th>Channel</th><th>Priority</th><th>Availability</th><th>Affinity</th></tr></thead>
              <tbody>
                {nbc.map((c, i) => (
                  <tr key={i}>
                    <td>{i + 1}</td>
                    <td><b>{c.channel}</b></td>
                    <td>{c.brand_priority && <Chip size="small" color={PRIO_COLOR[c.brand_priority] ?? "default"} label={c.brand_priority} />}</td>
                    <td>{c.availability ?? "N/A"}</td>
                    <td>{c.preference_affinity ?? "N/A"}</td>
                  </tr>
                ))}
              </tbody>
            </PlanTable>
          </ConsolePanel>

          <ConsolePanel title="Message ladder (sequencing)" sx={{ mb: 3 }}>
            {mf.key_messages.length ? (
              mf.key_messages.map((km, i) => (
                <Box key={i} sx={{ display: "flex", gap: 1.5, py: 1, borderBottom: i < mf.key_messages.length - 1 ? `1px dashed ${shade(0.14)}` : "none" }}>
                  <Box sx={{ width: 20, height: 20, borderRadius: "50%", bgcolor: "primary.main", fontSize: 11, display: "flex", alignItems: "center", justifyContent: "center", flex: "0 0 auto" }}>{i + 1}</Box>
                  <Box>
                    <Typography sx={{ fontWeight: 700, fontSize: 13 }}>{km.topic}</Typography>
                    <Typography variant="caption" sx={{ color: "text.secondary" }}>{km.supporting_messages.slice(0, 2).join(" · ")}</Typography>
                  </Box>
                </Box>
              ))
            ) : (
              <Typography sx={{ color: "text.secondary", fontStyle: "italic" }}>No key messages.</Typography>
            )}
          </ConsolePanel>

          <ConsolePanel title="Personal vs non-personal split & cadence">
            <PlanTable>
              <thead><tr><th>Channel</th><th>Share</th><th>PP / NPP</th></tr></thead>
              <tbody>
                {ppnpp.map((p, i) => (
                  <tr key={i}>
                    <td>{p.channel}</td>
                    <td>{p.pct}%</td>
                    <td><Chip size="small" color={p.bucket === "PP" ? "secondary" : "primary"} label={p.bucket} /></td>
                  </tr>
                ))}
              </tbody>
            </PlanTable>
            <Typography variant="caption" sx={{ color: "text.secondary", fontStyle: "italic", display: "block", mt: 1 }}>
              Cadence guardrail: respect channel-level frequency caps and suppression; a rep touch and a digital touch
              in the same week counts as one engagement for frequency purposes.
            </Typography>
          </ConsolePanel>
        </AccordionDetails>
      </Accordion>
    </Box>
  );
}
