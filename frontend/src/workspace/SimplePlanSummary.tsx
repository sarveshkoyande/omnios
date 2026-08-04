import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import { glass, tokens } from "../theme/tokens";

/**
 * Simplified Brand Engagement Plan — replaces the full generated plan document
 * (PlanSummaryCard/PlanDocument, ~30+ sections of HTML) with a single-screen,
 * card-based campaign brief: not just a reformatted strategy recap, but the
 * operational fields the next stages (Engagement Orchestration, Campaign
 * Operations) actually need — journey + entry/exit criteria, the tactic list
 * with messaging/audience/channel/tagging, segmentation/filtration criteria,
 * and a flighting timeline. Sourced from the uploaded 2026 Strategic Plan and
 * 2026 Tactical Plan documents (Oncomyra/talrenimab) — 2026-07-18.
 *
 * Static content for now; if this becomes the standing replacement, the next
 * step is deriving these fields from whatever plan the agent actually
 * generates rather than hardcoding one brand's data.
 */

const CSF_COLOR = {
  info: { rail: tokens.color.info, soft: tokens.color.infoSoft, ink: tokens.color.infoInk },
  brand: { rail: tokens.color.secondary, soft: "#F1EAFB", ink: "#5B21B6" },
  success: { rail: tokens.color.success, soft: tokens.color.successSoft, ink: tokens.color.successInk },
} as const;

const Card = styled(Box)({
  background: glass.panel,
  border: glass.border,
  borderRadius: tokens.radius.md,
  boxShadow: glass.shadow,
});

const RailCard = styled(Box)<{ rail: string }>(({ rail }) => ({
  background: glass.panel,
  border: glass.border,
  borderLeft: `4px solid ${rail}`,
  borderRadius: tokens.radius.md,
  padding: "16px 18px",
  display: "flex",
  flexDirection: "column",
  gap: 6,
}));

const Eyebrow = styled(Typography)({
  fontSize: tokens.fontSize.xs,
  fontWeight: 700,
  letterSpacing: "0.07em",
  textTransform: "uppercase",
  color: tokens.color.inkFaint,
});

const CSFS = [
  {
    n: 1,
    color: CSF_COLOR.info,
    title: "Win the testing battle",
    body: "Drive universal FGFR2 NGS testing at diagnosis; enable liquid-first with tissue reflex; partner with pathology and molecular tumor boards.",
  },
  {
    n: 2,
    color: CSF_COLOR.brand,
    title: "Convert evidence to consideration",
    body: "Lead with CLARITY-01 OS/PFS/ORR and fusion-partner-agnostic response, always with fair balance; differentiate the ADC mechanism.",
  },
  {
    n: 3,
    color: CSF_COLOR.success,
    title: "Enable confident management",
    body: "Turn safety into manageability via monitoring algorithms and special-population confidence (renal, hepatic, cardiac, elderly).",
  },
] as const;

const EVIDENCE = [
  { label: "Median OS", value: "12.8 vs 9.1 mo", detail: "HR 0.72 · p=0.007" },
  { label: "Median PFS", value: "7.0 vs 4.2 mo", detail: "HR 0.58 · p<0.001" },
  { label: "ORR", value: "42.1% vs 18.4%", detail: "vs FOLFOX · p<0.001" },
] as const;

// Target audience: 3 account archetypes (Business Review, strategic plan) plus
// the 2x2 filtration matrix used to prioritize accounts within them (Targeting,
// tactical plan) — together these ARE the segmentation/filtration criteria.
const ARCHETYPES = [
  { name: "Academic / NCI-designated", detail: "Highest FGFR2 testing rates, molecular tumor boards. Role: deepen scientific engagement, generate real-world experience." },
  { name: "High-volume community", detail: "Largest share of iCCA patients treated; testing least consistent. Role: drive testing-at-diagnosis behavior and management confidence." },
  { name: "Integrated delivery networks (IDN)", detail: "Pathway- and protocol-driven. Role: embed reflex FGFR2 testing into standing order sets." },
] as const;

const FILTRATION_QUADRANTS = [
  { priority: "Priority 1 — Activate testing", rule: "High iCCA volume · Low FGFR2 testing rate", action: "Field + pathology engagement to activate reflex testing", color: CSF_COLOR.info },
  { priority: "Priority 2 — Convert & manage", rule: "High iCCA volume · High FGFR2 testing rate", action: "Evidence + management enablement to convert identified patients", color: CSF_COLOR.brand },
  { priority: "Nurture via omnichannel", rule: "Low iCCA volume · Low FGFR2 testing rate", action: "Omnichannel testing education, minimal field footprint", color: CSF_COLOR.success },
  { priority: "Maintain — low-touch", rule: "Low iCCA volume · High FGFR2 testing rate", action: "Low-touch account maintenance", color: { rail: tokens.color.inkFaint, soft: "#EEF0F4", ink: tokens.color.inkSoft } },
] as const;

