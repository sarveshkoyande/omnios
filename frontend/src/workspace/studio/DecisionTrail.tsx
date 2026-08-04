import type { ReactNode } from "react";
import { useState } from "react";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Typography from "@mui/material/Typography";
import Accordion from "@mui/material/Accordion";
import AccordionSummary from "@mui/material/AccordionSummary";
import AccordionDetails from "@mui/material/AccordionDetails";
import { styled } from "@mui/material/styles";
import { glass, indigoTint, tokens, motion, hoverOnly } from "../../theme/tokens";
import type { DecisionItem, DecisionRecord } from "./studioTypes";

/** The reasoning trail: one card per spine stage, laid out as an explicit
 * reasoning path — WHAT WE USED → HOW WE REASONED → WHAT WE REJECTED →
 * THE DECISION → WHAT IT SHAPES. The decision itself is the hero of the card;
 * the numbered steps make "how we got there" legible at a glance. */

const SOURCE_COLOR: Record<string, { bg: string; ink: string }> = {
  internal: { bg: "#EAF0FE", ink: "#2451C4" },
  external: { bg: "#E3F6EE", ink: "#0B6B4C" },
  user: { bg: "#F1EAFB", ink: "#5B21B6" },
};

const RecordCard = styled(Accordion)({
  background: glass.panel,
  border: `1px solid ${indigoTint(0.12)}`,
  borderRadius: `${tokens.radius.md}px !important`,
  boxShadow: "none",
  "&:before": { display: "none" },
  marginBottom: 10,
});

/** The hero: the decision itself, unmissable. */
const DecisionBox = styled(Box)({
  background: tokens.color.primaryContainer,
  borderLeft: `4px solid ${tokens.color.primary}`,
  borderRadius: tokens.radius.sm,
  padding: "12px 16px",
  marginBottom: 16,
});

/** One numbered step on the reasoning path, with a connector line to the next. */
const Step = styled(Box)({
  position: "relative",
  paddingLeft: 40,
  paddingBottom: 18,
  "&:not(:last-of-type)::before": {
    content: '""',
    position: "absolute",
    left: 13,
    top: 28,
    bottom: 0,
    width: 2,
    background: indigoTint(0.15),
  },
});

const StepBadge = styled("span")({
  position: "absolute",
  left: 0,
  top: 0,
  width: 28,
  height: 28,
  borderRadius: "50%",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  fontSize: tokens.fontSize.xs,
  fontWeight: 800,
  background: tokens.color.surface,
  border: `2px solid ${tokens.color.primary}`,
  color: tokens.color.primary,
});

const StepTitle = styled(Typography)({
  fontSize: tokens.fontSize.xs,
  fontWeight: 800,
  letterSpacing: "0.07em",
  textTransform: "uppercase",
  color: tokens.color.inkSecondary,
  marginBottom: 6,
  lineHeight: "28px",
});

/** One chosen thing, as an object: what it is, how big, and what defines it. Replaces the
 *  semicolon-joined string that made a four-segment choice unreadable. */
function DecisionItemCard({ item }: { item: DecisionItem }) {
  const share = typeof item.share_pct === "number" ? item.share_pct : null;
  return (
    <Box
      sx={{
        flex: "1 1 200px",
        minWidth: 0,
        p: 1.5,
        borderRadius: `${tokens.radius.md}px`,
        background: tokens.color.surface,
        border: `1px solid ${item.lead ? tokens.color.primary : tokens.color.outline}`,
      }}
    >
      <Box sx={{ display: "flex", alignItems: "baseline", gap: 0.75, mb: 0.5 }}>
        <Typography sx={{ fontSize: tokens.fontSize.sm, fontWeight: 700, color: tokens.color.text, minWidth: 0 }}>
          {item.label}
        </Typography>
        {item.lead && (
          <Box component="span" sx={{ fontSize: 15, fontWeight: 700, px: 0.75, borderRadius: 1, flex: "0 0 auto", background: tokens.color.primaryContainer, color: tokens.color.onPrimaryContainer }}>
            lead
          </Box>
        )}
      </Box>
      {item.value && (
        <Typography sx={{ fontSize: tokens.fontSize.xs, fontWeight: 700, color: tokens.color.primary }}>
          {item.value}{share !== null ? ` · ${share}%` : ""}
        </Typography>
      )}
      {/* The bar is the fastest read of relative size; without it four segments are four
          numbers the eye has to compare by hand. */}
      {share !== null && (
        <Box sx={{ mt: 0.75, height: 4, borderRadius: tokens.radius.pill, background: indigoTint(0.1), overflow: "hidden" }}>
          <Box sx={{ width: `${Math.min(100, Math.max(0, share))}%`, height: "100%", background: tokens.color.primary }} />
        </Box>
      )}
      {item.criteria && (
        <Typography sx={{ fontSize: tokens.fontSize.xs, color: "text.secondary", mt: 0.75, lineHeight: 1.5 }}>
          {item.criteria}
        </Typography>
      )}
    </Box>
  );
}

