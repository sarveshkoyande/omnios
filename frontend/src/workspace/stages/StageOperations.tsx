import { useEffect, useState } from "react";
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import Typography from "@mui/material/Typography";
import { ConsolePanel } from "../../components/ConsolePanel";
import { getProject } from "../../api";
import { CampaignFlowBuilder } from "./operations/CampaignFlowBuilder";
import { PlanningSummaryRail } from "./operations/PlanningSummaryRail";
import { StageHead } from "./StageHead";
import type { PlanResult } from "../types";

export function StageOperations({
  result,
  projectId,
  agentBusy = false,
  refreshToken = 0,
}: {
  result: PlanResult | null;
  projectId: string | null;
  agentBusy?: boolean;
  refreshToken?: number;
}) {
  // The campaign engagement flow doesn't build itself on tab-open -- it's gated behind the
  // chat kickoff card (or the "Regenerate" action inside that chat) the same way Stage 2's
  // task checklist is. `layoutReady` tracks whether a WorkflowDocument has actually been
  // generated+saved for this project yet; refreshToken bumps after a kickoff-triggered
  // generation so this refetches and the builder mounts.
  const [layoutReady, setLayoutReady] = useState<boolean | null>(null);
  const [hydratedResult, setHydratedResult] = useState<PlanResult | null>(null);
  const effectiveResult = result ?? hydratedResult;

  useEffect(() => {
    if (result || !projectId) {
      setHydratedResult(null);
      return;
    }
    let cancelled = false;
    getProject(projectId)
      .then((proj) => {
        if (!cancelled) setHydratedResult(proj.result ?? null);
      })
      .catch(() => {
        if (!cancelled) setHydratedResult(null);
      });
    return () => {
      cancelled = true;
    };
  }, [result, projectId, refreshToken]);

  useEffect(() => {
    if (!projectId) {
      setLayoutReady(null);
      return;
    }
    let cancelled = false;
    setLayoutReady(null);
    getProject(projectId)
      .then((proj) => {
        if (!cancelled) setLayoutReady(!!proj.campaign_plan_layout);
      })
      .catch(() => {
        if (!cancelled) setLayoutReady(false);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, refreshToken]);

  if (!effectiveResult) {
    return <ConsolePanel><Typography sx={{ color: "text.secondary", fontStyle: "italic" }}>Complete Stage 1 to open campaign operations.</Typography></ConsolePanel>;
  }
  const plan = effectiveResult.stage_3_campaign_plan;
  const lib = effectiveResult.content_library ?? { assets: [], found: false };

  return (
    <Box>
      <StageHead
        icon="dashboard"
        title="Campaign Operations"
        blurb="The orchestrated journey becomes an editable engagement diagram: start to close, with decision-split branches, segment volume and content readiness at every step."
        agent="operations"
      />

      {!lib.found && (
        <ConsolePanel sx={{ mb: 3 }}>
          <Typography sx={{ fontSize: 12, color: "text.secondary", background: "#FFF8E6", border: "1px solid #F0E0A8", borderRadius: 2, p: 1.5 }}>
            No content library indexed for this brand. The diagram shows tactics only. Run <code>scripts/build_content_library.py</code> to populate assets.
          </Typography>
        </ConsolePanel>
      )}

      {layoutReady === null ? (
        <ConsolePanel sx={{ mb: 3 }}>
          <Box sx={{ display: "flex", justifyContent: "center", py: 3 }}>
            <CircularProgress size={22} />
          </Box>
        </ConsolePanel>
      ) : layoutReady && plan ? (
        <Box sx={{ display: "flex", flexDirection: "column", gap: 3, mb: 3 }}>
          <PlanningSummaryRail plan={plan} />
          <CampaignFlowBuilder projectId={projectId} flow={plan.flow} agentBusy={agentBusy} />
        </Box>
      ) : (
        <ConsolePanel sx={{ mb: 3 }}>
          <Typography sx={{ color: "text.secondary", fontStyle: "italic" }}>
            No campaign engagement flow yet. Use the chat on the left to build it from the Stage 1 plan, or
            upload a document with additional instructions first.
          </Typography>
        </ConsolePanel>
      )}
    </Box>
  );
}
