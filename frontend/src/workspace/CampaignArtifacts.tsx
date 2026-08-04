import { useCallback, useEffect, useState } from "react";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import ButtonGroup from "@mui/material/ButtonGroup";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import { ConsolePanel } from "../components/ConsolePanel";
import { DecisionTrail } from "./studio/DecisionTrail";
import { glass, indigoTint, tokens } from "../theme/tokens";
import { campaignBriefDownloadUrl, generateOrchestrationTasks, getCampaignArtifacts } from "../api";
import type { CampaignArtifactsPayload, JourneyDiagramPayload, JourneyMap } from "./types";

/** The Planning stage's two linked artifacts, replacing the old hardcoded simplified
 * summary + 30-section plan as the default view: the Campaign Strategy (the decision
 * trail — how and why each call was made) and the Campaign Brief (the operational
 * projection: agency-brief anatomy + first-class Measurement Plan and Risk Register).
 * Approving the brief seeds Engagement Orchestration with the activity checklist. */

const Section = styled(Box)({
  background: glass.panel,
  border: `1px solid ${indigoTint(0.12)}`,
  borderRadius: tokens.radius.md,
  padding: "14px 16px",
  marginBottom: 12,
});

const Eyebrow = styled(Typography)({
  fontSize: 15,
  fontWeight: 700,
  letterSpacing: "0.07em",
  textTransform: "uppercase",
  color: tokens.color.primary,
  marginBottom: 6,
});

const SEV_COLOR: Record<string, "error" | "warning" | "default"> = { critical: "error", monitor: "warning" };

/* ------------------------- The journey ------------------------- *
 * Two views of the same server-side projection (strategy/journey_brief.py): the rendered
 * flowchart, and the step table under it. The table is not a nicety — it is what survives
 * when the image does not (see JourneyPicture), and it is the form the .docx/.pdf download
 * carries, so the two must agree. */

/** Colour per step kind, matching the classDefs the backend puts in the Mermaid source so
 *  the table and the picture read as one diagram. */
const STEP_TONE: Record<string, { bg: string; ink: string }> = {
  send: { bg: tokens.color.primaryContainer, ink: tokens.color.primary },
  followup: { bg: tokens.color.surface, ink: tokens.color.inkSecondary },
  decision: { bg: tokens.color.warningSoft, ink: tokens.color.warning },
  branch: { bg: tokens.color.warningSoft, ink: tokens.color.warning },
  wait: { bg: tokens.color.canvas, ink: tokens.color.inkSoft },
  entry: { bg: tokens.color.canvas, ink: tokens.color.inkSecondary },
  exit: { bg: tokens.color.successSoft, ink: tokens.color.successInk },
  closure: { bg: tokens.color.canvas, ink: tokens.color.inkSecondary },
};

function JourneyPicture({ diagram }: { diagram?: JourneyDiagramPayload }) {
  // mermaid.ink is a third-party host: it can be blocked by a corporate proxy, be down, or
  // simply be slower than the brief. None of those may leave a blank hole where the journey
  // should be, so a failed load falls through to the step table below rather than retrying.
  const [failed, setFailed] = useState(false);
  if (!diagram?.image_url || failed) {
    return diagram?.image_url ? (
      <Typography variant="caption" sx={{ color: "text.secondary", fontStyle: "italic", display: "block", my: 1 }}>
        The journey diagram couldn't be fetched from mermaid.ink. The full step list is below.
      </Typography>
    ) : null;
  }
  return (
    <Box
      sx={{
        my: 1.5,
        p: 1.5,
        border: `1px solid ${indigoTint(0.12)}`,
        borderRadius: tokens.radius.md,
        background: tokens.color.surface,
        overflowX: "auto",
      }}
    >
      <Box
        component="img"
        src={diagram.image_url}
        alt="Engagement journey flowchart"
        loading="lazy"
        onError={() => setFailed(true)}
        sx={{ display: "block", maxWidth: "100%", height: "auto", margin: "0 auto" }}
      />
    </Box>
  );
}