/** What this decision rests on and what rests on it — the trail as a graph, not a list. */
function DependencyStrip({ record, onJump }: { record: DecisionRecord; onJump?: (stageId: string) => void }) {
  const deps = record.dependencies ?? [];
  if (!deps.length) return null;
  const rests = deps.filter((d) => d.relation === "depends_on");
  const feeds = deps.filter((d) => d.relation === "feeds_stage");
  const group = (label: string, rows: typeof deps) =>
    rows.length > 0 && (
      <Box sx={{ display: "flex", alignItems: "center", gap: 0.75, flexWrap: "wrap" }}>
        <Typography variant="caption" sx={{ fontWeight: 700, color: "text.secondary" }}>{label}</Typography>
        {rows.map((d) => (
          <Chip
            key={`${d.relation}-${d.stage_id}`}
            size="small"
            variant="outlined"
            label={`${d.stage_id} ${d.stage_name}`}
            onClick={onJump ? () => onJump(d.stage_id) : undefined}
            sx={{
              height: 22,
              fontSize: tokens.fontSize.xs,
              transition: `background ${motion.duration.hover} ${motion.easeOut}, transform ${motion.duration.press} ${motion.easeOut}`,
              ...(onJump
                ? {
                    cursor: "pointer",
                    [hoverOnly]: { "&:hover": { background: indigoTint(0.08) } },
                    "&:active": { transform: "scale(0.96)" },
                  }
                : {}),
            }}
          />
        ))}
      </Box>
    );
  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 0.75, pt: 1, mt: 0.5, borderTop: `1px dashed ${indigoTint(0.18)}` }}>
      {group("Rests on →", rests)}
      {group("Feeds →", feeds)}
    </Box>
  );
}

/** Change a landed decision in place. The options are the union of what was chosen and what
 *  was set aside, which is exactly the option set the original ask offered — reconstructed
 *  from the record so the trail needs no access to the ask itself. */
function ReviseBox({
  record,
  onRevise,
  onClose,
}: {
  record: DecisionRecord;
  onRevise: (sectionId: string, value: string) => Promise<unknown>;
  onClose: () => void;
}) {
  const chosen = (record.decision_items ?? []).map((i) => i.label);
  const all = [...chosen, ...(record.alternatives ?? []).map((a) => a.label)].filter(Boolean);
  const [picked, setPicked] = useState<string[]>(chosen);
  const [saving, setSaving] = useState(false);
  const dependents = (record.dependencies ?? []).filter((d) => d.relation === "feeds_stage").length;
  const toggle = (label: string) =>
    setPicked((prev) => (prev.includes(label) ? prev.filter((l) => l !== label) : [...prev, label]));

  const apply = async () => {
    setSaving(true);
    // Order matters downstream: the FIRST label is the lead segment apply_answer re-aims the
    // whole profile at, so preserve the option order rather than click order.
    const ordered = all.filter((l) => picked.includes(l));
    await onRevise(record.section_id, ordered.join("; "));
    setSaving(false);
    onClose();
  };

  return (
    <Box sx={{ mt: 1.5, p: 1.5, borderRadius: `${tokens.radius.md}px`, background: tokens.color.canvas, border: `1px solid ${tokens.color.outline}` }}>
      <Typography sx={{ fontSize: tokens.fontSize.xs, fontWeight: 800, letterSpacing: "0.07em", textTransform: "uppercase", color: tokens.color.inkSecondary, mb: 1 }}>
        Change this decision
      </Typography>
      <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75, mb: 1.5 }}>
        {all.map((label) => {
          const on = picked.includes(label);
          return (
            <Chip
              key={label}
              size="small"
              label={label}
              onClick={() => toggle(label)}
              sx={{
                height: 26,
                fontSize: tokens.fontSize.xs,
                cursor: "pointer",
                fontWeight: 700,
                background: on ? tokens.color.primary : tokens.color.surface,
                color: on ? "#fff" : tokens.color.text,
                border: `1px solid ${on ? tokens.color.primary : tokens.color.outline}`,
                transition: `background ${motion.duration.hover} ${motion.easeOut}, transform ${motion.duration.press} ${motion.easeOut}`,
                [hoverOnly]: { "&:hover": { background: on ? tokens.color.primaryDark : indigoTint(0.08) } },
                "&:active": { transform: "scale(0.96)" },
              }}
            />
          );
        })}
      </Box>
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap" }}>
        {/* The blast radius is named on the button rather than behind a confirm dialog: the
            cost of the click should be legible before it is paid, not after. */}
        <Button variant="contained" size="small" disabled={picked.length === 0 || saving} onClick={apply}>
          {saving ? "Rebuilding…" : `Apply and re-draft ${dependents} dependent stage${dependents === 1 ? "" : "s"}`}
        </Button>
        <Button variant="text" size="small" onClick={onClose} disabled={saving}>
          Cancel
        </Button>
      </Box>
    </Box>
  );
}

