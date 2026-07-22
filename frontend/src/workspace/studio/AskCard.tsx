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
  const [picked, setPicked] = useState<string | null>(answered ?? null);
  const [free, setFree] = useState("");
  const [detailAnchor, setDetailAnchor] = useState<HTMLElement | null>(null);
  const [reasonAnchor, setReasonAnchor] = useState<HTMLElement | null>(null);
  const locked = picked !== null;
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
  const recommendationLabel = ask.recommendation?.label?.trim() || "Confirm the recommended path";
  const recommendationSource = ask.recommendation?.source?.trim();
  const options = ask.options.filter((option) => option.label?.trim());

  const choose = (value: string) => {
    const cleanValue = value.trim();
    if (locked || !cleanValue) return;
    setPicked(cleanValue);
    onAnswer(cleanValue);
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
        <StatusChip title={llmStatus?.detail ?? undefined}>
          <span className="material-symbols-outlined" style={{ fontSize: 14 }}>{llmIcon}</span>
          {llmState}
        </StatusChip>
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

      <OptionBtn rec picked={picked === recommendationLabel} onClick={() => choose(recommendationLabel)}>
        <Box component="span" sx={{ minWidth: 0 }}>
          {recommendationLabel}
          {picked !== recommendationLabel && <RecommendedBadge>Recommended</RecommendedBadge>}
        </Box>
        {recommendationReason && (
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
      {options.map((option) => (
        <OptionBtn key={option.label} picked={picked === option.label.trim()} disabled={locked} onClick={() => choose(option.label)}>
          <Box component="span" sx={{ minWidth: 0 }}>
            {option.label.trim()}
            {option.source?.trim() && (
              <Typography component="span" sx={{ fontSize: 10.5, color: "text.secondary" }}>
                {" - "}{option.source.trim()}
              </Typography>
            )}
          </Box>
        </OptionBtn>
      ))}
      {ask.free_text && !locked && (
        <FreeText
          placeholder="Something else, type it and press Enter..."
          value={free}
          onChange={(event) => setFree(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && free.trim()) choose(free.trim());
          }}
        />
      )}
      {locked && (
        <Typography variant="caption" sx={{ color: "success.main", fontWeight: 700, display: "block", mt: 1 }}>
          Locked in. Drafting the section with it.
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
