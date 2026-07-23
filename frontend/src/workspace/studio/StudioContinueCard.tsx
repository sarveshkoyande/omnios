import { useEffect, useRef, useState } from "react";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Typography from "@mui/material/Typography";
import { AgentBubble } from "../ChatBubble";
import { tokens } from "../../theme/tokens";

const COUNTDOWN_SECONDS = 10;

/** Appears in chat right after a section lands. Auto-advances after a 10s countdown
 * (matching the "no dependency, just keep going" case) unless the user clicks "Continue
 * now" first -- either way the composer stays fully usable the whole time (this card
 * never blocks or disables chat). Once resolved, collapses to a quiet one-line receipt. */
export function StudioContinueCard({
  sectionTitle,
  resolved,
  onContinue,
}: {
  sectionTitle?: string;
  resolved?: boolean;
  onContinue: () => void;
}) {
  const [secondsLeft, setSecondsLeft] = useState(COUNTDOWN_SECONDS);
  const firedRef = useRef(false);

  useEffect(() => {
    if (resolved || firedRef.current) return;
    if (secondsLeft <= 0) {
      firedRef.current = true;
      onContinue();
      return;
    }
    const t = setTimeout(() => setSecondsLeft((s) => s - 1), 1000);
    return () => clearTimeout(t);
  }, [secondsLeft, resolved, onContinue]);

  const fire = () => {
    if (firedRef.current) return;
    firedRef.current = true;
    onContinue();
  };

  if (resolved) {
    return (
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, color: "text.secondary", fontSize: 12, pl: 1 }}>
        <span className="material-symbols-outlined" style={{ fontSize: 15, color: tokens.color.success }}>check_circle</span>
        <Typography variant="caption" sx={{ color: "text.secondary" }}>
          {sectionTitle ? `"${sectionTitle}" complete — continued.` : "Section complete — continued."}
        </Typography>
      </Box>
    );
  }

  return (
    <AgentBubble sx={{ maxWidth: 480 }}>
      <Typography sx={{ fontSize: 13, fontWeight: 700, mb: 0.5 }}>
        {sectionTitle ? `"${sectionTitle}" is done.` : "Section complete."}
      </Typography>
      <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mb: 1 }}>
        Continuing to the next section in {secondsLeft}s — keep chatting any time, this won't interrupt it.
      </Typography>
      <Button
        variant="contained"
        size="small"
        onClick={fire}
        endIcon={<span className="material-symbols-outlined" style={{ fontSize: 16 }}>arrow_forward</span>}
      >
        Continue now
      </Button>
    </AgentBubble>
  );
}
