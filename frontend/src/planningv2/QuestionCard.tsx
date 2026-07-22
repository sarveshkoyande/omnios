import { useState } from "react";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import { AgentBubble } from "../workspace/ChatBubble";
import { tokens } from "../theme/tokens";
import type { Gap } from "./api";

/**
 * QuestionCard — one pointed question from stage 5, modeled on the studio's
 * AskCard (recommended answer pre-staged, free text as fallback not the
 * default). The recommended option is always the gap's suggested_default,
 * since the engine never asks a question without one.
 */
const SectionChip = styled("span")({
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
  "&::before": { content: '""', width: 6, height: 6, borderRadius: 2, background: tokens.color.primary },
});

const OptionBtn = styled("button")<{ rec?: boolean; picked?: boolean }>(({ rec, picked }) => ({
  display: "block",
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

export function QuestionCard({
  gap,
  rank,
  total,
  answered,
  onAnswer,
}: {
  gap: Gap;
  rank: number;
  total: number;
  answered?: string;
  onAnswer: (value: string) => void;
}) {
  const [picked, setPicked] = useState<string | null>(answered ?? null);
  const [free, setFree] = useState("");
  const locked = picked !== null;
  const recommended = gap.suggested_default ?? "";

  const choose = (value: string) => {
    if (locked || !value.trim()) return;
    setPicked(value);
    onAnswer(value);
  };

  return (
    <AgentBubble sx={{ maxWidth: 640 }}>
      <Typography sx={{ fontSize: 11, fontWeight: 700, color: "primary.main", mb: 0.75 }}>
        Question {rank} of {total} · unblocks {gap.tactical_section_blocked}
      </Typography>
      <Box sx={{ mb: 0.75 }}>
        <SectionChip>{gap.tactical_section_blocked}</SectionChip>
      </Box>
      <Typography variant="body2" sx={{ lineHeight: 1.55, fontWeight: 600 }}>
        {gap.question}
      </Typography>
      <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mt: 0.5, fontStyle: "italic" }}>
        {gap.why_needed}
      </Typography>

      {recommended && (
        <OptionBtn rec picked={picked === recommended} disabled={locked} onClick={() => choose(recommended)}>
          {recommended}
          {picked !== recommended && (
            <Typography component="span" sx={{ fontSize: 10.5, color: "primary.main", fontWeight: 700 }}>
              {" "}
              · recommended default
            </Typography>
          )}
        </OptionBtn>
      )}
      {!locked && (
        <FreeText
          placeholder="Or type your own answer and press Enter…"
          value={free}
          onChange={(e) => setFree(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && free.trim()) choose(free.trim());
          }}
        />
      )}
      {locked && (
        <Typography variant="caption" sx={{ color: "success.main", fontWeight: 700, display: "block", mt: 1 }}>
          ✓ Locked in — {gap.tactical_section_blocked} will be built with this.
        </Typography>
      )}
    </AgentBubble>
  );
}