function SourceTag({ source_class }: { source_class: string }) {
  const c = SOURCE_COLOR[source_class] ?? SOURCE_COLOR.internal;
  return (
    <Box component="span" sx={{ fontSize: 15, fontWeight: 700, px: 0.75, py: 0.2, borderRadius: 1, background: c.bg, color: c.ink, flex: "0 0 auto" }}>
      {source_class}
    </Box>
  );
}

export function DecisionTrail({
  records,
  dense,
  onRevise,
}: {
  records: DecisionRecord[];
  dense?: boolean;
  /** Supplied by the workspace; when absent the trail is read-only (e.g. the brief view). */
  onRevise?: (sectionId: string, value: string) => Promise<unknown>;
}) {
  const [editing, setEditing] = useState<string | null>(null);
  if (!records.length) return null;
  // Dependency chips scroll to the record they name. Cheap DOM lookup rather than refs: the
  // cards are keyed by stage_id and may be collapsed or not yet mounted mid-run.
  const jumpToStage = (stageId: string) => {
    document.getElementById(`decision-${stageId}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  };
  return (
    <Box>
      {records.map((r) => {
        const steps: { title: string; body: ReactNode }[] = [];

        if (r.inputs.length > 0) {
          steps.push({
            title: "What we looked at",
            body: (
              <Box>
                {r.inputs.map((inp, i) => (
                  <Box key={i} sx={{ display: "flex", gap: 1, alignItems: "baseline", mb: 0.75 }}>
                    <SourceTag source_class={inp.source_class} />
                    <Typography variant="body2" sx={{ color: tokens.color.text }}>
                      <b>{inp.label}:</b> {inp.value}{" "}
                      <Box component="span" sx={{ color: "text.secondary", fontStyle: "italic" }}>({inp.source})</Box>
                    </Typography>
                  </Box>
                ))}
              </Box>
            ),
          });
        }

        steps.push({
          title: "How we reasoned",
          body: (
            <Box>
              <Chip size="small" variant="outlined" label={r.framework} sx={{ height: 24, fontSize: tokens.fontSize.xs, mb: 0.75 }} />
              {/* pre-line: the record appends a decision-specific sentence after a blank
                  line, and HTML would otherwise collapse it into the framework prose. */}
              <Typography variant="body2" sx={{ color: tokens.color.text, lineHeight: 1.65, whiteSpace: "pre-line" }}>
                {r.rationale}
              </Typography>
            </Box>
          ),
        });

        if (r.alternatives?.length > 0) {
          steps.push({
            title: "What we set aside",
            body: (
              <Box>
                {r.alternatives.map((a, i) => (
                  <Box key={i} sx={{ display: "flex", gap: 1, alignItems: "baseline", mb: 0.5 }}>
                    <Box component="span" className="material-symbols-outlined" sx={{ fontSize: "16px !important", color: tokens.color.inkSecondary, flex: "0 0 auto", position: "relative", top: 2 }}>
                      block
                    </Box>
                    <Typography variant="body2" sx={{ color: "text.secondary" }}>
                      <b style={{ color: tokens.color.text }}>{a.label}</b> — {a.why_rejected}
                    </Typography>
                  </Box>
                ))}
              </Box>
            ),
          });
        }

        const items = r.decision_items ?? [];
        const agentRec = r.agent_recommendation;
        const overrode =
          Boolean(agentRec?.label) &&
          items.length > 0 &&
          agentRec!.label.trim().toLowerCase() !== items[0].label.trim().toLowerCase();

        return (
          <RecordCard key={r.stage_id} id={`decision-${r.stage_id}`} defaultExpanded={!dense}>
            <AccordionSummary expandIcon={<span className="material-symbols-outlined">expand_more</span>}>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap", minWidth: 0 }}>
                <Chip size="small" label={r.stage_id} sx={{ height: 24, fontWeight: 700, fontSize: tokens.fontSize.xs }} />
                <Typography sx={{ fontWeight: 700, fontSize: tokens.fontSize.sm }}>{r.stage_name}</Typography>
                <Typography sx={{ fontSize: tokens.fontSize.sm, color: "text.secondary", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 360 }}>
                  {r.decision}
                </Typography>
                {r.answered_by_user && (
                  <Chip size="small" color="secondary" variant="outlined" label="your call" sx={{ height: 24, fontSize: 15 }} />
                )}
              </Box>
            </AccordionSummary>
            <AccordionDetails sx={{ pt: 0.5 }}>
              <DecisionBox>
                <Typography sx={{ fontSize: tokens.fontSize.xs, fontWeight: 800, letterSpacing: "0.07em", textTransform: "uppercase", color: tokens.color.primary, mb: 0.5 }}>
                  {r.answered_by_user ? "The decision — your call" : "The decision"}
                </Typography>
                {/* Objects when the backend gave us objects; the joined string only as a
                    fallback for stages with nothing structured to show. */}
                {items.length > 0 ? (
                  <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
                    {items.map((item) => (
                      <DecisionItemCard key={item.label} item={item} />
                    ))}
                  </Box>
                ) : (
                  <Typography sx={{ fontSize: tokens.fontSize.md, fontWeight: 700, color: tokens.color.onPrimaryContainer, lineHeight: 1.5 }}>
                    {r.decision}
                  </Typography>
                )}
                {overrode && (
                  <Typography sx={{ fontSize: tokens.fontSize.xs, color: tokens.color.onPrimaryContainer, mt: 1.25, lineHeight: 1.5 }}>
                    Agent recommended <b>{agentRec!.label}</b>
                    {agentRec!.reason ? ` — ${agentRec!.reason}` : ""}
                  </Typography>
                )}
              </DecisionBox>

              {r.panel_scope?.headline && (
                <Typography sx={{ fontSize: tokens.fontSize.xs, color: "text.secondary", mb: 1.5, lineHeight: 1.5 }}>
                  {r.panel_scope.headline}
                  {r.panel_scope.confidence ? ` · ${r.panel_scope.confidence}` : ""}
                  {r.panel_scope.caveat ? ` · ${r.panel_scope.caveat}` : ""}
                </Typography>
              )}

              {steps.map((s, i) => (
                <Step key={s.title}>
                  <StepBadge>{i + 1}</StepBadge>
                  <StepTitle>{s.title}</StepTitle>
                  {s.body}
                </Step>
              ))}

              {r.feeds.length > 0 && (
                <Box sx={{ display: "flex", alignItems: "center", gap: 0.75, flexWrap: "wrap", pt: 0.5, borderTop: `1px dashed ${indigoTint(0.18)}` }}>
                  <Typography variant="caption" sx={{ fontWeight: 700, color: "text.secondary" }}>
                    Shapes in the brief →
                  </Typography>
                  {r.feeds.map((f) => (
                    <Chip key={f} size="small" variant="outlined" color="primary" label={f} sx={{ height: 24, fontSize: tokens.fontSize.xs }} />
                  ))}
                </Box>
              )}

              <DependencyStrip record={r} onJump={jumpToStage} />

              {onRevise && r.editable && (
                editing === r.stage_id ? (
                  <ReviseBox record={r} onRevise={onRevise} onClose={() => setEditing(null)} />
                ) : (
                  <Button
                    size="small"
                    variant="text"
                    onClick={() => setEditing(r.stage_id)}
                    sx={{ mt: 1, px: 0, fontSize: tokens.fontSize.xs }}
                  >
                    Change this decision
                  </Button>
                )
              )}
            </AccordionDetails>
          </RecordCard>
        );
      })}
    </Box>
  );
}
