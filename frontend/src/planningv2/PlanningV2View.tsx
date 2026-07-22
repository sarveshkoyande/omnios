import { useRef, useState } from "react";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import CircularProgress from "@mui/material/CircularProgress";
import { GlassPanel, SectionCard, BrandButton, PillChip, DefinitionRow } from "../glass/primitives";
import { AgentBubble, NarrationLine } from "../workspace/ChatBubble";
import { tokens } from "../theme/tokens";
import { QuestionCard } from "./QuestionCard";
import {
  answerPlanningQuestion,
  finishPlanningRun,
  startPlanningRun,
  type PlanningRunPayload,
} from "./api";

const TACTICAL_SECTION_LABELS: Record<string, string> = {
  flighting: "Flighting",
  field_approach: "Field Approach",
  targeting_matrix: "Targeting Matrix",
  media_flighting: "Media Flighting",
  trigger_based_engagement: "Trigger-Based Engagement",
  content_inventory: "Content Inventory",
  congress_scientific_exchange: "Congress & Scientific Exchange",
  peer_to_peer: "Peer-to-Peer",
  nurse_app_education: "Nurse/APP Education",
  account_strategy: "Account Strategy",
  account_focus: "Account Focus",
  testing_enablement_digital: "Testing & Digital Enablement",
};

