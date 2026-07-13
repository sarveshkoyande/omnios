import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import IconButton from "@mui/material/IconButton";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import { AgentBubble } from "../ChatBubble";
import { PersonaAvatar } from "./PersonaAvatar";
import { SENTIMENT_COLOR } from "./personaUtils";
import type { PersonaReview } from "../types";
import { shade } from "../../theme/tokens";

const ColHead = styled(Typography)({
  fontSize: 10,
  fontWeight: 700,
  textTransform: "uppercase",
  letterSpacing: "0.06em",
  color: shade(0.55),
  marginBottom: 4,
});

const ReactionPill = styled(Chip)<{ reaction: string }>(({ reaction }) => ({
  height: 20,
  fontSize: 10,
  ...(reaction === "love it" && { background: "#DFF2E1", color: "#1B7A34" }),
  ...(reaction === "wasted on me" && { background: "#FDEAEA", color: "#A83232" }),
}));

export function PersonaReviewCard({
  review,
  onOpenProfile,
}: {
  review: PersonaReview;
  onOpenProfile: (id: string) => void;
}) {
  const color = SENTIMENT_COLOR[review.sentiment] ?? "secondary";
  const list = (arr: string[]) =>
    arr?.length ? (
      <Box component="ul" sx={{ m: 0, pl: 2 }}>
        {arr.map((x, i) => (
          <li key={i}>{x}</li>
        ))}
      </Box>
    ) : (
      <Typography variant="caption" sx={{ color: "text.secondary" }}>—</Typography>
    );

  return (
    <Box sx={{ display: "flex", gap: 2 }}>
      <PersonaAvatar name={review.persona_name} size={36} />
      <AgentBubble sx={{ flex: 1, borderLeft: (t) => `3px solid ${t.palette[color].main}` }}>
        <Box sx={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 1 }}>
          <Typography sx={{ fontWeight: 700 }}>{review.persona_name}</Typography>
          <Typography variant="caption" sx={{ color: "text.secondary" }}>
            {review.who} · {review.segment_name}
          </Typography>
          <IconButton size="small" onClick={() => onOpenProfile(review.persona_id)} title="View full persona profile">
            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>info</span>
          </IconButton>
          <Chip size="small" color={color} label={`${review.engagement_likelihood}% likely to engage`} sx={{ ml: "auto", fontWeight: 700 }} />
        </Box>

        {review.quote && (
          <Typography sx={{ fontStyle: "italic", my: 1.5 }}>&ldquo;{review.quote}&rdquo;</Typography>
        )}
        <Typography variant="body2" sx={{ color: "text.secondary", mb: 1.5 }}>{review.narrative}</Typography>

        <Box sx={{ display: "grid", gridTemplateColumns: "1fr", gap: 1 }}>
          <Box sx={{ background: shade(0.03), border: `1px solid ${shade(0.14)}`, borderRadius: "9px", p: 1.25 }}>
            <ColHead>What resonates</ColHead>
            {list(review.resonates)}
          </Box>
          <Box sx={{ background: shade(0.03), border: `1px solid ${shade(0.14)}`, borderRadius: "9px", p: 1.25 }}>
            <ColHead>What's missing</ColHead>
            {list(review.gaps)}
          </Box>
          <Box sx={{ background: shade(0.03), border: `1px solid ${shade(0.14)}`, borderRadius: "9px", p: 1.25 }}>
            <ColHead>To win me over</ColHead>
            {list(review.asks)}
          </Box>
        </Box>

        {!!review.channel_reactions?.length && (
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5, mt: 1.5 }}>
            {review.channel_reactions.map((c, i) => (
              <ReactionPill key={i} size="small" reaction={c.reaction} label={`${c.bucket} ${c.pct}%`} title={c.reaction} />
            ))}
          </Box>
        )}
      </AgentBubble>
    </Box>
  );
}