// Journey: the trigger-based engagement model from the tactical plan — each
// branch's entry criterion (the Event) and exit/next-step criterion (the
// Action) define the actual orchestration logic for Stage 2.
const JOURNEY = [
  { signal: "Testing signal", entry: "HCP engages testing content or downloads the testing guide", exit: "Serve fusion-partner-agnostic selection content; offer pathology support", csf: "CSF1", color: CSF_COLOR.info },
  { signal: "Evidence signal", entry: "HCP views the CLARITY-01 data page", exit: "Follow with the safety/management asset; offer an MSL connection", csf: "CSF2/3", color: CSF_COLOR.brand },
  { signal: "Congress signal", entry: "HCP attends a relevant session or booth (opt-in)", exit: "Send the congress data recap with full ISI", csf: "CSF2", color: CSF_COLOR.success },
] as const;

// Tactics: the content-inventory table from the tactical plan, extended with
// channel + tagging so it's directly usable by Campaign Operations. "Tagging"
// = whether the asset carries a brand claim and therefore needs ISI/fair-
// balance tagging, or is unbranded and must NOT carry one.
const TACTICS = [
  { name: "FGFR2 testing guide", stage: "Identification", audience: "HCP / Pathologist", channel: "Field, Peer", tag: "unbranded" },
  { name: "Disease-education module", stage: "Awareness", audience: "HCP", channel: "Search, Endemic media", tag: "unbranded" },
  { name: "CLARITY-01 evidence summary", stage: "Evidence evaluation", audience: "HCP", channel: "HCP website, Email", tag: "branded" },
  { name: "Fusion-partner-agnostic selection aid", stage: "Patient identification", audience: "HCP", channel: "HCP website", tag: "branded" },
  { name: "AE-management guide", stage: "Safety / management", audience: "HCP / Nurse-APP", channel: "Field, Nurse programs", tag: "unbranded" },
  { name: "Special-population briefs", stage: "Treatment discussion", audience: "Medical", channel: "Medical / MSL", tag: "medical" },
  { name: "MOA explainer", stage: "Clinical consideration", audience: "HCP / Medical", channel: "Congress, Web", tag: "branded" },
  { name: "Congress data recap", stage: "Re-engagement", audience: "HCP", channel: "Congress, Email", tag: "branded" },
] as const;

const TAG_STYLE = {
  branded: { label: "Branded — ISI tag required", bg: tokens.color.warningSoft, ink: tokens.color.warningInk },
  unbranded: { label: "Unbranded — no brand tag", bg: tokens.color.successSoft, ink: tokens.color.successInk },
  medical: { label: "Non-promotional (medical)", bg: tokens.color.infoSoft, ink: tokens.color.infoInk },
} as const;

const CHANNELS = [
  { name: "Search", csf: "CSF1/2" },
  { name: "Endemic HCP media", csf: "CSF1/2" },
  { name: "Rep-triggered email", csf: "CSF2/3" },
  { name: "HCP website", csf: "CSF2/3" },
  { name: "Peer platforms", csf: "CSF1/2" },
  { name: "Medical (MSL/MI)", csf: "CSF2/3" },
] as const;

// Timeline: quarterly flighting intensity, straight from the tactical plan's
// Media Flighting slide — this is "what is the date planned" at the
// granularity the source document actually supports (quarters, not days).
const FLIGHTING = [
  { band: "Unbranded testing education", q: [3, 3, 2, 1] },
  { band: "Branded evidence media", q: [2, 3, 3, 2] },
  { band: "Management / nurse-APP enablement", q: [1, 2, 3, 3] },
  { band: "Congress bursts", q: [1, 2, 2, 1] },
] as const;
const DOT = ["", "●", "●●", "●●●"];

const FIELD_STEPS = ["Open", "Evidence", "Manage", "Refer"] as const;

const GUARDRAILS = [
  "No dosing or drug-interaction claims until PI resolves the source conflicts.",
  "First-line / combination data: medical channels only, never promotional.",
  "Commercial–medical firewall maintained across every channel.",
  "Fair balance and full ISI travel with every branded efficacy claim.",
  "Patient tactics are gated — no approved PI/ISI yet; unbranded disease/testing awareness only.",
];

