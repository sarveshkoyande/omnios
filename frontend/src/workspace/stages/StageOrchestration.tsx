import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import { PlanTable } from "./PlanTable";
import { StageHead } from "./StageHead";
import { ConsolePanel } from "../../components/ConsolePanel";
import { glass, indigoTint, shade, tokens } from "../../theme/tokens";
import type { PlanResult } from "../types";

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

export function StageOrchestration({ result }: { result: PlanResult | null }) {
  if (!result) {
    return <ConsolePanel><Typography sx={{ color: "text.secondary", fontStyle: "italic" }}>Complete Stage 1 to orchestrate engagement.</Typography></ConsolePanel>;
  }
  const mj = result.stage_2_4_micro_journeys ?? { journeys: [] };
  const bam = result.stage_2_4_bam_chart ?? {};
  const m = result.stage_2_4_strategy?.messaging_architecture ?? {};
  const mf = result.stage_2_4_message_flow ?? { key_messages: [] };
  const ppnpp = result.stage_2_4_pp_npp ?? [];
  const chsel = result.stage_5_channel_selection?.channels ?? [];

  const prioRank: Record<string, number> = { High: 0, Medium: 1, Low: 2 };
  const nbc = [...chsel].sort((a, b) => (prioRank[a.brand_priority ?? ""] ?? 3) - (prioRank[b.brand_priority ?? ""] ?? 3));

  return (
    <Box>
      <StageHead
        icon="account_tree"
        title="Engagement Orchestration"
        blurb="The plan becomes an orchestrated program: what triggers an engagement, which channel answers it, and in what order the message ladder unfolds."
      />

      <ConsolePanel sx={{ mb: 3 }}>
        <Typography variant="overline">Orchestration objective — belief shift</Typography>
        <BeliefShift>
          <BeliefPill tone="a">{m.current_belief || "—"}</BeliefPill>
          <span className="material-symbols-outlined">east</span>
          <BeliefPill tone="b">{m.desired_belief || "—"}</BeliefPill>
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
          Ranked by brand priority — the orchestration engine's channel-selection order.
        </Typography>
        <PlanTable>
          <thead><tr><th>#</th><th>Channel</th><th>Priority</th><th>Availability</th><th>Affinity</th></tr></thead>
          <tbody>
            {nbc.map((c, i) => (
              <tr key={i}>
                <td>{i + 1}</td>
                <td><b>{c.channel}</b></td>
                <td>{c.brand_priority && <Chip size="small" color={PRIO_COLOR[c.brand_priority] ?? "default"} label={c.brand_priority} />}</td>
                <td>{c.availability ?? "—"}</td>
                <td>{c.preference_affinity ?? "—"}</td>
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
    </Box>
  );
}
