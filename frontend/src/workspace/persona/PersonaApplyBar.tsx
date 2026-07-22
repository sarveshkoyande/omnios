import { useState } from "react";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Typography from "@mui/material/Typography";
import { AgentBubble } from "../ChatBubble";
import type { PersonaApplyChange } from "../types";

export function PersonaApplyBar({ onApply }: { onApply: () => Promise<void> }) {
  const [state, setState] = useState<"idle" | "applying">("idle");
  return (
    <AgentBubble>
      <Typography sx={{ fontWeight: 700, mb: 0.5 }}>Adjust the plan based on this feedback?</Typography>
      <Typography variant="body2" sx={{ color: "text.secondary", mb: 2 }}>
        I can automatically rebalance the channel mix toward what these personas actually respond to, and
        refresh the plan document. A bounded nudge, not a rebuild, and every change names the persona
        whose preference drove it.
      </Typography>
      <Button
        variant="contained"
        color="primary"
        disabled={state === "applying"}
        onClick={async () => {
          setState("applying");
          await onApply();
        }}
      >
        {state === "applying" ? "Adjusting plan…" : "Apply feedback to plan"}
      </Button>
    </AgentBubble>
  );
}

export function PersonaApplyResultCard({ changes }: { changes: PersonaApplyChange[] }) {
  return (
    <AgentBubble>
      <Typography sx={{ fontWeight: 700, mb: 0.5 }}>Plan updated from persona feedback</Typography>
      {changes.length ? (
        <>
          <Typography variant="body2" sx={{ color: "text.secondary", mb: 1 }}>
            {changes.length} channel{changes.length === 1 ? "" : "s"} rebalanced on the plan:
          </Typography>
          <Box component="ul" sx={{ m: 0, pl: 2 }}>
            {changes.map((c, i) => (
              <li key={i}>
                <b>{c.note}</b>: {c.from_pct}% to {c.to_pct}%
              </li>
            ))}
          </Box>
        </>
      ) : (
        <Typography variant="caption" sx={{ color: "text.secondary" }}>
          No material change was needed. The mix already fits this audience.
        </Typography>
      )}
    </AgentBubble>
  );
}
