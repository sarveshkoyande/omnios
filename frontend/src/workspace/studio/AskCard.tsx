import { useState } from "react";
import Box from "@mui/material/Box";
import Popover from "@mui/material/Popover";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import { indigoTint, tokens, motion, hoverOnly } from "../../theme/tokens";
import { accent } from "../../theme/stageTheme";
import type { AskOption, StudioAsk } from "./studioTypes";

const SourceChip = styled("span")({
  display: "inline-flex",
  alignItems: "center",
  gap: 5,
  fontSize: 15,
  fontWeight: 600,
  color: tokens.color.primary,
  background: tokens.color.primaryContainer,
  border: `1px solid ${tokens.color.outline}`,
  borderRadius: tokens.radius.pill,
  padding: "2px 9px",
  marginRight: 6,
  "&::before": {
    content: '""',
    width: 6,
    height: 6,
    borderRadius: 2,
    background: tokens.color.primary,
  },
});

const RecommendedBadge = styled("span")({
  display: "inline-flex",
  alignItems: "center",
  marginLeft: 8,
  padding: "1px 7px",
  borderRadius: tokens.radius.pill,
  // Solid accent on the already-tinted recommended row: the badge has to stay legible against
  // the deeper wash behind it, which a container-tinted badge would not.
  background: accent.primary,
  color: "#fff",
  border: "none",
  fontSize: 15,
  fontWeight: 800,
  textTransform: "uppercase",
});

const IconAction = styled("span")({
  border: 0,
  background: "transparent",
  color: tokens.color.primary,
  padding: 2,
  width: 22,
  height: 22,
  borderRadius: tokens.radius.pill,
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  cursor: "pointer",
  flex: "0 0 auto",
  "&:hover": { background: tokens.color.primaryContainer },
  "&:focus-visible": { outline: `2px solid ${tokens.color.primary}`, outlineOffset: 1 },
});

/**
 * Three states, three depths of the SAME stage accent, so the card reads as one family and
 * still tells you what is what at a glance:
 *   plain option  — faintest wash (tint 0.04)
 *   recommended   — deeper wash + accent border (tint 0.12); emphasis, not selection
 *   picked        — solid accent, white text
 * Recommended deliberately stops short of the solid fill: if "recommended" already looked
 * selected, there would be no way to see that you had actually chosen it.
 */
const OptionBtn = styled("button")<{ rec?: boolean; picked?: boolean }>(({ rec, picked }) => ({
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: 10,
  width: "100%",
  textAlign: "left",
  font: "inherit",
  fontSize: tokens.fontSize.sm,
  marginTop: 8,
  padding: "10px 12px",
  borderRadius: 10,
  cursor: "pointer",
  color: picked ? "#fff" : tokens.color.text,
  background: picked ? accent.primary : rec ? accent.container : accent.tint04,
  border: `1px solid ${picked ? "transparent" : rec ? accent.primary : tokens.color.outline}`,
  boxShadow: "none",
  transition: `background ${motion.duration.hover} ${motion.easeOut}, border-color ${motion.duration.hover} ${motion.easeOut}, transform ${motion.duration.press} ${motion.easeOut}`,
  [hoverOnly]: {
    "&:hover": picked ? {} : { background: accent.tint12 },
  },
  "&:active:not(:disabled)": { transform: "scale(0.99)" },
  "&:focus-visible": { outline: `2px solid ${accent.primary}`, outlineOffset: 2 },
  "&:disabled": { cursor: "default", opacity: 0.8 },
}));

const FreeText = styled("input")({
  width: "100%",
  font: "inherit",
  fontSize: tokens.fontSize.sm,
  marginTop: 8,
  padding: "10px 12px",
  borderRadius: 10,
  border: `1px dashed ${tokens.color.outlineStrong}`,
  background: tokens.color.surface,
  color: tokens.color.text,
  "&:focus-visible": { outline: `2px solid ${accent.primary}`, outlineOffset: 0 },
});

const ConfirmBtn = styled("button")({
  font: "inherit",
  fontSize: tokens.fontSize.sm,
  fontWeight: 700,
  marginTop: 10,
  padding: "8px 16px",
  borderRadius: 10,
  cursor: "pointer",
  color: "#fff",
  background: accent.primary,
  border: "none",
  "&:hover": { background: accent.primaryDark },
  "&:disabled": { opacity: 0.5, cursor: "default" },
  "&:focus-visible": { outline: `2px solid ${accent.primary}`, outlineOffset: 2 },
});

