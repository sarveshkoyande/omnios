import { useState } from "react";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Typography from "@mui/material/Typography";
import { AgentBubble } from "./ChatBubble";

const LABEL: Record<string, string> = {
  orchestration: "the Activities & setup-task checklist",
  operations: "the campaign engagement flow",
  reporting: "the reporting and insights view",
};

export function KickoffCard({
  stageId,
  resolved,
  awaitingInput,
  onUsePlan,
  onWantUpload,
}: {
  stageId: string;
  resolved: boolean;
  awaitingInput: boolean;
  onUsePlan: () => void;
  onWantUpload: () => void;
}) {
  const [choosing, setChoosing] = useState<"plan" | "upload" | null>(null);
  const label = LABEL[stageId] ?? "this";

  if (resolved || awaitingInput) {
    return (
      <AgentBubble sx={{ maxWidth: 560 }}>
        <Typography variant="body2" sx={{ color: "text.secondary" }}>
          {awaitingInput
            ? "Type any additional instructions below, or attach a document — I'll fold them in and build it."
            : "Building it now…"}
        </Typography>
      </AgentBubble>
    );
  }

  return (
    <AgentBubble sx={{ maxWidth: 560 }}>
      <Typography sx={{ fontWeight: 700, mb: 0.5 }}>Ready to build {label}?</Typography>
      <Typography variant="body2" sx={{ color: "text.secondary", mb: 2 }}>
        I can use the brief/plan from Stage 1 as-is, or you can give me a new document or extra
        instructions first and I'll fold those in too.
      </Typography>
      <Box sx={{ display: "flex", gap: 1.5, flexWrap: "wrap" }}>
        <Button
          variant="contained"
          disabled={choosing !== null}
          onClick={() => {
            setChoosing("plan");
            onUsePlan();
          }}
        >
          {choosing === "plan" ? "Building…" : "Use the Stage 1 plan"}
        </Button>
        <Button
          variant="outlined"
          disabled={choosing !== null}
          onClick={() => {
            setChoosing("upload");
            onWantUpload();
          }}
        >
          Upload a document / add instructions
        </Button>
      </Box>
    </AgentBubble>
  );
}
