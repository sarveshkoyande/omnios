import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Typography from "@mui/material/Typography";
import Tooltip from "@mui/material/Tooltip";
import { styled } from "@mui/material/styles";
import { ConsolePanel } from "../../../components/ConsolePanel";
import { glass, indigoTint, shade, tokens } from "../../../theme/tokens";
import { COVERAGE_STYLE, RUN_STEPS } from "./derive";
import type { Deliverable, Risk } from "./types";

/** Severity is a functional three-state signal, not brand colour. */
const SEV: Record<Risk["severity"], { color: string; bg: string }> = {
  high: { color: "#A11F35", bg: "#FBEAED" },
  medium: { color: "#B4552F", bg: "#FDF1EC" },
  low: { color: "#2451C4", bg: "#E8EEFB" },
};

const StepCard = styled(Box)<{ ready?: boolean }>(({ ready }) => ({
  display: "flex",
  gap: 10,
  alignItems: "flex-start",
  padding: "10px 12px",
  borderRadius: tokens.radius.sm,
  background: ready ? glass.content : indigoTint(0.05),
  border: `1px solid ${indigoTint(ready ? 0.14 : 0.08)}`,
  opacity: ready ? 1 : 0.78,
}));

/**
 * The 14-step setup run. Steps marked "needs input" are not unfinished UI — they are the
 * steps that cannot be computed until the app has a source for data it does not hold today
 * (approval records, team capacity, a rate card). Showing which is which is the point.
 */
export function RunPanel() {
  const ready = RUN_STEPS.filter((s) => s.state === "ready").length;
  return (
    <ConsolePanel
      id="ops2-run"
      title="The setup run"
      icon="conveyor_belt"
      collapsible
      sx={{ mb: 3 }}
      action={
        <Chip size="small" label={`${ready} of ${RUN_STEPS.length} computable today`} sx={{ height: 24, fontWeight: 700 }} />
      }
    >
      <Typography variant="body2" sx={{ color: "text.secondary", mb: 2 }}>
        Fourteen steps, each grounded in the plan, gated by one decision, producing one artefact —
        the same shape as the Stage 1 plan studio. Dimmed steps are blocked on data the app has no
        source for yet.
      </Typography>
      <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(310px, 1fr))", gap: 1.25 }}>
        {RUN_STEPS.map((s) => (
          <StepCard key={s.n} ready={s.state === "ready"}>
            <Box
              sx={{
                flex: "0 0 auto", width: 24, height: 24, borderRadius: "50%",
                display: "grid", placeItems: "center", fontSize: 13, fontWeight: 700,
                color: "#fff", background: s.state === "ready" ? tokens.color.primary : tokens.color.inkSoft,
              }}
            >
              {s.n}
            </Box>
            <Box sx={{ minWidth: 0 }}>
              <Typography variant="body2" sx={{ fontWeight: 700, lineHeight: 1.3 }}>{s.title}</Typography>
              <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mt: 0.15 }}>
                {s.question}
              </Typography>
              <Box sx={{ display: "flex", gap: 0.6, mt: 0.6, flexWrap: "wrap", alignItems: "center" }}>
                <Chip size="small" variant="outlined" label={s.agent} sx={{ height: 19, fontSize: 11.5 }} />
                {s.needsNote && (
                  <Tooltip title={s.needsNote}>
                    <Chip size="small" color="warning" label="Needs input" sx={{ height: 19, fontSize: 11.5 }} />
                  </Tooltip>
                )}
              </Box>
            </Box>
          </StepCard>
        ))}
      </Box>
    </ConsolePanel>
  );
}