/** The data-analysis line above the options: what the sizing is based on. */
const EvidenceNote = styled("div")({
  display: "flex",
  alignItems: "flex-start",
  gap: 6,
  fontSize: 15,
  lineHeight: 1.45,
  color: tokens.color.inkSecondary,
  background: accent.tint04,
  border: `1px solid ${tokens.color.outline}`,
  borderRadius: 8,
  padding: "6px 9px",
  marginBottom: 4,
});

const PopoverBody = styled(Box)({
  maxWidth: 360,
  padding: 14,
});

export function AskCard({
  ask,
  ownerName,
  answered,
  onAnswer,
}: {
  ask: StudioAsk;
  ownerName: string;
  answered?: string;
  onAnswer: (value: string) => void;
}) {
  const multi = Boolean(ask.multi_select);
  // The card counts whatever the ask is choosing between; "segments" was hardcoded and read
  // wrong the moment a second multi-select (message rungs) existed.
  const selectNoun = ask.select_noun?.trim() || "option";
  const recommendationLabel = ask.recommendation?.label?.trim() || "Confirm the recommended path";
  const options = ask.options.filter((option) => option.label?.trim());

  const [picked, setPicked] = useState<string | null>(answered ?? null);
  // Multi-select: pre-tick `preselected` when the sensible default is a set (every clinical
  // message rung, say) and fall back to the recommendation alone otherwise. A prior answer
  // always wins and restores the whole set.
  const [selected, setSelected] = useState<Set<string>>(() => {
    if (answered) return new Set(answered.split(/\s*;\s*/).filter(Boolean));
    if (!multi) return new Set<string>();
    const preselected = (ask.preselected ?? []).map((label) => label.trim()).filter(Boolean);
    return new Set(preselected.length ? preselected : [recommendationLabel]);
  });
  const [confirmed, setConfirmed] = useState<boolean>(multi ? Boolean(answered) : false);
  const [free, setFree] = useState("");
  const [detailAnchor, setDetailAnchor] = useState<HTMLElement | null>(null);
  const [reasonAnchor, setReasonAnchor] = useState<HTMLElement | null>(null);
  // Auto-assumed asks arrive already answered: the card is a record of what was taken, not a gate.
  const autoAssumed = Boolean(ask.auto_assumed);
  const locked = autoAssumed || (multi ? confirmed : picked !== null);
  const llmStatus = ask.llm_status;
  const llmFailed = llmStatus?.ok === false || ask.source === "deterministic-fallback";
  const llmState = llmStatus?.ok === true
    ? "Claude generated this"
    : llmFailed
      ? "Claude failed; fallback shown"
      : "Claude generation pending";
  const llmIcon = llmStatus?.ok === true ? "smart_toy" : llmFailed ? "warning" : "hourglass_top";
  const diagnostics = Object.entries(llmStatus?.diagnostics ?? {})
    .filter(([, value]) => value !== "" && value !== null && value !== undefined)
    .map(([key, value]) => `${key}: ${String(value)}`);
  const recommendationReason = ask.recommendation_reason || ask.why || ask.evidence_basis || "";
  const hasGroundingDetails = Boolean(ask.evidence_basis || ask.why || ask.framework || ask.blocked);
  const recommendationSource = ask.recommendation?.source?.trim();

  const choose = (value: string) => {
    const cleanValue = value.trim();
    if (locked || !cleanValue) return;
    setPicked(cleanValue);
    onAnswer(cleanValue);
  };

  const isChosen = (label: string) => (multi ? selected.has(label) : picked === label);

  const toggle = (label: string) => {
    if (locked) return;
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(label)) next.delete(label);
      else next.add(label);
      return next;
    });
  };

  // Clicking an option toggles it in multi mode, or locks it in single mode.
  const activate = (label: string) => (multi ? toggle(label) : choose(label));

  const addFree = (value: string) => {
    const clean = value.trim();
    if (!clean || locked) return;
    if (multi) {
      setSelected((prev) => new Set(prev).add(clean));
      setFree("");
    } else {
      choose(clean);
    }
  };

  // Confirm the multi-selection, ordered recommendation-first then options, customs last.
  const confirmMulti = () => {
    if (locked) return;
    const known = [recommendationLabel, ...options.map((o) => o.label.trim())];
    const ordered = known.filter((l) => selected.has(l));
    const customs = [...selected].filter((l) => !known.includes(l));
    const final = [...ordered, ...customs];
    if (!final.length) return;
    setConfirmed(true);
    onAnswer(final.join("; "));
  };

  const renderOption = (opt: AskOption, isRec: boolean) => {
    const label = opt.label.trim();
    const chosen = isChosen(label);
    return (
      <OptionBtn
        key={isRec ? "__rec__" : label}
        rec={isRec}
        picked={chosen}
        disabled={locked && !chosen}
        onClick={() => activate(label)}
      >
        <Box component="span" sx={{ display: "flex", gap: 1, minWidth: 0, alignItems: "flex-start" }}>
          {multi && (
            <span className="material-symbols-outlined" style={{ fontSize: 18, marginTop: 1, flex: "0 0 auto" }}>
              {chosen ? "check_box" : "check_box_outline_blank"}
            </span>
          )}
          <Box component="span" sx={{ minWidth: 0 }}>
            {/* The option's `source` ("alternative cadence", "claim library", "channel-affinity
                model") is deliberately not shown: it labelled where the option came from, which
                is provenance the reasoning popover already carries, and on the option row it
                just competed with the option itself. */}
            <Box component="span">
              {label}
              {isRec && !chosen && <RecommendedBadge>Recommended</RecommendedBadge>}
            </Box>
            {opt.size && (
              <Typography component="span" sx={{ display: "block", fontSize: 15, fontWeight: 700, mt: 0.25, color: chosen ? "#fff" : "primary.main" }}>
                {opt.size}
              </Typography>
            )}
            {opt.criteria && (
              <Typography component="span" sx={{ display: "block", fontSize: 15, lineHeight: 1.4, mt: 0.15, color: chosen ? "rgba(255,255,255,0.9)" : "text.secondary" }}>
                {opt.criteria}
              </Typography>
            )}
            {opt.distribution && opt.distribution.length > 0 && (
              <Box component="span" sx={{ display: "flex", flexWrap: "wrap", gap: 0.5, mt: 0.5 }}>
                {opt.distribution.map((slice) => (
                  <Typography
                    key={slice.channel}
                    component="span"
                    sx={{
                      fontSize: 15,
                      fontWeight: 700,
                      lineHeight: 1.6,
                      px: 0.6,
                      borderRadius: 0.5,
                      color: chosen ? "#fff" : "primary.main",
                      background: chosen ? "rgba(255,255,255,0.18)" : indigoTint(0.1),
                    }}
                  >
                    {slice.channel} {Math.round(slice.pct)}%
                  </Typography>
                ))}
              </Box>
            )}
          </Box>
        </Box>
        {isRec && recommendationReason && (
          <IconAction
            role="button"
            tabIndex={0}
            aria-label="Show recommendation rationale"
            title="Why this recommendation"
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              setReasonAnchor(event.currentTarget);
            }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 15 }}>info</span>
          </IconAction>
        )}
      </OptionBtn>
    );
  };

  const renderMarkup = (t: string) =>
    t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

  return (
    // No chat bubble: the question and its options are the thing being acted on, so they sit
    // on the pane rather than inside a message. Every provenance tag that used to sit above
    // the question ("best practice", the recommendation's source, "Claude generation pending")
    // has moved into the reasoning popover behind the single psychology icon.
    <Box sx={{ maxWidth: 640, width: "100%", minWidth: 0 }}>
      <Box sx={{ display: "flex", alignItems: "center", gap: 0.75, mb: 0.75 }}>
        <Typography sx={{ fontSize: 15, fontWeight: 700, color: accent.primary }}>
          {ownerName} - {autoAssumed ? "decided for you (auto-assume)" : "needs your call"}
        </Typography>
        {hasGroundingDetails && (
          <IconAction
            role="button"
            tabIndex={0}
            aria-label="Show reasoning and grounding"
            title="Reasoning and grounding"
            onClick={(event) => setDetailAnchor(event.currentTarget)}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>psychology</span>
          </IconAction>
        )}
      </Box>

      <Typography
        sx={{ fontSize: tokens.fontSize.md, lineHeight: 1.55, mb: 1.25, color: tokens.color.text }}
        dangerouslySetInnerHTML={{ __html: renderMarkup(ask.text) }}
      />

      {ask.evidence_note && (
        <EvidenceNote>
          <span className="material-symbols-outlined" style={{ fontSize: 15, marginTop: 1 }}>insights</span>
          <span>{ask.evidence_note}</span>
        </EvidenceNote>
      )}

      {renderOption(ask.recommendation, true)}
      {options.map((option) => renderOption(option, false))}

      {ask.free_text && !locked && (
        <FreeText
          placeholder={multi ? "Add another segment, type it and press Enter..." : "Something else, type it and press Enter..."}
          value={free}
          onChange={(event) => setFree(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && free.trim()) addFree(free.trim());
          }}
        />
      )}

      {multi && !locked && (
        <ConfirmBtn onClick={confirmMulti} disabled={selected.size === 0}>
          Confirm {selected.size} {selectNoun}{selected.size === 1 ? "" : "s"}
        </ConfirmBtn>
      )}

      {locked && (
        <Typography variant="caption" sx={{ color: autoAssumed ? "text.secondary" : "success.main", fontWeight: 700, display: "block", mt: 1 }}>
          {autoAssumed
            ? "Auto-assumed the recommendation and kept going. Untick auto-assume to be asked again."
            : multi
              ? `Locked in ${selected.size} ${selectNoun}${selected.size === 1 ? "" : "s"}. Drafting the section with them.`
              : "Locked in. Drafting the section with it."}
        </Typography>
      )}

      <Popover
        open={Boolean(detailAnchor)}
        anchorEl={detailAnchor}
        onClose={() => setDetailAnchor(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "left" }}
      >
        <PopoverBody>
          <Typography sx={{ fontSize: 15, fontWeight: 800, mb: 1 }}>Reasoning and grounding</Typography>
          {/* This is now the only home for provenance. The best-practice / model / library
              labels that used to sit as chips on the card body land here instead. */}
          {recommendationSource && (
            <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mb: 1 }}>
              <b>Recommendation drawn from:</b> {recommendationSource}
            </Typography>
          )}
          {ask.evidence_basis && (
            <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mb: 1 }}>
              <b>Basis:</b> {ask.evidence_basis}
            </Typography>
          )}
          {ask.why && (
            <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mb: 1, fontStyle: "italic" }}>
              {ask.why}
            </Typography>
          )}
          {(ask.framework || ask.blocked) && (
            <Box sx={{ display: "flex", gap: 0.5, flexWrap: "wrap", mt: 0.5 }}>
              {ask.framework && <SourceChip>framework - {ask.framework}</SourceChip>}
              {ask.blocked && <SourceChip>unblocks - {ask.blocked}</SourceChip>}
            </Box>
          )}
          {/* Kept, but demoted out of the card body: a deterministic fallback shown as if it
              were AI-generated is a misread worth being able to check. */}
          {llmStatus?.ok !== true && (
            <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, mt: 1, pt: 1, borderTop: `1px solid ${tokens.color.outline}` }}>
              <span className="material-symbols-outlined" style={{ fontSize: 15, color: tokens.color.inkSecondary }}>{llmIcon}</span>
              <Typography variant="caption" sx={{ color: "text.secondary" }}>
                {llmState}
                {llmFailed && llmStatus?.detail ? ` - ${llmStatus.detail}` : ""}
                {llmFailed && diagnostics.length ? ` (${diagnostics.join(" | ")})` : ""}
              </Typography>
            </Box>
          )}
        </PopoverBody>
      </Popover>

      <Popover
        open={Boolean(reasonAnchor)}
        anchorEl={reasonAnchor}
        onClose={() => setReasonAnchor(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
      >
        <PopoverBody>
          <Typography sx={{ fontSize: 15, fontWeight: 800, mb: 0.75 }}>Why this recommendation</Typography>
          <Typography variant="body2" sx={{ color: "text.secondary", lineHeight: 1.45 }}>
            {recommendationReason}
          </Typography>
        </PopoverBody>
      </Popover>
    </Box>
  );
}