export function PlanningV2View() {
  const [run, setRun] = useState<PlanningRunPayload | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<"upload" | "finish" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const onUpload = async (file: File) => {
    setBusy("upload");
    setError(null);
    try {
      const payload = await startPlanningRun(file);
      setRun(payload);
      setAnswers({});
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed.");
    } finally {
      setBusy(null);
    }
  };

  const onAnswer = async (field: string, value: string) => {
    if (!run) return;
    setAnswers((prev) => ({ ...prev, [field]: value }));
    try {
      await answerPlanningQuestion(run.id, field, value);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save that answer.");
    }
  };

  const onFinish = async () => {
    if (!run) return;
    setBusy("finish");
    setError(null);
    try {
      const payload = await finishPlanningRun(run.id);
      setRun(payload);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Synthesis failed.");
    } finally {
      setBusy(null);
    }
  };

  const questions = run?.questions ?? [];
  const allAnswered = questions.every((q) => answers[q.field]);
  const isDone = run?.stage === "validated" || run?.stage === "handed_off";

  return (
    <Box sx={{ display: "flex", gap: 3, p: 3, maxWidth: 1400, mx: "auto" }}>
      {/* Left: chat column — upload, then the ranked question set */}
      <Box sx={{ flex: "0 0 420px", display: "flex", flexDirection: "column", gap: 2 }}>
        <SectionCard icon="hub" label="Planning Engine v2">
          <Typography variant="body2" sx={{ color: "text.secondary", lineHeight: 1.6 }}>
            Upload a strategic plan (PDF, PPTX, or DOCX). The engine reads it, enriches it
            against the knowledge graph and market signals, and asks only what it genuinely
            couldn't work out on its own.
          </Typography>
        </SectionCard>

        {!run && (
          <GlassPanel tier="0" sx={{ p: 3, textAlign: "center", border: `1px dashed ${tokens.color.primary}` }}>
            <input
              ref={fileInput}
              type="file"
              accept=".pdf,.pptx,.docx"
              hidden
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) onUpload(f);
                e.target.value = "";
              }}
            />
            {busy === "upload" ? (
              <Box sx={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 1.5, py: 2 }}>
                <CircularProgress size={18} />
                <Typography variant="body2">Ingesting, extracting, enriching, analyzing gaps…</Typography>
              </Box>
            ) : (
              <BrandButton onClick={() => fileInput.current?.click()}>Upload strategic plan</BrandButton>
            )}
          </GlassPanel>
        )}

        {error && (
          <GlassPanel tier="0" sx={{ p: 2, border: `1px solid ${tokens.color.danger}` }}>
            <Typography variant="body2" sx={{ color: tokens.color.danger }}>{error}</Typography>
          </GlassPanel>
        )}

        {run && (
          <NarrationLine>
            {run.brand ? `Reading for ${run.brand}. ` : ""}
            {questions.length > 0
              ? `${questions.length} question${questions.length === 1 ? "" : "s"} to close the gaps that matter — ${run.assumptions.length} other assumption${run.assumptions.length === 1 ? "" : "s"} inferred silently.`
              : "No true gaps found — everything needed was already inferable."}
          </NarrationLine>
        )}

        {questions.map((g, i) => (
          <QuestionCard
            key={g.field}
            gap={g}
            rank={i + 1}
            total={questions.length}
            answered={answers[g.field]}
            onAnswer={(value) => onAnswer(g.field, value)}
          />
        ))}

        {run && !isDone && (
          <Box sx={{ mt: 1 }}>
            <BrandButton arrow onClick={onFinish} disabled={busy === "finish"}>
              {busy === "finish" ? "Synthesizing…" : allAnswered ? "Generate tactical plan & BRB" : "Generate now (unanswered → default)"}
            </BrandButton>
          </Box>
        )}
      </Box>

      {/* Right: the synthesized plan + compliance report */}
      <Box sx={{ flex: 1, display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
        {!isDone && (
          <GlassPanel tier="0" sx={{ p: 4, textAlign: "center", color: "text.secondary" }}>
            <Typography variant="body2">
              {run ? "Answer the questions on the left, then generate the plan." : "Upload a strategic plan to begin."}
            </Typography>
          </GlassPanel>
        )}

        {isDone && run?.compliance && (
          <SectionCard
            icon="verified"
            label="Compliance Report"
            action={
              <PillChip
                dot={run.compliance.findings.every((f) => f.severity !== "blocker")}
                label={run.compliance.findings.filter((f) => f.severity === "blocker").length === 0 ? "No blockers" : `${run.compliance.findings.filter((f) => f.severity === "blocker").length} blocker(s)`}
                sx={{ background: run.compliance.findings.some((f) => f.severity === "blocker") ? "rgba(220,38,38,0.1)" : undefined }}
              />
            }
          >
            {run.compliance.findings.length === 0 ? (
              <Typography variant="body2" sx={{ color: "text.secondary" }}>No findings.</Typography>
            ) : (
              run.compliance.findings.map((f, i) => (
                <Box key={i} sx={{ py: 1, borderBottom: i < run.compliance!.findings.length - 1 ? "1px solid rgba(0,0,0,0.06)" : "none" }}>
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                    <PillChip
                      label={f.severity}
                      sx={{ background: f.severity === "blocker" ? "rgba(220,38,38,0.12)" : "rgba(217,119,6,0.12)", color: f.severity === "blocker" ? "#b91c1c" : "#b45309", fontWeight: 700 }}
                    />
                    <Typography variant="caption" sx={{ fontWeight: 700 }}>{f.rule}</Typography>
                    <Typography variant="caption" sx={{ color: "text.secondary" }}>@ {f.location}</Typography>
                  </Box>
                  <Typography variant="body2" sx={{ mt: 0.5 }}>{f.message}</Typography>
                </Box>
              ))
            )}
          </SectionCard>
        )}

        {isDone && run?.tactical_plan && (
          <SectionCard icon="map" label="Tactical Plan">
            <Typography variant="body2" sx={{ mb: 1.5 }}>{run.tactical_plan.strategic_recap}</Typography>
            <DefinitionRow label="Investment thesis" value={run.tactical_plan.investment_thesis} />
            <DefinitionRow
              label="Patient strategy"
              value={run.tactical_plan.patient_strategy?.gated ? "Gated" : "Active"}
              hint={run.tactical_plan.patient_strategy?.gating_logic}
            />
            {run.tactical_plan.omnichannel_strategy && run.tactical_plan.omnichannel_strategy.length > 0 && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="caption" sx={{ fontWeight: 700, color: "primary.main" }}>OMNICHANNEL STRATEGY</Typography>
                <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, mt: 1 }}>
                  {run.tactical_plan.omnichannel_strategy.map((c, i) => (
                    <PillChip key={i} label={`${c.channel} · ${c.branded_or_unbranded}`} />
                  ))}
                </Box>
              </Box>
            )}
            {Object.entries(TACTICAL_SECTION_LABELS).map(([key, label]) => {
              const section = run.tactical_plan?.[key] as { summary?: string; items?: unknown[] } | undefined;
              if (!section?.summary) return null;
              return (
                <Box key={key} sx={{ mt: 2 }}>
                  <Typography variant="caption" sx={{ fontWeight: 700, color: "primary.main" }}>{label.toUpperCase()}</Typography>
                  <Typography variant="body2" sx={{ mt: 0.5 }}>{section.summary}</Typography>
                </Box>
              );
            })}
            {run.tactical_plan.measurement && run.tactical_plan.measurement.length > 0 && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="caption" sx={{ fontWeight: 700, color: "primary.main" }}>MEASUREMENT</Typography>
                {run.tactical_plan.measurement.map((m, i) => (
                  <Box key={i} sx={{ mt: 1 }}>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>{m.csf_id}</Typography>
                    {Object.entries(m.targets).map(([k, v]) => (
                      <Typography key={k} variant="caption" sx={{ display: "block", color: "text.secondary" }}>
                        {k}: {v.is_placeholder ? "[placeholder — requires brand-team data]" : String(v.value)} — {v.note}
                      </Typography>
                    ))}
                  </Box>
                ))}
              </Box>
            )}
            {run.tactical_plan.appendices?.guardrails_recap && run.tactical_plan.appendices.guardrails_recap.length > 0 && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="caption" sx={{ fontWeight: 700, color: "primary.main" }}>GUARDRAILS</Typography>
                {run.tactical_plan.appendices.guardrails_recap.map((g, i) => (
                  <Typography key={i} variant="body2" sx={{ mt: 0.5 }}>• {g}</Typography>
                ))}
              </Box>
            )}
          </SectionCard>
        )}

        {isDone && run?.brb && (
          <SectionCard icon="assignment" label="Business Requirements Brief">
            <Typography variant="body2" sx={{ mb: 1.5 }}>{run.brb.initiative_summary}</Typography>
            {run.brb.workstreams?.map((ws, i) => (
              <AgentBubble key={i} sx={{ maxWidth: "100%", mb: 1.5 }}>
                <Typography variant="body2" sx={{ fontWeight: 700 }}>{ws.name}</Typography>
                <Typography variant="caption" sx={{ color: "text.secondary" }}>
                  → {ws.tactical_sections.join(", ")}
                </Typography>
                <DefinitionRow label="Owner" value={ws.proposed_owning_team} />
                <DefinitionRow label="SLA" value={ws.suggested_sla} />
                <DefinitionRow label="Parallelizable" value={ws.parallelizable ? "Yes" : "No"} />
                {ws.dependencies.length > 0 && (
                  <DefinitionRow label="Dependencies" value={ws.dependencies.join("; ")} />
                )}
              </AgentBubble>
            ))}
          </SectionCard>
        )}
      </Box>
    </Box>
  );
}