function JourneySteps({ j }: { j?: JourneyMap }) {
  const steps = j?.steps ?? [];
  if (steps.length === 0) return null;
  return (
    <Table size="small" sx={{ mt: 1 }}>
      <TableHead>
        <TableRow>
          <TableCell sx={{ width: 64 }}>Day</TableCell>
          <TableCell sx={{ width: 96 }}>Step</TableCell>
          <TableCell>What happens</TableCell>
          <TableCell>Channel</TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {steps.map((s) => {
          const tone = STEP_TONE[s.kind] ?? STEP_TONE.entry;
          return (
            <TableRow key={s.id}>
              <TableCell sx={{ color: "text.secondary" }}>{s.day ?? "—"}</TableCell>
              <TableCell>
                <Chip
                  size="small"
                  label={s.kind_label}
                  sx={{ height: 22, fontSize: 15, fontWeight: 700, background: tone.bg, color: tone.ink }}
                />
              </TableCell>
              <TableCell>
                <Typography variant="body2" sx={{ fontWeight: s.is_comms ? 700 : 400 }}>{s.label}</Typography>
                {s.detail && (
                  <Typography variant="caption" sx={{ color: "text.secondary" }}>{s.detail}</Typography>
                )}
              </TableCell>
              <TableCell sx={{ color: "text.secondary", fontSize: 15 }}>{s.channel || "—"}</TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}

function JourneyDiagram({ j, diagram }: { j?: JourneyMap; diagram?: JourneyDiagramPayload }) {
  if (!j?.steps?.length) return null;
  return (
    <Box sx={{ my: 1.5 }}>
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1, flexWrap: "wrap" }}>
        <Typography sx={{ fontSize: tokens.fontSize.sm, fontWeight: 700 }}>How the journey runs</Typography>
        {j.touchpoint_count ? (
          <Chip size="small" variant="outlined" label={`${j.touchpoint_count} touchpoints`} sx={{ height: 24 }} />
        ) : null}
        {j.duration_days ? (
          <Chip size="small" variant="outlined" label={`${j.duration_days}-day journey`} sx={{ height: 24 }} />
        ) : null}
      </Box>

      <JourneyPicture diagram={diagram} />

      {(j.entry?.length ?? 0) > 0 && (
        <Box sx={{ mt: 1 }}>
          <Typography variant="caption" sx={{ fontWeight: 700 }}>Entry criteria</Typography>
          <Rows items={j.entry ?? []} />
        </Box>
      )}

      <JourneySteps j={j} />

      {j.decision_logic && j.decision_logic.length > 0 && (
        <Box sx={{ mt: 1.5 }}>
          <Typography variant="caption" sx={{ fontWeight: 700 }}>Decision logic</Typography>
          {j.decision_logic.map((d, i) => (
            <Typography key={i} variant="body2" sx={{ display: "flex", gap: 0.75, mb: 0.3 }}>
              <span style={{ color: tokens.color.warning }}>◇</span>
              <span><b>{d.condition}</b> — {d.outcome}</span>
            </Typography>
          ))}
        </Box>
      )}
      {j.operational_rules && j.operational_rules.length > 0 && (
        <Box sx={{ mt: 1 }}>
          <Typography variant="caption" sx={{ fontWeight: 700 }}>Operating rules</Typography>
          <Rows items={j.operational_rules} />
        </Box>
      )}
    </Box>
  );
}

function Rows({ items }: { items: string[] }) {
  return (
    <>
      {items.filter(Boolean).map((t, i) => (
        <Typography key={i} variant="body2" sx={{ display: "flex", gap: 0.75, mb: 0.4 }}>
          <span style={{ color: tokens.color.primary }}>•</span> {t}
        </Typography>
      ))}
    </>
  );
}

function audienceFilterLabel(rule: string) {
  return rule.replace(/^(Entry|Segment):\s*/i, "");
}

/** Download the brief as a document. Split control: the main button takes the common case
 *  (.docx, editable by the brand team) and the caret offers PDF, so the default path is one
 *  click and neither format is buried. */
function DownloadBrief({ projectId }: { projectId: string }) {
  const [menuAnchor, setMenuAnchor] = useState<HTMLElement | null>(null);

  const download = (format: "docx" | "pdf") => {
    setMenuAnchor(null);
    // An <a download> rather than fetch+blob: the file is generated per request and can be
    // megabytes, and this way a failed export surfaces as the server's own error page
    // instead of a silent no-op in a promise.
    const link = document.createElement("a");
    link.href = campaignBriefDownloadUrl(projectId, format);
    link.rel = "noopener";
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  return (
    <>
      <ButtonGroup size="small" variant="outlined">
        <Button
          onClick={() => download("docx")}
          startIcon={<span className="material-symbols-outlined" style={{ fontSize: 17 }}>download</span>}
        >
          Download brief
        </Button>
        <Button
          onClick={(e) => setMenuAnchor(e.currentTarget)}
          aria-label="Choose brief download format"
          sx={{ px: 0.5, minWidth: 32 }}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 17 }}>arrow_drop_down</span>
        </Button>
      </ButtonGroup>
      <Menu anchorEl={menuAnchor} open={Boolean(menuAnchor)} onClose={() => setMenuAnchor(null)}>
        <MenuItem onClick={() => download("docx")}>Word (.docx)</MenuItem>
        <MenuItem onClick={() => download("pdf")}>PDF</MenuItem>
      </Menu>
    </>
  );
}

function StrategyDecisionTrailPanel({ data, sx }: { data: CampaignArtifactsPayload; sx?: object }) {
  return (
    <ConsolePanel id="decision-trail-anchor" title="Campaign Strategy - decision trail" icon="psychology" collapsible sx={sx}>
      <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mb: 1.5 }}>
        {data.strategy.note}
      </Typography>
      {data.strategy.source_summary && (
        <Section>
          <Eyebrow>Source basis</Eyebrow>
          <Typography variant="body2" sx={{ mb: 0.75 }}>{data.strategy.source_summary.basis}</Typography>
          {data.strategy.source_summary.positioning && (
            <Typography variant="body2" sx={{ mb: 0.5 }}><b>Positioning:</b> {data.strategy.source_summary.positioning}</Typography>
          )}
          {data.strategy.source_summary.csfs.length > 0 && (
            <Rows items={data.strategy.source_summary.csfs.map((c) => `CSF: ${c}`)} />
          )}
        </Section>
      )}
      <DecisionTrail records={data.strategy.records} dense />
    </ConsolePanel>
  );
}

