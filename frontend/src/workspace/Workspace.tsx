import { useEffect, useRef, useState } from "react";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import { AgentTeamPanel } from "./AgentTeamPanel";
import { BriefCard } from "./BriefCard";
import { ChatMessages } from "./ChatMessages";
import { Composer } from "./Composer";
import { IntakeCard } from "./IntakeCard";
import { PersonaProfileModal } from "./persona/PersonaProfileModal";
import { PlanSummaryCard } from "./PlanSummaryCard";
import { PlansDrawer } from "./PlansDrawer";
import { StageOperations } from "./stages/StageOperations";
import { StageOrchestration } from "./stages/StageOrchestration";
import { StageReporting } from "./stages/StageReporting";
import { WorkflowStepper } from "./stages/WorkflowStepper";
import { useWorkspace } from "./useWorkspace";
import { ConsolePanel } from "../components/ConsolePanel";
import { tokens, indigoTint } from "../theme/tokens";

const EmptyState = styled(Box)(({ theme }) => ({
  flex: 1,
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  gap: theme.spacing(3),
  color: tokens.color.inkSoft,
  textAlign: "center",
  padding: theme.spacing(10),
}));

export function Workspace({ prefillBrand }: { prefillBrand?: string | null }) {
  const ws = useWorkspace();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const bootstrapped = useRef(false);

  useEffect(() => {
    if (bootstrapped.current) return;
    bootstrapped.current = true;
    if (prefillBrand) {
      ws.newProject().then(() => {
        // small delay so projectId lands in state before send
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (prefillBrand && ws.projectId && ws.showIntake) {
      ws.setShowIntake(false);
      ws.sendMessage(`I want to plan a campaign for ${prefillBrand}`);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ws.projectId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [ws.items]);

  return (
    <Box sx={{ display: "flex", height: "calc(100vh - 56px)", minHeight: 0 }}>
      <PlansDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        projects={ws.projects}
        activeId={ws.projectId}
        onOpenProject={(id) => { ws.openProject(id); setDrawerOpen(false); }}
        onNewProject={() => { ws.newProject(); setDrawerOpen(false); }}
      />

      <Box component="main" sx={{ flex: "0 0 42%", minWidth: 320, display: "flex", flexDirection: "column", borderRight: `1px solid ${indigoTint(0.1)}`, position: "relative" }}>
        <Button
          size="small"
          variant="outlined"
          onClick={() => setDrawerOpen(true)}
          sx={{ alignSelf: "flex-start", m: 2, mb: 0 }}
        >
          ☰ Plans
        </Button>

        {!ws.projectId ? (
          <EmptyState>
            <span className="material-symbols-outlined" style={{ fontSize: 46, color: tokens.color.primary }}>hub</span>
            <Typography variant="body1">
              <b>No plan open.</b>
              <br />
              Start a new plan and just tell the agent what you're working on — which brand, which
              therapy area, where it is in its lifecycle.
            </Typography>
            <Button variant="contained" color="primary" onClick={() => ws.newProject()}>
              + New plan
            </Button>
          </EmptyState>
        ) : (
          <>
            <Box sx={{ p: 3, pb: 2, borderBottom: `1px solid ${indigoTint(0.1)}` }}>
              <Typography variant="h3" sx={{ fontSize: tokens.fontSize.xl }}>{ws.projectName}</Typography>
              <Typography variant="caption" sx={{ color: "text.secondary" }}>
                The agent captures your brief in conversation, then runs its research agents on the right.
              </Typography>
            </Box>

            <Box ref={scrollRef} sx={{ flex: 1, overflowY: "auto", px: 3 }}>
              {ws.showIntake && <IntakeCard onSubmit={ws.submitIntake} onSkip={() => ws.setShowIntake(false)} />}
              <ChatMessages
                items={ws.items}
                onSkipPersonaOffer={ws.skipPersonaOffer}
                onRunPersonas={ws.runPersonas}
                onApplyFeedback={ws.applyFeedback}
                onOpenPersonaProfile={ws.openPersonaProfile}
              />
            </Box>

            <Box sx={{ p: 3, pt: 2 }}>
              <Composer disabled={ws.busy} onSend={ws.sendMessage} onUpload={ws.uploadFile} />
            </Box>
          </>
        )}
      </Box>

      <Box component="aside" sx={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 380, minHeight: 0 }}>
        {ws.projectId && (
          <>
            <WorkflowStepper stage={ws.stage} unlocked={!!ws.result} onSelect={ws.setStage} />
            <Box sx={{ flex: 1, overflowY: "auto", p: 3, pt: 1 }}>
              {ws.stage === 1 && (
                <>
                  <ConsolePanel title="Brief" icon="assignment" collapsible sx={{ mb: 3 }}>
                    <BriefCard slots={ws.slots} inferred={ws.inferred} />
                  </ConsolePanel>
                  <ConsolePanel title="Agent team" icon="smart_toy" collapsible>
                    <AgentTeamPanel agents={ws.agents} caption={ws.teamCaption} />
                  </ConsolePanel>
                  {ws.planHtml && (
                    <PlanSummaryCard
                      projectId={ws.projectId}
                      planHtml={ws.planHtml}
                      planMarkdown={ws.planMarkdown}
                      planFrozen={ws.planFrozen}
                      planEditing={ws.planEditing}
                      sectionsProgress={ws.sectionsProgress}
                      onBeginEdit={ws.beginPlanEdit}
                      onCancelEdit={ws.cancelPlanEdit}
                      onSaveEdit={ws.savePlanEdit}
                      onCloseUpdates={ws.closeUpdatesAction}
                    />
                  )}
                </>
              )}
              {ws.stage === 2 && <StageOrchestration result={ws.result} />}
              {ws.stage === 3 && <StageOperations result={ws.result} />}
              {ws.stage === 4 && <StageReporting result={ws.result} />}
            </Box>
          </>
        )}
      </Box>
      <PersonaProfileModal personaId={ws.profileOpen} onClose={ws.closePersonaProfile} />
    </Box>
  );
}
