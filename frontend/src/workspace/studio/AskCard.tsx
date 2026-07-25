import { useState } from "react";
import Box from "@mui/material/Box";
import Popover from "@mui/material/Popover";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import { AgentBubble } from "../ChatBubble";
import { tokens } from "../../theme/tokens";
import type { StudioAsk } from "./studioTypes";

const SourceChip = styled("span")({
  display: "inline-flex",
  alignItems: "center",
  gap: 5,
  fontSize: 10.5,
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

const StatusChip = styled("span")({
  display: "inline-flex",
  alignItems: "center",
  gap: 5,
  fontSize: 10.5,
  fontWeight: 700,
  borderRadius: tokens.radius.pill,
  padding: "2px 9px",
  marginRight: 6,
  border: `1px solid ${tokens.color.warning}`,
  background: tokens.color.warningSoft,
  color: tokens.color.warningInk,
});

const RecommendedBadge = styled("span")({
  display: "inline-flex",
  alignItems: "center",
  marginLeft: 8,
  padding: "1px 7px",
  borderRadius: tokens.radius.pill,
  background: tokens.color.primaryContainer,
  color: tokens.color.primary,
  border: `1px solid ${tokens.color.outline}`,
  fontSize: 10,
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

const OptionBtn = styled("button")<{ rec?: boolean; picked?: boolean }>(({ rec, picked }) => ({
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: 10,
  width: "100%",
  textAlign: "left",
  font: "inherit",
  fontSize: tokens.fontSize.sm,
  marginTop: 6,
  padding: "8px 12px",
  borderRadius: 10,
  cursor: "pointer",
  color: picked ? "#fff" : tokens.color.text,
  background: picked ? tokens.color.primary : tokens.color.surface,
  border: `1px solid ${picked ? "transparent" : rec ? tokens.color.primary : tokens.color.outline}`,
  boxShadow: "none",
  "&:hover": picked ? {} : { background: tokens.color.canvas },
  "&:focus-visible": { outline: `2px solid ${tokens.color.primary}`, outlineOffset: 2 },
  "&:disabled": { cursor: "default", opacity: 0.8 },
}));

const FreeText = styled("input")({
  width: "100%",
  font: "inherit",
  fontSize: tokens.fontSize.sm,
  marginTop: 6,
  padding: "8px 12px",
  borderRadius: 10,
  border: `1px solid ${tokens.color.outline}`,
  background: tokens.color.surface,
  color: tokens.color.text,
  "&:focus-visible": { outline: `2px solid ${tokens.color.primary}`, outlineOffset: 0 },
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
  background: tokens.color.primary,
  border: "none",
  "&:hover": { background: tokens.color.primaryDark },
  "&:disabled": { opacity: 0.5, cursor: "default" },
  "&:focus-visible": { outline: `2px solid ${tokens.color.primary}`, outlineOffset: 2 },
});

/** The data-analysis line above the options: what the sizing is based on. */
const EvidenceNote = styled("div")({
  display: "flex",
  alignItems: "flex-start",
  gap: 6,
  fontSize: 11.5,
  lineHeight: 1.45,
  color: tokens.color.inkSecondary,
  background: tokens.color.primaryContainer,
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
  const recommendationLabel = ask.recommendation?.label?.trim() || "Confirm the recommended path";
  const options = ask.options.filter((option) => option.label?.trim());

  const [picked, setPicked] = useState<string | null>(answered ?? null);
  // Multi-select: pre-select the recommendation; a prior answer restores the whole set.
  const [selected, setSelected] = useState<Set<string>>(() =>
    new Set(answered ? answered.split(/\s*;\s*/).filter(Boolean) : multi ? [recommendationLabel] : []),
  );
  const [confirmed, setConfirmed] = useState<boolean>(multi ? Boolean(answered) : false);
  const [free, setFree] = useState("");
  const [detailAnchor, setDetailAnchor] = useState<HTMLElement | null>(null);
  const [reasonAnchor, setReasonAnchor] = useState<HTMLElement | null>(null);
  const locked = multi ? confirmed : picked !== null;
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

  const renderOption = (opt: { label: string; source?: string; size?: string; criteria?: string }, isRec: boolean) => {
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
            <Box component="span">
              {label}
              {isRec && !chosen && <RecommendedBadge>Recommended</RecommendedBadge>}
              {!isRec && opt.source?.trim() && !opt.size && (
                <Typography component="span" sx={{ fontSize: 10.5, color: chosen ? "rgba(255,255,255,0.85)" : "text.secondary" }}>
                  {" - "}{opt.source.trim()}
                </Typography>
              )}
            </Box>
            {opt.size && (
              <Typography component="span" sx={{ display: "block", fontSize: 11, fontWeight: 700, mt: 0.25, color: chosen ? "#fff" : "primary.main" }}>
                {opt.size}
              </Typography>
            )}
            {opt.criteria && (
              <Typography component="span" sx={{ display: "block", fontSize: 10.5, lineHeight: 1.4, mt: 0.15, color: chosen ? "rgba(255,255,255,0.9)" : "text.secondary" }}>
                {opt.criteria}
              </Typography>
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
    <AgentBubble sx={{ maxWidth: 640 }}>
      <Typography sx={{ fontSize: 11, fontWeight: 700, color: "primary.main", mb: 0.75 }}>
        {ownerName} - needs your call
      </Typography>
      <Box sx={{ mb: 0.75, display: "flex", flexWrap: "wrap", gap: 0.5, alignItems: "center" }}>
        {recommendationSource && <SourceChip>{recommendationSource}</SourceChip>}
        {/* Only surface this status chip when something's actually wrong or still pending --
            a routine successful generation doesn't need a "Claude generated this" badge. */}
        {llmStatus?.ok !== true && (
          <StatusChip title={llmStatus?.detail ?? undefined}>
            <span className="material-symbols-outlined" style={{ fontSize: 14 }}>{llmIcon}</span>
            {llmState}
          </StatusChip>
        )}
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
        {llmFailed && (
          <Typography variant="caption" sx={{ color: "text.secondary", display: "block", flexBasis: "100%" }}>
            {llmStatus?.detail ?? "No LLM failure detail returned."}
            {diagnostics.length ? ` (${diagnostics.join(" | ")})` : ""}
          </Typography>
        )}
      </Box>

      <Typography
        variant="body2"
        sx={{ lineHeight: 1.55, mb: 1 }}
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
          Confirm {selected.size} segment{selected.size === 1 ? "" : "s"}
        </ConfirmBtn>
      )}

      {locked && (
        <Typography variant="caption" sx={{ color: "success.main", fontWeight: 700, display: "block", mt: 1 }}>
          {multi ? `Locked in ${selected.size} segment${selected.size === 1 ? "" : "s"}. Drafting the section with them.` : "Locked in. Drafting the section with it."}
        </Typography>
      )}

      <Popover
        open={Boolean(detailAnchor)}
        anchorEl={detailAnchor}
        onClose={() => setDetailAnchor(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "left" }}
      >
        <PopoverBody>
          <Typography sx={{ fontSize: 12, fontWeight: 800, mb: 1 }}>Reasoning and grounding</Typography>
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
        </PopoverBody>
      </Popover>

      <Popover
        open={Boolean(reasonAnchor)}
        anchorEl={reasonAnchor}
        onClose={() => setReasonAnchor(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
      >
        <PopoverBody>
          <Typography sx={{ fontSize: 12, fontWeight: 800, mb: 0.75 }}>Why this recommendation</Typography>
          <Typography variant="body2" sx={{ color: "text.secondary", lineHeight: 1.45 }}>
            {recommendationReason}
          </Typography>
        </PopoverBody>
      </Popover>
    </AgentBubble>
  );
}