export function CampaignArtifacts({
  projectId,
  onSeeded,
  refreshToken = 0,
}: {
  projectId: string;
  onSeeded?: () => void;
  /** Bumped by the workspace when the plan ctx changes (e.g. persona rebalance) — triggers a refetch. */
  refreshToken?: number;
}) {
  const [data, setData] = useState<CampaignArtifactsPayload | null>(null);
  const [err, setErr] = useState<"no-plan" | "failed" | null>(null);
  const [seeding, setSeeding] = useState(false);
  const [seeded, setSeeded] = useState(false);
  const [approveErr, setApproveErr] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setErr(null);
    // The backend persists the just-finished run's ctx in a `finally` block AFTER it streams
    // the "done" event that triggers this mount, so the very first fetch can race a save that
    // hasn't landed yet. Retry a few times before treating it as a real failure.
    const attempt = (n: number) => {
      getCampaignArtifacts(projectId)
        .then((d) => { if (!cancelled) setData(d); })
        .catch((e: unknown) => {
          if (cancelled) return;
          if (n < 4) setTimeout(() => attempt(n + 1), 800);
          else setErr(String((e as Error)?.message ?? "").includes("400") ? "no-plan" : "failed");
        });
    };
    attempt(0);
    return () => { cancelled = true; };
  }, [projectId, refreshToken]);

  const approve = useCallback(() => {
    setSeeding(true);
    setApproveErr(false);
    generateOrchestrationTasks(projectId)
      .then(() => { setSeeded(true); onSeeded?.(); })
      .catch(() => setApproveErr(true))
      .finally(() => setSeeding(false));
  }, [projectId, onSeeded]);

  // Only a 400 genuinely means "no plan yet"; anything else is a transient/compose failure and
  // telling a user who just watched 19/19 sections land to "run Stage 1 first" is simply wrong.
  if (err)
    return (
      <Typography sx={{ color: "text.secondary", fontStyle: "italic" }}>
        {err === "no-plan"
          ? "Artifacts unavailable — run Stage 1 first."
          : "Couldn’t load the campaign brief just now. It stays saved with the plan — reopen this tab to retry."}
      </Typography>
    );
  if (!data) return <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}><CircularProgress size={22} /></Box>;

  const strategyData = data;
  const b = data.brief;

  return (
    <Box>
      {(() => { const data = strategyData; const sourceSummary = data.strategy.source_summary ?? { basis: "", positioning: "", csfs: [] }; return false ? (
        <>
      {/* ------------------------------ Campaign Strategy ------------------------------ */}
      <ConsolePanel id="decision-trail-anchor" title="Campaign Strategy — decision trail" icon="psychology" collapsible sx={{ mb: 3 }}>
        <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mb: 1.5 }}>
          {data.strategy.note}
        </Typography>
        {sourceSummary && (
          <Section>
            <Eyebrow>Source basis</Eyebrow>
            <Typography variant="body2" sx={{ mb: 0.75 }}>{sourceSummary.basis}</Typography>
            {sourceSummary.positioning && (
              <Typography variant="body2" sx={{ mb: 0.5 }}><b>Positioning:</b> {sourceSummary.positioning}</Typography>
            )}
            {sourceSummary.csfs.length > 0 && (
              <Rows items={sourceSummary.csfs.map((c) => `CSF: ${c}`)} />
            )}
          </Section>
        )}
        <DecisionTrail records={data.strategy.records} dense />
      </ConsolePanel>
        </>
      ) : null; })()}

      {/* ------------------------------ Campaign Brief --------------------------------- */}
      <ConsolePanel
        id="campaign-brief-anchor"
        title={`Campaign Brief — ${b.header.brand || "brand"}`}
        icon="assignment_turned_in"
        action={
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <DownloadBrief projectId={projectId} />
            <Button size="small" variant="contained" onClick={approve} disabled={seeding || seeded}>
              {seeding ? <CircularProgress size={16} sx={{ color: "#fff" }} /> : seeded ? "Sent to Orchestration ✓" : "Approve → Orchestration"}
            </Button>
          </Box>
        }
      >
        {approveErr && (
          <Typography variant="caption" sx={{ color: "error.main", display: "block", mb: 1 }}>
            Couldn't send this to Orchestration — the plan may still be saving. Give it a moment and try again.
          </Typography>
        )}
        <Box sx={{ display: "flex", gap: 0.75, flexWrap: "wrap", mb: 2 }}>
          {b.header.therapy_area && <Chip size="small" label={b.header.therapy_area} sx={{ height: 24 }} />}
          {b.header.lifecycle && <Chip size="small" variant="outlined" label={b.header.lifecycle} sx={{ height: 24 }} />}
          <Chip size="small" variant="outlined" label={`v${b.version} · ${b.generated_at}`} sx={{ height: 24 }} />
        </Box>

        {b.snapshot && (
          <Section>
            {[
              ["Campaign objective", b.snapshot.objective],
              ["Brand", b.snapshot.brand],
              ["Therapy area", b.snapshot.therapy_area],
              ["Target audience", b.snapshot.target_audience],
              ["Why this campaign", b.snapshot.reason],
            ]
              .filter(([, value]) => Boolean(value))
              .map(([label, value]) => (
                <Box key={label} sx={{ display: "flex", gap: 1.5, mb: 0.6, alignItems: "baseline" }}>
                  <Typography
                    variant="caption"
                    sx={{ fontWeight: 700, color: "text.secondary", minWidth: 132, flexShrink: 0 }}
                  >
                    {label}
                  </Typography>
                  <Typography variant="body2" sx={{ fontWeight: label === "Campaign objective" ? 700 : 400 }}>
                    {value}
                  </Typography>
                </Box>
              ))}
          </Section>
        )}

        <Section>
          <Eyebrow>Purpose</Eyebrow>
          <Typography variant="body2" sx={{ mb: 0.75 }}><b>{b.purpose.program_context}</b></Typography>
          <Typography variant="body2" sx={{ mb: 0.75 }}>{b.purpose.summary}</Typography>
          {b.purpose.trigger_logic.length > 0 && (
            <><Typography variant="caption" sx={{ fontWeight: 700 }}>Trigger / entry logic</Typography>
            <Rows items={b.purpose.trigger_logic} /></>
          )}
        </Section>

        <Section>
          <Eyebrow>Objective</Eyebrow>
          {b.objective.pillar && <Chip size="small" color="primary" variant="outlined" label={`pillar · ${b.objective.pillar}`} sx={{ height: 24, mb: 0.75 }} />}
          <Typography variant="body2" sx={{ mb: 0.75 }}>{b.objective.statement}</Typography>
          <Rows items={b.objective.leading_indicators.map((k) => `Leading indicator: ${k}`)} />
        </Section>

        <Section>
          <Eyebrow>Target audience & eligibility</Eyebrow>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap", mb: 1.5 }}>
            <Typography variant="body2" sx={{ fontWeight: 700, color: tokens.color.ink }}>
              {b.audience.segment}
            </Typography>
            {b.audience.eligibility_rules.filter(Boolean).map((rule) => (
              <Chip
                key={rule}
                size="small"
                variant="outlined"
                label={audienceFilterLabel(rule)}
                sx={{
                  height: 24,
                  borderRadius: 999,
                  background: tokens.color.primaryContainer,
                  borderColor: indigoTint(0.18),
                  color: tokens.color.ink,
                  fontSize: 15,
                  fontWeight: 600,
                  "& .MuiChip-label": { px: 1 },
                }}
              />
            ))}
          </Box>
          {(b.audience.segments?.length ?? 0) > 0 && (
            <Box
              sx={{
                display: "grid",
                gridTemplateColumns: { xs: "1fr", md: `repeat(${Math.min(b.audience.segments.length, 3)}, minmax(0, 1fr))` },
                gap: 1.25,
                my: 1,
              }}
            >
              {b.audience.segments.map((s, i) => (
                <Box
                  key={`${s.name}-${i}`}
                  sx={{
                    minWidth: 0,
                    border: `1px solid ${indigoTint(0.14)}`,
                    borderRadius: tokens.radius.sm,
                    background: tokens.color.surface,
                    p: 1.5,
                    display: "flex",
                    flexDirection: "column",
                    gap: 0.9,
                  }}
                >
                  <Box sx={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 1 }}>
                    <Typography variant="body2" sx={{ fontWeight: 800, color: tokens.color.ink, lineHeight: 1.25 }}>
                      {s.name}
                    </Typography>
                    <Chip
                      size="small"
                      title={s.volume_note ?? undefined}
                      // A counted panel headcount prints exactly; only an apportioned
                      // estimate keeps the "~".
                      label={
                        s.volume
                          ? s.volume_exact
                            ? `${s.volume.toLocaleString()} HCPs`
                            : `~${s.volume.toLocaleString()}`
                          : "Size TBD"
                      }
                      sx={{
                        height: 22,
                        flex: "0 0 auto",
                        background: tokens.color.successSoft,
                        color: tokens.color.successInk,
                        fontSize: 15,
                        fontWeight: 800,
                      }}
                    />
                  </Box>
                  <Typography variant="body2" sx={{ color: "text.secondary", lineHeight: 1.45 }}>
                    {s.profile}
                  </Typography>
                  {s.key_characteristics.length > 0 && (
                    <Box sx={{ display: "flex", gap: 0.5, flexWrap: "wrap", mt: "auto" }}>
                      {s.key_characteristics.map((k) => (
                        <Chip
                          key={k}
                          size="small"
                          variant="outlined"
                          label={k}
                          sx={{ height: 24, maxWidth: "100%", fontSize: 15, "& .MuiChip-label": { overflow: "hidden", textOverflow: "ellipsis" } }}
                        />
                      ))}
                    </Box>
                  )}
                </Box>
              ))}
            </Box>
          )}
          <Typography variant="caption" sx={{ color: "text.secondary", fontStyle: "italic" }}>{b.audience.consent_note}</Typography>
        </Section>

        <Section>
          <Eyebrow>Communication strategy</Eyebrow>
          {b.comms_strategy.belief_shift && <Typography variant="body2" sx={{ mb: 0.75 }}>Belief shift: <b>{b.comms_strategy.belief_shift}</b></Typography>}
          {b.comms_strategy.core_claim && <Typography variant="body2" sx={{ mb: 0.75 }}>Core claim: <b>{b.comms_strategy.core_claim}</b></Typography>}
          {(b.comms_strategy.message_detail?.length ?? 0) > 0 ? (
            <>
              <Typography variant="caption" sx={{ fontWeight: 700 }}>Message ladder</Typography>
              {b.comms_strategy.message_detail.map((m, i) => (
                <Box key={i} sx={{ mb: 0.75 }}>
                  <Typography variant="body2" sx={{ display: "flex", gap: 0.75 }}>
                    <span style={{ color: tokens.color.primary, fontWeight: 700 }}>{i + 1}.</span> <b>{m.topic}</b>
                  </Typography>
                  {m.supporting.map((s, k) => (
                    <Typography key={k} variant="body2" sx={{ pl: 3, color: "text.secondary" }}>{s}</Typography>
                  ))}
                </Box>
              ))}
            </>
          ) : b.comms_strategy.message_ladder.length > 0 && (
            <><Typography variant="caption" sx={{ fontWeight: 700 }}>Message ladder</Typography>
            <Rows items={b.comms_strategy.message_ladder} /></>
          )}
          <Typography variant="caption" sx={{ fontWeight: 700 }}>Tone guardrails</Typography>
          <Rows items={b.comms_strategy.tone_guardrails} />
        </Section>

        <Section>
          <Eyebrow>Deliverables</Eyebrow>
          <Table size="small">
            <TableHead><TableRow><TableCell>Asset</TableCell><TableCell>Variants</TableCell><TableCell>Notes</TableCell></TableRow></TableHead>
            <TableBody>
              {b.deliverables.map((d, i) => (
                <TableRow key={i}>
                  <TableCell sx={{ fontWeight: 600 }}>{d.asset}</TableCell>
                  <TableCell>{d.variants}</TableCell>
                  <TableCell sx={{ color: "text.secondary", fontSize: 15 }}>{d.notes}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Section>

        <Section>
          <Eyebrow>Channel & journey</Eyebrow>
          {b.channel_journey.anchor && <Typography variant="body2" sx={{ mb: 0.5 }}>Anchor: <b>{b.channel_journey.anchor}</b></Typography>}
          <Box sx={{ display: "flex", gap: 0.5, flexWrap: "wrap", mb: 0.75 }}>
            {b.channel_journey.mix.map((m) => (
              <Chip key={m.channel} size="small" variant="outlined" label={`${m.channel} ${m.pct}%`} sx={{ height: 24 }} />
            ))}
          </Box>
          {b.channel_journey.journey?.summary && (
            <Typography variant="body2" sx={{ mb: 0.5 }}>{b.channel_journey.journey.summary}</Typography>
          )}
          <JourneyDiagram j={b.channel_journey.journey} diagram={b.journey_diagram} />
          <Typography variant="caption" sx={{ color: "text.secondary" }}>{b.channel_journey.cadence_note}</Typography>
        </Section>

        <Section>
          <Eyebrow>Measurement plan</Eyebrow>
          <Rows items={b.measurement_plan.kpis} />
          <Typography variant="caption" sx={{ display: "block", mt: 0.5 }}>{b.measurement_plan.link_matrix_note}</Typography>
          <Typography variant="caption" sx={{ display: "block" }}>Test design: {b.measurement_plan.test_design}</Typography>
        </Section>

        <Section>
          <Eyebrow>Scope & review assumptions</Eyebrow>
          <Typography variant="body2" sx={{ mb: 0.5 }}><b>{b.scope_review.ladder}</b></Typography>
          <Typography variant="caption" sx={{ display: "block", color: "text.secondary" }}>{b.scope_review.rounds_note}</Typography>
          <Typography variant="caption" sx={{ display: "block", color: "text.secondary" }}>{b.scope_review.change_control}</Typography>
        </Section>

        <Section>
          <Eyebrow>Risk register</Eyebrow>
          {b.risk_register.map((r, i) => (
            <Box key={i} sx={{ display: "flex", gap: 1, alignItems: "baseline", mb: 0.75 }}>
              <Chip size="small" color={SEV_COLOR[r.severity] ?? "default"} label={r.severity} sx={{ height: 24, fontSize: 15, flex: "0 0 auto" }} />
              <Typography variant="body2"><b>{r.risk}</b> — <span style={{ color: tokens.color.inkSoft }}>{r.mitigation}</span></Typography>
            </Box>
          ))}
        </Section>

        <Section>
          <Eyebrow>Assumptions & mandatories</Eyebrow>
          <Rows items={b.assumptions} />
        </Section>

        <Section>
          <Eyebrow>Timeline & approvals</Eyebrow>
          <Typography variant="body2" sx={{ mb: 0.5 }}><b>{b.timeline.window}</b> — {b.timeline.note}</Typography>
          <Box sx={{ display: "flex", gap: 0.5, flexWrap: "wrap" }}>
            {b.approvals.map((a) => (
              <Chip key={a.role} size="small" variant="outlined" label={`${a.role}: ${a.name || "unassigned"}`} sx={{ height: 24 }} />
            ))}
          </Box>
        </Section>

        {/* Technical detail lives after the campaign, not before it: sources, review path and
            the decision trail are needed to audit the brief, not to read it. */}
        <Section>
          <Eyebrow>Technical detail</Eyebrow>
          {b.technical_appendix && b.technical_appendix.review_and_pv.length > 0 && (
            <Rows items={b.technical_appendix.review_and_pv} />
          )}
          {b.technical_appendix && b.technical_appendix.technical_decisions.length > 0 && (
            <Rows
              items={b.technical_appendix.technical_decisions.map(
                (d) => `${d.stage_name}: ${d.decision}`,
              )}
            />
          )}
          {b.source_summary && (
            <>
              <Typography variant="caption" sx={{ fontWeight: 700, display: "block", mt: 1 }}>
                Source basis
              </Typography>
              <Typography variant="body2" sx={{ mb: 0.75 }}>{b.source_summary.basis}</Typography>
              {b.source_summary.captured_fields.length > 0 && (
                <Box sx={{ display: "flex", gap: 0.5, flexWrap: "wrap", mb: 0.75 }}>
                  {b.source_summary.captured_fields.map((f) => (
                    <Chip key={`${f.label}-${f.value}`} size="small" variant="outlined" label={`${f.label}: ${f.value}`} sx={{ height: 24 }} />
                  ))}
                </Box>
              )}
              {b.source_summary.evidence.length > 0 && (
                <>
                  <Typography variant="caption" sx={{ fontWeight: 700 }}>Strategic evidence anchors</Typography>
                  <Rows items={b.source_summary.evidence} />
                </>
              )}
              {b.source_summary.guardrails.length > 0 && (
                <>
                  <Typography variant="caption" sx={{ fontWeight: 700 }}>Strategic guardrails</Typography>
                  <Rows items={b.source_summary.guardrails} />
                </>
              )}
            </>
          )}
        </Section>

        <Typography variant="caption" sx={{ color: "text.secondary", fontStyle: "italic" }}>
          Traceability: every section above projects from a named decision record in the Campaign Strategy —
          {" "}{b.traceability.map((t) => t.stage_id).join(" · ")}.
        </Typography>
      </ConsolePanel>
      <StrategyDecisionTrailPanel data={data} sx={{ mt: 3 }} />
    </Box>
  );
}
