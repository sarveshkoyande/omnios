import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Typography from "@mui/material/Typography";
import TextField from "@mui/material/TextField";
import Slider from "@mui/material/Slider";
import Tooltip from "@mui/material/Tooltip";
import { ConsolePanel } from "../../../components/ConsolePanel";
import { indigoTint, shade, tokens } from "../../../theme/tokens";
import { COVERAGE_STYLE } from "./derive";
import type { Coverage, LaunchVerdict } from "./types";

/** Verdict colours — a three-state signal, not brand decoration. */
const STATUS_STYLE: Record<LaunchVerdict["status"], { label: string; color: string; bg: string; icon: string }> = {
  "on-track": { label: "On track", color: "#1B7A34", bg: "#E7F4EA", icon: "check_circle" },
  "at-risk": { label: "At risk", color: "#B4552F", bg: "#FDF1EC", icon: "warning" },
  blocked: { label: "Blocked", color: "#A11F35", bg: "#FBEAED", icon: "block" },
};

const ORDER: Coverage[] = ["reuse", "adapt", "build", "blocked"];

/**
 * The answer the stage exists to give: can we launch, and what is in the way. Everything
 * below it on the page is the evidence for this panel, not a separate destination.
 */
export function LaunchStatus({
  verdict,
  goLive,
  onGoLive,
  parallelTeams,
  onParallelTeams,
}: {
  verdict: LaunchVerdict;
  goLive: string;
  onGoLive: (v: string) => void;
  parallelTeams: number;
  onParallelTeams: (v: number) => void;
}) {
  const st = STATUS_STYLE[verdict.status];
  const { totals } = verdict;
  const readyPct = totals.total ? Math.round((totals.reuse / totals.total) * 100) : 0;

  return (
    <ConsolePanel
      id="ops2-status"
      title="Launch status"
      icon="flag"
      sx={{ mb: 3 }}
      action={
        <Box sx={{ display: "flex", gap: 1.5, alignItems: "center" }}>
          <TextField
            size="small"
            type="date"
            label="Go-live"
            value={goLive}
            onChange={(e) => onGoLive(e.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
            sx={{ width: 165 }}
          />
          <Tooltip title="How many workstreams can genuinely run at once. No capacity data exists in the app, so this is an assumption you set — never a measured fact.">
            <Box sx={{ width: 175 }}>
              <Typography variant="caption" sx={{ color: "text.secondary", display: "block", lineHeight: 1.2 }}>
                Parallel workstreams: <b>{parallelTeams}</b>
              </Typography>
              <Slider
                size="small"
                min={1}
                max={8}
                value={parallelTeams}
                onChange={(_e, v) => onParallelTeams(v as number)}
                sx={{ mt: -0.25 }}
              />
            </Box>
          </Tooltip>
        </Box>
      }
    >
      {/* The verdict itself. */}
      <Box
        sx={{
          display: "flex", alignItems: "center", gap: 2, flexWrap: "wrap",
          p: 2, mb: 2, borderRadius: tokens.radius.md, background: st.bg,
        }}
      >
        <span className="material-symbols-outlined" style={{ fontSize: 34, color: st.color }}>{st.icon}</span>
        <Box sx={{ minWidth: 0 }}>
          <Typography sx={{ fontSize: 21, fontWeight: 800, color: st.color, lineHeight: 1.2 }}>
            {st.label} · {verdict.headline}
          </Typography>
          <Typography variant="body2" sx={{ color: "text.secondary", mt: 0.25 }}>
            {verdict.remainingDays} business days of work remain against {verdict.availableDays} available before go-live.
          </Typography>
        </Box>
        <Box sx={{ ml: "auto", textAlign: "right" }}>
          <Typography sx={{ fontSize: 30, fontWeight: 800, lineHeight: 1, color: st.color }}>
            {verdict.projectedOverrunDays > 0 ? `+${verdict.projectedOverrunDays}d` : "0d"}
          </Typography>
          <Typography variant="caption" sx={{ color: "text.secondary" }}>
            {verdict.projectedOverrunDays > 0 ? "projected overrun" : "no projected overrun"}
          </Typography>
        </Box>
      </Box>

      {/* Coverage split — the four states, as one bar. */}
      <Box sx={{ display: "flex", height: 12, borderRadius: 6, overflow: "hidden", mb: 1.25 }}>
        {ORDER.map((c) => {
          const n = totals[c];
          if (!n) return null;
          return (
            <Tooltip key={c} title={`${COVERAGE_STYLE[c].label}: ${n}`}>
              <Box sx={{ flex: n, background: COVERAGE_STYLE[c].color }} />
            </Tooltip>
          );
        })}
      </Box>
      <Box sx={{ display: "flex", gap: 2.5, flexWrap: "wrap", mb: 2.5 }}>
        {ORDER.map((c) => (
          <Box key={c} sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
            <Box sx={{ width: 11, height: 11, borderRadius: 0.5, background: COVERAGE_STYLE[c].color }} />
            <Typography variant="caption" sx={{ color: "text.secondary" }}>
              <b style={{ color: COVERAGE_STYLE[c].color }}>{totals[c]}</b> {COVERAGE_STYLE[c].label.toLowerCase()}
            </Typography>
          </Box>
        ))}
        <Typography variant="caption" sx={{ color: "text.secondary", ml: "auto" }}>
          {totals.total} deliverables · {readyPct}% already covered · ~{verdict.effortSaved} days saved by reuse
        </Typography>
      </Box>

      {/* Ranked blockers — the "why not" half of the question. */}
      {verdict.blockers.length > 0 ? (
        <Box>
          <Typography variant="caption" sx={{ fontWeight: 700, color: "text.secondary", letterSpacing: "0.06em" }}>
            WHAT IS IN THE WAY
          </Typography>
          {verdict.blockers.map((b, i) => (
            <Box
              key={b.title}
              sx={{
                display: "flex", gap: 1.25, alignItems: "flex-start", py: 1.15,
                borderBottom: i < verdict.blockers.length - 1 ? `1px dashed ${shade(0.1)}` : "none",
              }}
            >
              <Chip size="small" label={i + 1} sx={{ height: 22, minWidth: 22, fontWeight: 700, background: indigoTint(0.12) }} />
              <Box sx={{ minWidth: 0 }}>
                <Typography variant="body2" sx={{ fontWeight: 700 }}>{b.title}</Typography>
                <Typography variant="caption" sx={{ color: "text.secondary" }}>{b.detail}</Typography>
              </Box>
            </Box>
          ))}
        </Box>
      ) : (
        <Typography variant="body2" sx={{ color: "text.secondary", fontStyle: "italic" }}>
          Nothing blocking. Every deliverable is covered or scheduled inside the window.
        </Typography>
      )}
    </ConsolePanel>
  );
}
