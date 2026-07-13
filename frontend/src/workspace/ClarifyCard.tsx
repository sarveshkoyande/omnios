import Box from "@mui/material/Box";
import LinearProgress from "@mui/material/LinearProgress";
import Typography from "@mui/material/Typography";
import type { ClarifyPayload } from "./types";
import { tokens } from "../theme/tokens";

/** ClarifyCard — the question-progress gauge stamped into an agent memo. */
export function ClarifyCard({ clarify }: { clarify: ClarifyPayload }) {
  const pct = clarify.group_total ? (clarify.group_index / clarify.group_total) * 100 : 0;
  return (
    <Box>
      <Box sx={{ display: "flex", justifyContent: "space-between", fontSize: tokens.fontSize.xs, fontWeight: 700, color: "primary.dark", mb: 0.5 }}>
        <span>{clarify.title}</span>
        <span style={{ color: "inherit", opacity: 0.7, fontWeight: 500 }}>
          {clarify.group_index}/{clarify.group_total}
        </span>
      </Box>
      <LinearProgress variant="determinate" value={pct} sx={{ mb: 2, height: 7 }} />
      <Typography variant="body2" sx={{ whiteSpace: "pre-wrap" }}>
        {clarify.text}
      </Typography>
      {clarify.source && (
        <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mt: 1 }}>
          {clarify.source}
        </Typography>
      )}
    </Box>
  );
}