export function SimplePlanSummary() {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      {/* Header */}
      <Card sx={{ p: 3 }}>
        <Eyebrow>Campaign brief · simplified</Eyebrow>
        <Typography variant="h3" sx={{ mt: 0.5 }}>Oncomyra™ (talrenimab)</Typography>
        <Typography variant="body2" sx={{ color: "text.secondary", mt: 0.5 }}>
          FGFR2-directed antibody–drug conjugate · previously treated FGFR2 fusion-positive advanced cholangiocarcinoma (iCCA)
        </Typography>
        <Box sx={{ display: "flex", gap: 2, mt: 2 }}>
          <Box sx={{ flex: 1, p: 2, borderRadius: `${tokens.radius.sm}px`, background: tokens.color.accentSurface }}>
            <Eyebrow sx={{ color: tokens.color.primary }}>Identify</Eyebrow>
            <Typography variant="body2" sx={{ mt: 0.5 }}>Make FGFR2 fusion testing routine at diagnosis so every eligible patient is found.</Typography>
          </Box>
          <Box sx={{ flex: 1, p: 2, borderRadius: `${tokens.radius.sm}px`, background: tokens.color.accentSurface }}>
            <Eyebrow sx={{ color: tokens.color.secondary }}>Establish</Eyebrow>
            <Typography variant="body2" sx={{ mt: 0.5 }}>Position Oncomyra as the overall-survival-supported FGFR2-directed choice at progression.</Typography>
          </Box>
        </Box>
      </Card>

      {/* Target audience & filtration criteria */}
      <Box>
        <Eyebrow sx={{ mb: 1 }}>Target audience & filtration criteria</Eyebrow>
        <Box sx={{ display: "flex", gap: 2, mb: 2 }}>
          {ARCHETYPES.map((a) => (
            <Card key={a.name} sx={{ flex: 1, p: 2 }}>
              <Typography sx={{ fontWeight: 700, fontSize: tokens.fontSize.sm }}>{a.name}</Typography>
              <Typography variant="body2" sx={{ color: "text.secondary", mt: 0.5 }}>{a.detail}</Typography>
            </Card>
          ))}
        </Box>
        <Card sx={{ p: 2.5 }}>
          <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mb: 1.5 }}>
            Segment accounts on two filters — iCCA patient volume and FGFR2 testing rate — then route each quadrant to its own tactic mix.
          </Typography>
          <Box sx={{ display: "flex", gap: 1.5, flexWrap: "wrap" }}>
            {FILTRATION_QUADRANTS.map((q) => (
              <RailCard key={q.priority} rail={q.color.rail} sx={{ flex: "1 1 220px" }}>
                <Typography sx={{ fontWeight: 700, fontSize: tokens.fontSize.sm }}>{q.priority}</Typography>
                <Chip size="small" label={q.rule} sx={{ alignSelf: "flex-start", background: q.color.soft, color: q.color.ink, fontWeight: 600 }} />
                <Typography variant="body2" sx={{ color: "text.secondary" }}>{q.action}</Typography>
              </RailCard>
            ))}
          </Box>
        </Card>
      </Box>

      {/* Journey: entry / exit criteria */}
      <Box>
        <Eyebrow sx={{ mb: 1 }}>Journey — entry & exit criteria</Eyebrow>
        <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
          {JOURNEY.map((j) => (
            <Card key={j.signal} sx={{ p: 2, display: "flex", alignItems: "center", gap: 2 }}>
              <Chip size="small" label={j.signal} sx={{ background: j.color.soft, color: j.color.ink, fontWeight: 700, flex: "0 0 auto" }} />
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography variant="caption" sx={{ color: tokens.color.inkFaint }}>ENTRY</Typography>
                <Typography variant="body2">{j.entry}</Typography>
              </Box>
              <Typography sx={{ color: tokens.color.inkFaint, flex: "0 0 auto" }}>→</Typography>
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography variant="caption" sx={{ color: tokens.color.inkFaint }}>EXIT / NEXT STEP</Typography>
                <Typography variant="body2">{j.exit}</Typography>
              </Box>
              <Chip size="small" variant="outlined" label={j.csf} sx={{ flex: "0 0 auto" }} />
            </Card>
          ))}
        </Box>
        <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mt: 1 }}>
          Shared guardrail: respect consent and frequency caps; never push patient-facing or investigational content into promotional channels.
        </Typography>
      </Box>

      {/* Tactics: count, messaging, audience, channel, tagging */}
      <Box>
        <Eyebrow sx={{ mb: 1 }}>Tactics — {TACTICS.length} assets</Eyebrow>
        <Card sx={{ overflow: "hidden" }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 700 }}>Tactic</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Journey stage / message</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Audience</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Channel</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Tagging</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {TACTICS.map((t) => {
                const tag = TAG_STYLE[t.tag];
                return (
                  <TableRow key={t.name}>
                    <TableCell sx={{ fontWeight: 600 }}>{t.name}</TableCell>
                    <TableCell sx={{ color: "text.secondary" }}>{t.stage}</TableCell>
                    <TableCell sx={{ color: "text.secondary" }}>{t.audience}</TableCell>
                    <TableCell sx={{ color: "text.secondary" }}>{t.channel}</TableCell>
                    <TableCell>
                      <Chip size="small" label={tag.label} sx={{ background: tag.bg, color: tag.ink, fontWeight: 600 }} />
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </Card>
      </Box>

      {/* Channels + timeline */}
      <Box sx={{ display: "flex", gap: 2 }}>
        <Card sx={{ flex: 1, p: 3 }}>
          <Eyebrow sx={{ mb: 1.5 }}>Channels</Eyebrow>
          <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
            {CHANNELS.map((c) => (
              <Chip key={c.name} size="small" label={`${c.name} · ${c.csf}`} sx={{ background: tokens.color.accentSurface, color: tokens.color.primary }} />
            ))}
          </Box>
        </Card>
        <Card sx={{ flex: 1, p: 2.25 }}>
          <Typography sx={{ fontWeight: 700, mb: 1 }}>Field approach</Typography>
          <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, flexWrap: "wrap" }}>
            {FIELD_STEPS.map((s, i) => (
              <Box key={s} sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                <Chip size="small" label={s} />
                {i < FIELD_STEPS.length - 1 && <Typography sx={{ color: tokens.color.inkFaint }}>→</Typography>}
              </Box>
            ))}
          </Box>
        </Card>
      </Box>

      {/* Timeline */}
      <Card sx={{ p: 3, overflowX: "auto" }}>
        <Eyebrow sx={{ mb: 1.5 }}>Planned timing — quarterly flighting</Eyebrow>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell sx={{ fontWeight: 700 }}>Channel band</TableCell>
              <TableCell sx={{ fontWeight: 700 }}>Q1</TableCell>
              <TableCell sx={{ fontWeight: 700 }}>Q2</TableCell>
              <TableCell sx={{ fontWeight: 700 }}>Q3</TableCell>
              <TableCell sx={{ fontWeight: 700 }}>Q4</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {FLIGHTING.map((row) => (
              <TableRow key={row.band}>
                <TableCell sx={{ color: "text.secondary" }}>{row.band}</TableCell>
                {row.q.map((v, i) => (
                  <TableCell key={i} sx={{ color: tokens.color.secondary, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{DOT[v]}</TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <Typography variant="caption" sx={{ color: tokens.color.inkFaint, display: "block", mt: 1 }}>
          ● light · ●● medium · ●●● heavy (illustrative — align to the real media calendar and congress dates before committing).
        </Typography>
      </Card>

      {/* Critical success factors */}
      <Box>
        <Eyebrow sx={{ mb: 1 }}>Critical success factors</Eyebrow>
        <Box sx={{ display: "flex", gap: 2 }}>
          {CSFS.map((c) => (
            <RailCard key={c.n} rail={c.color.rail} sx={{ flex: 1 }}>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <Box
                  sx={{
                    width: 22, height: 22, borderRadius: "50%", flex: "0 0 auto",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    background: c.color.soft, color: c.color.ink, fontSize: 15, fontWeight: 700,
                  }}
                >
                  {c.n}
                </Box>
                <Typography sx={{ fontWeight: 700, fontSize: tokens.fontSize.md }}>{c.title}</Typography>
              </Box>
              <Typography variant="body2" sx={{ color: "text.secondary" }}>{c.body}</Typography>
            </RailCard>
          ))}
        </Box>
      </Box>

      {/* Pivotal evidence */}
      <Card sx={{ p: 3 }}>
        <Eyebrow sx={{ mb: 1.5 }}>Pivotal evidence · CLARITY-01</Eyebrow>
        <Box sx={{ display: "flex", gap: 3 }}>
          {EVIDENCE.map((e) => (
            <Box key={e.label} sx={{ flex: 1 }}>
              <Typography variant="caption" sx={{ color: "text.secondary" }}>{e.label}</Typography>
              <Typography sx={{ fontSize: 20, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{e.value}</Typography>
              <Typography variant="caption" sx={{ color: tokens.color.inkFaint, fontVariantNumeric: "tabular-nums" }}>{e.detail}</Typography>
            </Box>
          ))}
        </Box>
      </Card>

      {/* Standing guardrails */}
      <Box
        sx={{
          background: tokens.color.warningSoft,
          border: `1.5px solid ${tokens.color.warning}`,
          borderRadius: `${tokens.radius.md}px`,
          p: 3,
        }}
      >
        <Typography sx={{ fontWeight: 700, color: tokens.color.warningInk, mb: 1 }}>Standing guardrails</Typography>
        <Box component="ul" sx={{ m: 0, pl: 2.5, display: "flex", flexDirection: "column", gap: 0.5 }}>
          {GUARDRAILS.map((g) => (
            <Typography component="li" key={g} variant="body2" sx={{ color: tokens.color.warningInk }}>{g}</Typography>
          ))}
        </Box>
      </Box>
    </Box>
  );
}
