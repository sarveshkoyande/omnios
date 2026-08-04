import { useCallback, useEffect, useMemo, useState } from "react";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Typography from "@mui/material/Typography";
import TextField from "@mui/material/TextField";
import Button from "@mui/material/Button";
import Tooltip from "@mui/material/Tooltip";
import CircularProgress from "@mui/material/CircularProgress";
import { ConsolePanel } from "../../components/ConsolePanel";
import { glass, indigoTint, shade, tokens } from "../../theme/tokens";
import { getOrchestrationSchedule } from "../../api";
import { ORCHESTRATION_TEAMS } from "../types";
import type { OrchestrationSchedule, OrchestrationTask } from "../types";

// Phase band accent colours -- a functional legend, deliberately not brand-token driven
// (same pattern as planDocSkinCss.ts's toolkit-phase legend, called out in CLAUDE.md).
const PHASE_COLOR: Record<string, string> = {
  planning: "#6C7BF2",
  production: "#22B36B",
  review: "#E8A13A",
  execution: "#3AA0E8",
  wrap: "#9B72E0",
};
const PHASE_LABEL: Record<string, string> = {
  planning: "Planning", production: "Production", review: "Review", execution: "Execution", wrap: "Wrap / measure",
};

function ymd(d: string): number {
  return new Date(d + "T00:00:00").getTime();
}
function fmt(d: string): string {
  return new Date(d + "T00:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function defaultGoLive(): string {
  const d = new Date();
  d.setDate(d.getDate() + 56); // 8 weeks out -- a sane default anchor for backward scheduling
  return d.toISOString().slice(0, 10);
}

/** Colour for an activity bar by live state. */
function barState(a: OrchestrationTask, todayMs: number): { color: string; label: string } {
  if (a.done) return { color: "#1B7A34", label: "Done" };
  if (a.planned_due && ymd(a.planned_due) < todayMs) return { color: tokens.color.danger ?? "#C0392B", label: "Overdue" };
  if (a.is_critical) return { color: "#E8A13A", label: "Critical" };
  return { color: "#3AA0E8", label: "On track" };
}

export function OrchestrationTimeline({
  projectId,
  tasks,
  onScheduled,
}: {
  projectId: string | null;
  tasks: OrchestrationTask[] | null;
  onScheduled?: (s: OrchestrationSchedule) => void;
}) {
  const [goLive, setGoLive] = useState<string>(defaultGoLive());
  const [sched, setSched] = useState<OrchestrationSchedule | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const todayMs = useMemo(() => ymd(new Date().toISOString().slice(0, 10)), []);

  const load = useCallback(() => {
    if (!projectId) return;
    setLoading(true);
    setErr(null);
    getOrchestrationSchedule(projectId, { goLive })
      .then((s) => {
        setSched(s);
        onScheduled?.(s);
      })
      .catch(() => setErr("Couldn't compute the timeline. Generate activities first, then try again."))
      .finally(() => setLoading(false));
  }, [projectId, goLive, onScheduled]);

  // Recompute whenever the activity set changes (e.g. after regenerate) or the date changes.
  const taskCount = tasks?.length ?? 0;
  useEffect(() => {
    if (taskCount > 0) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskCount, goLive]);

  // Domain across all bands for horizontal positioning.
  const domain = useMemo(() => {
    if (!sched?.bands.length) return null;
    const starts = sched.bands.map((b) => ymd(b.start));
    const ends = sched.bands.map((b) => ymd(b.end));
    const min = Math.min(...starts, todayMs);
    const max = Math.max(...ends);
    return { min, max, span: Math.max(1, max - min) };
  }, [sched, todayMs]);

  const pct = (ms: number) => (domain ? ((ms - domain.min) / domain.span) * 100 : 0);

  const teamsOrdered = useMemo(() => {
    if (!sched) return [];
    const present = new Set(sched.activities.map((a) => a.team));
    const extra = [...present].filter((t) => !(ORCHESTRATION_TEAMS as readonly string[]).includes(t));
    return [...ORCHESTRATION_TEAMS, ...extra].filter((t) => present.has(t));
  }, [sched]);

  if (!projectId) return null;

  return (
    <ConsolePanel
      title="Timeline & time-saved"
      icon="timeline"
      sx={{ mb: 3 }}
      action={
        <Box sx={{ display: "flex", gap: 1, alignItems: "center" }}>
          <TextField
            size="small"
            type="date"
            label="Go-live"
            value={goLive}
            onChange={(e) => setGoLive(e.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
            sx={{ width: 160 }}
          />
          <Button size="small" onClick={load} disabled={loading || taskCount === 0}>
            Recompute
          </Button>
        </Box>
      }
    >
      {taskCount === 0 ? (
        <Typography sx={{ color: "text.secondary", fontStyle: "italic" }}>
          Generate activities above to see the backward-scheduled timeline and the time saved versus the manual baseline.
        </Typography>
      ) : loading && !sched ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 3 }}>
          <CircularProgress size={22} />
        </Box>
      ) : err ? (
        <Typography sx={{ color: "text.secondary", fontStyle: "italic" }}>{err}</Typography>
      ) : sched ? (
        <>
          {/* ROI banner -- the stakeholder "powerful, simple visual" (PRD 6.4/F4.7). */}
          <Box
            sx={{
              display: "flex",
              gap: 3,
              flexWrap: "wrap",
              alignItems: "center",
              p: 2,
              mb: 2,
              borderRadius: tokens.radius.md,
              background: "linear-gradient(90deg, rgba(34,179,107,0.10), rgba(58,160,232,0.10))",
              border: `1px solid ${indigoTint(0.14)}`,
            }}
          >
            <Box>
              <Typography variant="overline" sx={{ color: "text.secondary" }}>Orchestrated timeline</Typography>
              <Typography sx={{ fontSize: 26, fontWeight: 800, lineHeight: 1.1 }}>
                {sched.elapsed.pre_launch_days}<span style={{ fontSize: 15, fontWeight: 600 }}> business days</span>
              </Typography>
            </Box>
            <span className="material-symbols-outlined" style={{ color: "#1B7A34" }}>trending_down</span>
            <Box>
              <Typography variant="overline" sx={{ color: "text.secondary" }}>Manual baseline</Typography>
              <Typography sx={{ fontSize: 20, fontWeight: 700, color: "text.secondary", textDecoration: "line-through" }}>
                {sched.elapsed.pre_launch_days_baseline} days
              </Typography>
            </Box>
            <Box sx={{ ml: "auto", textAlign: "right" }}>
              <Chip
                color="success"
                label={`${sched.elapsed.reduction_pct}% faster · ${sched.elapsed.days_saved} days saved`}
                sx={{ fontWeight: 700 }}
              />
              <Typography variant="caption" sx={{ display: "block", color: "text.secondary", mt: 0.5 }}>
                Ref: ~{sched.elapsed.reference_baseline_simple_campaign_days}-day simple-campaign baseline · {sched.elapsed.reference_target_days}-day target
              </Typography>
            </Box>
          </Box>

          {sched.infeasible && (
            <Box sx={{ display: "flex", gap: 1, alignItems: "center", p: 1.5, mb: 2, borderRadius: tokens.radius.sm, background: "#FDEAEA", color: "#9C3232" }}>
              <span className="material-symbols-outlined" style={{ fontSize: 18 }}>warning</span>
              <Typography variant="body2">{sched.infeasible_note}</Typography>
            </Box>
          )}

          {/* Phase legend */}
          <Box sx={{ display: "flex", gap: 1.5, flexWrap: "wrap", mb: 1.5 }}>
            {sched.bands.map((b) => (
              <Box key={b.phase} sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                <Box sx={{ width: 12, height: 12, borderRadius: 0.5, background: PHASE_COLOR[b.phase] ?? shade(0.3) }} />
                <Typography variant="caption" sx={{ color: "text.secondary" }}>
                  {PHASE_LABEL[b.phase] ?? b.phase} · {fmt(b.start)}–{fmt(b.end)}{b.is_post_launch ? " (post-launch)" : ""}
                </Typography>
              </Box>
            ))}
          </Box>

          {/* Swimlane Gantt: one row per team, bars positioned by planned dates. */}
          <Box sx={{ position: "relative", border: `1px solid ${indigoTint(0.12)}`, borderRadius: tokens.radius.sm, overflow: "hidden" }}>
            {/* go-live marker */}
            {domain && (
              <Box
                sx={{
                  position: "absolute",
                  left: `calc(180px + (100% - 180px) * ${pct(ymd(sched.go_live)) / 100})`,
                  top: 0,
                  bottom: 0,
                  width: "2px",
                  background: "#C0392B",
                  zIndex: 2,
                }}
              >
                <Chip size="small" color="error" label="Go-live" sx={{ position: "absolute", top: 2, left: 4, height: 24, fontSize: 15 }} />
              </Box>
            )}
            {teamsOrdered.map((team) => {
              const rows = sched.activities.filter((a) => a.team === team);
              return (
                <Box key={team} sx={{ display: "flex", borderBottom: `1px dashed ${shade(0.1)}`, minHeight: 46 }}>
                  <Box sx={{ flex: "0 0 180px", p: 1, borderRight: `1px solid ${shade(0.1)}`, background: glass.content }}>
                    <Typography variant="caption" sx={{ fontWeight: 700, lineHeight: 1.15, display: "block" }}>{team}</Typography>
                    <Typography variant="caption" sx={{ color: "text.secondary" }}>{rows.length} activit{rows.length === 1 ? "y" : "ies"}</Typography>
                  </Box>
                  <Box sx={{ position: "relative", flex: 1, py: 0.5 }}>
                    {rows.map((a, i) => {
                      if (!a.planned_start || !a.planned_due || !domain) return null;
                      const left = pct(ymd(a.planned_start));
                      const width = Math.max(2, pct(ymd(a.planned_due)) - left);
                      const st = barState(a, todayMs);
                      return (
                        <Tooltip
                          key={a.id}
                          title={
                            <Box sx={{ fontSize: 15 }}>
                              <b>{a.title}</b><br />
                              {fmt(a.planned_start)} → {fmt(a.planned_due)} · {st.label}<br />
                              SLA {a.sla_meta?.target_days ?? "?"}d (was {a.sla_meta?.baseline_days ?? "?"}d)
                              {a.gate ? <> · <b>Gate: {a.gate}</b></> : null}
                              {typeof a.slack_days === "number" ? <> · slack {a.slack_days}d</> : null}
                            </Box>
                          }
                        >
                          <Box
                            sx={{
                              position: "absolute",
                              left: `${left}%`,
                              width: `${width}%`,
                              top: 4 + (i % 2) * 20,
                              height: 16,
                              borderRadius: 1,
                              background: st.color,
                              border: a.gate ? "2px solid #9C3232" : "none",
                              opacity: a.done ? 0.55 : 1,
                              cursor: "default",
                              display: "flex",
                              alignItems: "center",
                              px: 0.5,
                              overflow: "hidden",
                            }}
                          >
                            <Typography sx={{ fontSize: 15, color: "#fff", whiteSpace: "nowrap", textOverflow: "ellipsis", overflow: "hidden" }}>
                              {a.title}
                            </Typography>
                          </Box>
                        </Tooltip>
                      );
                    })}
                  </Box>
                </Box>
              );
            })}
          </Box>

          <Typography variant="caption" sx={{ color: "text.secondary", fontStyle: "italic", display: "block", mt: 1 }}>
            Backward-scheduled from go-live. Amber = critical path (zero slack); red border = hard compliance gate (routed &amp; tracked, never auto-closed).
            Effort across all activities: {sched.effort.baseline_days_total}d → {sched.effort.target_days_total}d.
          </Typography>
        </>
      ) : null}
    </ConsolePanel>
  );
}
