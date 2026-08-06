import { useEffect, useMemo, useState } from "react";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { ConsolePanel } from "../../../components/ConsolePanel";
import { getProject } from "../../../api";
import { StageHead } from "../StageHead";
import { LaunchStatus } from "./LaunchStatus";
import { DeliverablesPanel } from "./DeliverablesPanel";
import { GapsPanel, RiskPanel, RunPanel, WavesPanel } from "./RunPanels";
import { computeVerdict, deriveDeliverables, deriveRisks, deriveWaves } from "./derive";
import type { PlanResult } from "../../types";

function defaultGoLive(): string {
  const d = new Date();
  d.setDate(d.getDate() + 56); // 8 weeks out — the same anchor Stage 2's scheduler uses
  return d.toISOString().slice(0, 10);
}

/**
 * Campaign Ops (2) — sandbox stage.
 *
 * Answers one question: *can we launch, and what is in the way?* Everything is derived on the
 * client from the plan the earlier stages already produced (`deriveDeliverables`), so this
 * stage adds no backend endpoint and touches no shared state — nothing outside this folder is
 * affected by anything here.
 */
export function StageCampaignOps2({
  result,
  projectId,
  refreshToken = 0,
}: {
  result: PlanResult | null;
  projectId: string | null;
  refreshToken?: number;
}) {
  const [hydrated, setHydrated] = useState<PlanResult | null>(null);
  const [goLive, setGoLive] = useState(defaultGoLive());
  const [parallelTeams, setParallelTeams] = useState(4);
  const effective = result ?? hydrated;

  // The plan can be saved before the parent workspace's own state catches up, so hydrate
  // locally — same pattern the other stages use.
  useEffect(() => {
    if (result || !projectId) {
      setHydrated(null);
      return;
    }
    let cancelled = false;
    getProject(projectId)
      .then((p) => { if (!cancelled) setHydrated(p.result ?? null); })
      .catch(() => { if (!cancelled) setHydrated(null); });
    return () => { cancelled = true; };
  }, [result, projectId, refreshToken]);

  const items = useMemo(() => deriveDeliverables(effective), [effective]);
  const verdict = useMemo(() => computeVerdict(items, goLive, parallelTeams), [items, goLive, parallelTeams]);
  const risks = useMemo(() => deriveRisks(items, verdict), [items, verdict]);
  const waves = useMemo(() => deriveWaves(items), [items]);

  if (!effective) {
    return (
      <ConsolePanel>
        <Typography sx={{ color: "text.secondary", fontStyle: "italic" }}>
          Complete Stage 1 to assess launch readiness.
        </Typography>
      </ConsolePanel>
    );
  }

  if (!items.length) {
    return (
      <Box>
        <StageHead
          icon="checklist_rtl"
          title="Campaign Ops (2)"
          blurb="Launch readiness: what has to exist, what already does, and whether the date holds."
          agent="operations"
        />
        <ConsolePanel>
          <Typography sx={{ color: "text.secondary", fontStyle: "italic" }}>
            The plan carries no journey, messages or segments yet, so there is nothing to explode into
            deliverables. Build the campaign flow first.
          </Typography>
        </ConsolePanel>
      </Box>
    );
  }

  return (
    <Box>
      <StageHead
        icon="checklist_rtl"
        title="Campaign Ops (2)"
        blurb="Launch readiness. Every deliverable the journey implies, checked against what already exists, resourced and sequenced — ending in one verdict on the go-live date."
        agent="operations"
      />

      {/* The verdict leads: everything below it is the evidence for this panel, not a
          separate destination. Anchor ids feed StageSectionRail (OPS2_SECTIONS). */}
      <LaunchStatus
        verdict={verdict}
        goLive={goLive}
        onGoLive={setGoLive}
        parallelTeams={parallelTeams}
        onParallelTeams={setParallelTeams}
      />

      <DeliverablesPanel items={items} />
      <WavesPanel waves={waves} />
      <RiskPanel risks={risks} />
      <RunPanel />
      <GapsPanel />
    </Box>
  );
}