/** Launch waves: readiness is never binary, so the answer is what ships when. */
export function WavesPanel({ waves }: { waves: { name: string; note: string; items: Deliverable[] }[] }) {
  return (
    <ConsolePanel id="ops2-waves" title="Launch sequence" icon="stacked_line_chart" sx={{ mb: 3 }}>
      <Typography variant="body2" sx={{ color: "text.secondary", mb: 2 }}>
        Campaigns rarely launch all at once. Treating it as one switch hides the fact that most of
        it could be live earlier.
      </Typography>
      {waves.map((w) => {
        const days = w.items.filter((i) => i.coverage !== "reuse").reduce((s, i) => s + i.effortDays, 0);
        return (
          <Box
            key={w.name}
            sx={{
              p: 1.75, mb: 1.25, borderRadius: tokens.radius.sm,
              background: glass.content, border: `1px solid ${indigoTint(0.12)}`,
            }}
          >
            <Box sx={{ display: "flex", alignItems: "baseline", gap: 1.25, flexWrap: "wrap" }}>
              <Typography sx={{ fontWeight: 700, fontSize: 15 }}>{w.name}</Typography>
              <Chip size="small" label={`${w.items.length} items · ${days}d`} sx={{ height: 21, fontSize: 12.5 }} />
            </Box>
            <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mt: 0.25, mb: 1 }}>
              {w.note}
            </Typography>
            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.6 }}>
              {w.items.slice(0, 10).map((i) => (
                <Chip
                  key={i.id}
                  size="small"
                  label={i.title}
                  sx={{
                    height: 21, fontSize: 12,
                    color: COVERAGE_STYLE[i.coverage].color,
                    background: COVERAGE_STYLE[i.coverage].bg,
                    maxWidth: 300,
                  }}
                />
              ))}
              {w.items.length > 10 && (
                <Chip size="small" variant="outlined" label={`+${w.items.length - 10} more`} sx={{ height: 21, fontSize: 12 }} />
              )}
            </Box>
          </Box>
        );
      })}
    </ConsolePanel>
  );
}

/** Risks read off the same derivation, so the register opens populated rather than empty. */
export function RiskPanel({ risks }: { risks: Risk[] }) {
  return (
    <ConsolePanel id="ops2-risks" title="Risks & issues" icon="report" sx={{ mb: 3 }}>
      <Typography variant="body2" sx={{ color: "text.secondary", mb: 2 }}>
        Blockers are what has already gone wrong. These are what might — found by the same pass
        that built the deliverables list, not typed into an empty template.
      </Typography>
      {risks.map((r, i) => (
        <Box
          key={r.id}
          sx={{
            display: "flex", gap: 1.25, alignItems: "flex-start", py: 1.4,
            borderBottom: i < risks.length - 1 ? `1px dashed ${shade(0.1)}` : "none",
          }}
        >
          <Chip
            size="small"
            label={r.severity}
            sx={{ height: 22, fontWeight: 700, fontSize: 12, textTransform: "capitalize", color: SEV[r.severity].color, background: SEV[r.severity].bg }}
          />
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Typography variant="body2" sx={{ fontWeight: 700 }}>{r.title}</Typography>
            <Typography variant="caption" sx={{ color: "text.secondary" }}>{r.detail}</Typography>
          </Box>
          <Typography variant="caption" sx={{ flex: "0 0 190px", textAlign: "right", color: "text.secondary" }}>
            {r.owner}
          </Typography>
        </Box>
      ))}
    </ConsolePanel>
  );
}

/** What the design needs that the app cannot supply yet — stated on the page, not hidden. */
export function GapsPanel() {
  const gaps = [
    ["Approval & claim data", "Steps 3 and 4 depend on knowing what is approved and when it expires. Nothing in the app holds this, so blocked items stay blocked.", true],
    ["Team capacity data", "The projection divides work by an assumed number of parallel workstreams. Real capacity would replace the slider above."],
    ["Journey locking", "Step 1 needs a freeze-this-version concept on the flow planner's output, or the list is derived against a moving target."],
    ["One market or many", "Multiple markets multiply steps 3, 4 and 12 — and turn the deliverables list from a list into a matrix."],
  ] as const;
  return (
    <ConsolePanel id="ops2-gaps" title="What this needs that we don't have" icon="help" sx={{ mb: 3 }}>
      <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 1.5 }}>
        {gaps.map(([title, detail, flagged]) => (
          <Box
            key={title}
            sx={{
              p: 1.75, borderRadius: tokens.radius.sm,
              background: flagged ? "#FDF1EC" : glass.content,
              border: `1px solid ${flagged ? "#F0D5C8" : indigoTint(0.12)}`,
            }}
          >
            <Typography sx={{ fontWeight: 700, fontSize: 15, mb: 0.5 }}>{title}</Typography>
            <Typography variant="caption" sx={{ color: "text.secondary" }}>{detail}</Typography>
            {flagged && (
              <Typography variant="caption" sx={{ display: "block", mt: 1, fontWeight: 700, color: "#B4552F", letterSpacing: "0.06em" }}>
                BIGGEST OPEN QUESTION
              </Typography>
            )}
          </Box>
        ))}
      </Box>
    </ConsolePanel>
  );
}
