import { useEffect, useRef, useState } from "react";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import IconButton from "@mui/material/IconButton";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import Accordion from "@mui/material/Accordion";
import AccordionSummary from "@mui/material/AccordionSummary";
import AccordionDetails from "@mui/material/AccordionDetails";
import { AgentTeamPanel } from "./AgentTeamPanel";
import { AgentAvatar } from "./Avatar";
import { BriefCard } from "./BriefCard";
import { CampaignArtifacts } from "./CampaignArtifacts";
import { ChatMessages } from "./ChatMessages";
import { DecisionTrail } from "./studio/DecisionTrail";
import { Composer } from "./Composer";
import { IntakeCard } from "./IntakeCard";
import { PersonaProfileModal } from "./persona/PersonaProfileModal";
import { PlanSectionsRail } from "./PlanSectionsRail";
import { SECTION_TITLES, sectionTotal } from "./PlanSectionsRail";
import { StageSectionRail, ORCH_SECTIONS, OPS2_SECTIONS, OPS_SECTIONS, REPORT_SECTIONS } from "./StageSectionRail";
import { PlansDrawer } from "./PlansDrawer";
import { PlanDocument } from "./PlanDocument";
import { PlanSummaryCard } from "./PlanSummaryCard";
import { SimplePlanSummary } from "./SimplePlanSummary";
import { StageOperations } from "./stages/StageOperations";
import { StageOrchestration } from "./stages/StageOrchestration";
import { StageCampaignOps2 } from "./stages/campaignops2/StageCampaignOps2";
import { StageReporting } from "./stages/StageReporting";
import type { StudioState } from "./studio/studioTypes";
import { WorkflowStepper } from "./stages/WorkflowStepper";
import { useWorkspace } from "./useWorkspace";
import { STAGE_AGENTS, agentForStage } from "./types";
import { ConsolePanel } from "../components/ConsolePanel";
import { tokens, indigoTint, light } from "../theme/tokens";
import { enterRise, enterWith } from "../theme/motionPresets";
import { stageVars, accent, stageMark } from "../theme/stageTheme";

// All four stages are freely accessible at any time — there is no unlock gating.
// The legacy /api/run-stream flow and its revealed_phases tracking stay in the
// codebase (openProject still reads state.revealed_phases) but no longer drive Stage 1.

/** Toggle row shown above the plan — the simplified summary is the default view,
 * but the full generated Brand Engagement Plan is one click away, not deleted. */
function PlanViewToggle({ showFull, onToggle }: { showFull: boolean; onToggle: () => void }) {
  return (
    <Box sx={{ display: "flex", justifyContent: "flex-end", mb: 1 }}>
      <Button size="small" variant="text" onClick={onToggle}>
        {showFull ? "← Back to simplified summary" : "View full plan →"}
      </Button>
    </Box>
  );
}

/** The retired plan outputs (hardcoded simplified summary + 30-section Brand Engagement
 * Plan), archived behind an accordion — recoverable, out of the way. The Campaign
 * Strategy + Campaign Brief (CampaignArtifacts) are the standing default. */
function ArchivedPlanViews({ children }: { children: React.ReactNode }) {
  return (
    <Accordion
      sx={{
        background: light(0.4),
        border: `1px solid ${indigoTint(0.12)}`,
        borderRadius: tokens.radius.md,
        mt: 3,
        boxShadow: "none",
        "&:before": { display: "none" },
      }}
    >
      <AccordionSummary expandIcon={<span className="material-symbols-outlined">expand_more</span>}>
        <Typography sx={{ fontWeight: 700, fontSize: 15 }}>Previous plan views (archived)</Typography>
      </AccordionSummary>
      <AccordionDetails>{children}</AccordionDetails>
    </Accordion>
  );
}

function FinalPlanSections({ studio }: { studio: StudioState }) {
  /*
   * Rows are positional, matching PlanSectionsRail. The previous version keyed a Map on
   * `section.num` and then looked rows up by `index + 1`, which are two unrelated numbering
   * schemes: `num` is the position in the master plan template (a real run stores
   * 7, 8, 9, 10, 11, 12, 13, 14, 26, 27, 28, 33), while `index + 1` just counts rows 1..N.
   * Only the handful of `num`s that happened to fall under N matched, and they matched the
   * wrong row -- so fully generated sections rendered "This section has not been generated
   * for this plan", two titles appeared twice, and the rail (which indexes positionally, and
   * was right all along) disagreed with the document.
   *
   * The row count follows whichever is longer so a section can never be generated-but-hidden:
   * SECTION_TITLES supplies placeholder titles for sections not yet drafted, and anything the
   * studio emits beyond that list still gets a row under its own title.
   */
  const completeCount = studio.sections.length;
  const total = Math.max(SECTION_TITLES.length, completeCount);
  const rows = Array.from({ length: total }, (_, index) => ({
    num: index + 1,
    section: studio.sections[index],
    title: studio.sections[index]?.title || SECTION_TITLES[index] || `Section ${index + 1}`,
  }));

  return (
    <ConsolePanel
      id="final-plan-sections-anchor"
      title="Plan sections"
      icon="format_list_numbered"
      sx={{ mt: 3 }}
    >
      <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mb: 1.5 }}>
        {completeCount}/{total} generated. Sections are minimized by default.
      </Typography>
      <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
        {rows.map(({ num, section, title }) => {
          return (
            <Accordion
              key={`${num}-${title}`}
              disableGutters
              sx={{
                background: tokens.color.surface,
                border: `1px solid ${tokens.color.outline}`,
                borderRadius: tokens.radius.sm,
                boxShadow: "none",
                "&:before": { display: "none" },
              }}
            >
              <AccordionSummary expandIcon={<span className="material-symbols-outlined">expand_more</span>}>
                <Box sx={{ display: "flex", alignItems: "center", gap: 1.25, minWidth: 0 }}>
                  <Box
                    component="span"
                    sx={{
                      width: 24,
                      height: 24,
                      borderRadius: "50%",
                      display: "inline-grid",
                      placeItems: "center",
                      flex: "0 0 auto",
                      background: section ? tokens.color.primaryContainer : tokens.color.canvas,
                      color: section ? tokens.color.primary : "text.secondary",
                      fontSize: 15,
                      fontWeight: 800,
                    }}
                  >
                    {num}
                  </Box>
                  <Typography sx={{ fontSize: tokens.fontSize.sm, fontWeight: 700 }}>
                    {section?.title || title}
                  </Typography>
                </Box>
              </AccordionSummary>
              <AccordionDetails>
                {section ? (
                  <PlanDocument html={section.html} editing={false} />
                ) : (
                  <Typography variant="body2" sx={{ color: "text.secondary", fontStyle: "italic" }}>
                    This section has not been generated for this plan.
                  </Typography>
                )}
              </AccordionDetails>
            </Accordion>
          );
        })}
      </Box>
    </ConsolePanel>
  );
}

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

function EditableProjectTitle({ name, onRename, light }: { name: string; onRename: (name: string) => void | Promise<void>; light?: boolean }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(name);

  useEffect(() => {
    if (!editing) setDraft(name);
  }, [name, editing]);

  const commit = () => {
    setEditing(false);
    const trimmed = draft.trim();
    if (trimmed && trimmed !== name) onRename(trimmed);
    else setDraft(name);
  };

  if (editing) {
    return (
      <TextField
        autoFocus
        size="small"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") commit();
          if (e.key === "Escape") { setDraft(name); setEditing(false); }
        }}
        sx={{ "& .MuiInputBase-input": { fontSize: tokens.fontSize.xl, fontWeight: 700, py: 0.5 } }}
      />
    );
  }

  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
      <Typography variant="h3" sx={{ fontSize: tokens.fontSize.xl, color: light ? "#FFFFFF" : undefined }}>{name}</Typography>
      <IconButton
        size="small"
        aria-label="Rename plan"
        onClick={() => setEditing(true)}
        sx={light ? { color: "rgba(255,255,255,0.8)", "&:hover": { color: "#fff", background: "rgba(255,255,255,0.12)" } } : undefined}
      >
        <span className="material-symbols-outlined" style={{ fontSize: 17 }}>edit</span>
      </IconButton>
    </Box>
  );
}

export function Workspace({
  prefillBrand,
  openProjectId,
  seedMessage,
  seedFile,
  initialStage,
  startMode = "direct",
}: {
  prefillBrand?: string | null;
  openProjectId?: string | null;
  seedMessage?: string | null;
  seedFile?: File | null;
  initialStage?: number;
  startMode?: "flow" | "direct";
}) {
  const ws = useWorkspace();
  // Who owns the window currently on screen — drives the chat header identity and the stage
  // marker hue. It does NOT drive the chrome: the top bar, sub-bar and every control stay blue.
  const stageAgentId = agentForStage(ws.stage);
  const stageAgent = STAGE_AGENTS[stageAgentId];
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [showFullPlan, setShowFullPlan] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const bootstrapped = useRef(false);
  const seeded = useRef(false);
  const sequentialStarted = useRef(false);

  // Entry routing: open the requested plan, or spin up a fresh one that lands
  // straight on the briefing intake — no "click to begin" empty state.
  useEffect(() => {
    if (bootstrapped.current) return;
    bootstrapped.current = true;
    if (openProjectId) ws.openProject(openProjectId, initialStage ?? 1);
    else ws.newProject(initialStage ?? 1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Once the fresh project's id lands, auto-send the seed (a brand pick or a typed
  // one-line requirement) and drop the intake. With no seed the intake stays open.
  useEffect(() => {
    if (openProjectId || seeded.current || !ws.projectId || !ws.showIntake) return;
    // A file import from Home takes priority: upload it into the fresh plan and drop the intake.
    if (seedFile) {
      seeded.current = true;
      ws.setShowIntake(false);
      ws.uploadFile(seedFile);
      return;
    }
    const seed = prefillBrand
      ? `I want to plan a campaign for ${prefillBrand}`
      : (seedMessage?.trim() || null);
    if (!seed) return;
    seeded.current = true;
    ws.setShowIntake(false);
    ws.sendMessage(seed);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ws.projectId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [ws.items]);

  useEffect(() => {
    if (startMode !== "flow" || sequentialStarted.current || !ws.projectId || !ws.studio.done) return;
    sequentialStarted.current = true;
    ws.runSequentialFlow();
  }, [startMode, ws.projectId, ws.studio.done, ws.runSequentialFlow]);

  return (
    // stageVars publishes the stage's marker hue as CSS variables for the six sanctioned marker
    // slots (stageTheme.ts). Nothing structural reads them: buttons, links, inputs, panel
    // headers and both bars resolve to Omni blue in every stage.
    <Box sx={{ ...stageVars(stageAgentId), display: "flex", flexDirection: "column", height: `calc(100vh - ${tokens.layout.topBarHeight}px)`, minHeight: 0 }}>
      <PlansDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        projects={ws.projects}
        activeId={ws.projectId}
        onOpenProject={(id) => { ws.openProject(id); setDrawerOpen(false); }}
        onNewProject={() => { ws.newProject(); setDrawerOpen(false); }}
        onDeleteProject={ws.deleteProject}
      />

      {/* Sub-bar: a darker shade of the app-bar gradient. Holds the plan title +
          rename + plans menu on the left, and the folder-tab WorkflowStepper spread
          across the rest — the active tab sits flush with the bar's bottom edge so
          it merges into the workspace below like the tab of a paper folder (no
          shadow under the bar, it would cut the seam). */}
      <Box
        sx={{
          flex: "0 0 auto",
          display: "flex",
          alignItems: "stretch",
          gap: 3,
          pl: 3,
          // No right padding: the spacer below reserves the chat pane's width instead, so
          // the tab strip ends exactly on the workspace/chat seam.
          pr: 0,
          // Breathing room between the app bar above and the tops of the folder tabs.
          pt: 2,
          pb: 0,
          backgroundColor: accent.primaryDark,
          position: "relative",
          zIndex: 1,
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, flex: "0 0 auto", py: 1 }}>
          <IconButton
            size="small"
            aria-label="Plan history"
            onClick={() => setDrawerOpen(true)}
            sx={{ color: "rgba(255,255,255,0.8)", "&:hover": { color: "#fff", background: "rgba(255,255,255,0.12)" } }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 20 }}>history</span>
          </IconButton>
          {ws.projectId && <EditableProjectTitle name={ws.projectName} onRename={ws.renameProject} light />}
        </Box>
        {ws.projectId && (
          <Box sx={{ flex: 1, minWidth: 0, display: "flex", alignItems: "flex-end" }}>
            <WorkflowStepper
              stage={ws.stage}
              onSelect={ws.setStage}
              subLabel={
                ws.studio.active || (ws.studio.sections.length > 0 && !ws.studio.done)
                  ? `SECTION ${Math.min(ws.studio.sections.length + 1, sectionTotal(ws.studio))}/${sectionTotal(ws.studio)}`
                  : undefined
              }
            />
          </Box>
        )}
        {/* Dead space over the chat pane, sized identically to it, so the tabs span the
            workspace column only — a tab that overhung the chat pointed at the wrong pane. */}
        <Box
          aria-hidden
          sx={{
            flex: `0 0 ${tokens.layout.chatPaneWidth}`,
            minWidth: `${tokens.layout.chatPaneMinWidth}px`,
          }}
        />
      </Box>

      <Box sx={{ display: "flex", flex: 1, minHeight: 0 }}>
      {/* Left rail: read-only table of contents for the Stage 1 Sequential Plan Studio build.
          Shown from the very start of Stage 1 (even during the intake brief, before the studio
          run has started) since all 19 titles are already known statically -- staying present
          the whole time avoids a layout jump once the build actually kicks off. */}
      {ws.projectId && ws.stage === 1 && (
        <PlanSectionsRail studio={ws.studio} />
      )}
      {/* Stages 2-4 get the same left-hand section nav as Stage 1, to jump between their panels. */}
      {ws.projectId && ws.stage === 2 && <StageSectionRail sections={ORCH_SECTIONS} />}
      {ws.projectId && ws.stage === 3 && <StageSectionRail sections={OPS_SECTIONS} />}
      {ws.projectId && ws.stage === 4 && <StageSectionRail sections={REPORT_SECTIONS} />}
      {ws.projectId && ws.stage === 5 && <StageSectionRail sections={OPS2_SECTIONS} />}

      {/* Same canvas as the chat pane: the folder-tab seam must be uniform across both panes. */}
      <Box component="aside" sx={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 380, minHeight: 0, backgroundColor: tokens.color.canvas }}>
        {ws.projectId && (
          <>
            {/* Keyed on the stage so switching tabs replays the entrance: the four stages are
                different documents, and swapping one for another on a single frame read as a
                glitch. The stage's own content already unmounts on switch, so the key costs
                nothing extra. */}
            <Box key={ws.stage} sx={{ flex: 1, overflowY: "auto", p: 3, pt: 3, animation: enterWith(enterRise) }}>
              {ws.stage === 1 && (ws.studio.active || ws.studio.sections.length > 0 || ws.studio.done) && (
                <>
                  {/* Sequential Plan Studio: no live section canvas during a build -- the left
                      rail carries build progress, and the plan itself renders once done. */}
                  {ws.studio.records.length > 0 && !ws.studio.done && (
                    <ConsolePanel id="decision-trail-anchor" title="Decision trail" icon="psychology" collapsible sx={{ mt: 3 }}>
                      <DecisionTrail records={ws.studio.records} dense onRevise={ws.reviseStudioDecision} />
                    </ConsolePanel>
                  )}
                  {ws.studio.done && (
                    <Box sx={{ mt: 3 }}>
                      <CampaignArtifacts projectId={ws.projectId} onSeeded={() => ws.setStage(2)} refreshToken={ws.artifactRefresh.planning} />
                      {ws.planHtml && (
                        <ArchivedPlanViews>
                          <PlanViewToggle showFull={showFullPlan} onToggle={() => setShowFullPlan((v) => !v)} />
                          {showFullPlan ? (
                            <PlanSummaryCard
                              projectId={ws.projectId}
                              planHtml={ws.planHtml}
                              planMarkdown={ws.planMarkdown}
                              planFrozen={ws.planFrozen}
                              planEditing={ws.planEditing}
                              sectionsProgress={null}
                              onBeginEdit={ws.beginPlanEdit}
                              onCancelEdit={ws.cancelPlanEdit}
                              onSaveEdit={ws.savePlanEdit}
                              onCloseUpdates={ws.closeUpdatesAction}
                            />
                          ) : (
                            <SimplePlanSummary />
                          )}
                        </ArchivedPlanViews>
                      )}
                      <FinalPlanSections studio={ws.studio} />
                    </Box>
                  )}
                </>
              )}
              {/* PLAN brief -- what you gave us, as opposed to the CAMPAIGN brief the run
                  produces (CampaignArtifacts, #campaign-brief-anchor). It renders for the whole
                  of stage 1, not just before the run starts: the inputs stay worth re-reading
                  while the plan is being built, and the left rail links here from the outset. */}
              {ws.stage === 1 && (
                <Box id="plan-brief-anchor">
                  <ConsolePanel title="Plan brief" icon="assignment" collapsible sx={{ mb: 3 }}>
                    <Typography variant="body2" sx={{ color: "text.secondary", mb: 1.5 }}>
                      What you asked for — the inputs this plan is being built from.
                    </Typography>
                    <BriefCard slots={ws.slots} inferred={ws.inferred} />
                  </ConsolePanel>
                </Box>
              )}
              {ws.stage === 1 && !(ws.studio.active || ws.studio.sections.length > 0 || ws.studio.done) && (
                <>
                  {/* Nothing to say before the brief completes — no placeholder card. */}
                  {ws.agents.length > 0 && (
                    <ConsolePanel title="Agent" icon="smart_toy" collapsible>
                      <AgentTeamPanel agents={ws.agents} caption={ws.teamCaption} />
                    </ConsolePanel>
                  )}
                  {ws.planHtml && (
                    <Box>
                      <CampaignArtifacts projectId={ws.projectId} onSeeded={() => ws.setStage(2)} refreshToken={ws.artifactRefresh.planning} />
                      <ArchivedPlanViews>
                        <PlanViewToggle showFull={showFullPlan} onToggle={() => setShowFullPlan((v) => !v)} />
                        {showFullPlan ? (
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
                        ) : (
                          <SimplePlanSummary />
                        )}
                      </ArchivedPlanViews>
                    </Box>
                  )}
                </>
              )}
              {ws.stage === 2 && (
                <StageOrchestration
                  result={ws.result}
                  projectId={ws.projectId}
                  refreshToken={ws.artifactRefresh.orchestration}
                />
              )}
              {ws.stage === 3 && (
                <StageOperations
                  result={ws.result}
                  projectId={ws.projectId}
                  agentBusy={ws.busy && ws.typingAuthor === "operations"}
                  refreshToken={ws.artifactRefresh.operations}
                />
              )}
              {ws.stage === 4 && <StageReporting result={ws.result} projectId={ws.projectId} />}
              {ws.stage === 5 && (
                <StageCampaignOps2
                  result={ws.result}
                  projectId={ws.projectId}
                  refreshToken={ws.artifactRefresh.operations}
                />
              )}
            </Box>
          </>
        )}
      </Box>

      {/* Right rail: the AI Assistant. Same conversation/composer as before -- moved from
          the left to the right so the middle column (plan content) reads first. */}
      {/* White pane against the grey workspace canvas: the conversation is a different kind of
          surface from the document being built, and the colour break is what says so. Bubbles
          carry a canvas-grey fill (ChatBubble.tsx) so they still read against it. */}
      <Box component="main" sx={{ flex: `0 0 ${tokens.layout.chatPaneWidth}`, minWidth: `${tokens.layout.chatPaneMinWidth}px`, display: "flex", flexDirection: "column", borderLeft: `1px solid ${tokens.color.outline}`, position: "relative", backgroundColor: tokens.color.surface }}>
        {!ws.projectId ? (
          <EmptyState>
            <span className="material-symbols-outlined" style={{ fontSize: 46, color: tokens.color.primary }}>hub</span>
            <Typography variant="body1">
              <b>Preparing your brief…</b>
              <br />
              Setting up a fresh plan. If nothing appears, start one manually.
            </Typography>
            <Button variant="contained" color="primary" onClick={() => ws.newProject()}>
              + New plan
            </Button>
          </EmptyState>
        ) : (
          <>
            {/* The stage's agent identity, stated once, directly above its conversation --
                the transcript below carries no avatars at all. White surface: the colour is
                carried by the avatar ring and the 2px rule under it, not by a filled band.
                A tinted panel behind the name made each stage read as a different product. */}
            <Box
              sx={{
                px: 2.5,
                py: 2,
                borderBottom: `2px solid ${stageMark.primary}`,
                backgroundColor: tokens.color.surface,
                display: "flex",
                alignItems: "center",
                flex: "0 0 auto",
              }}
            >
              <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, minWidth: 0 }}>
                <AgentAvatar id={stageAgent.id} size={40} />
                <Typography sx={{ fontWeight: 700, fontSize: tokens.fontSize.xl, lineHeight: 1.25 }}>
                  {stageAgent.name}
                </Typography>
              </Box>
            </Box>

            <Box ref={scrollRef} sx={{ flex: 1, overflowY: "auto", px: 2 }}>
              {ws.showIntake && (
                <IntakeCard
                  onSubmit={ws.submitIntake}
                  onSkip={() => ws.setShowIntake(false)}
                  onImport={(file) => { ws.setShowIntake(false); ws.uploadFile(file); }}
                />
              )}
              <ChatMessages
                items={ws.activeChatItems}
                onSkipPersonaOffer={ws.skipPersonaOffer}
                onRunPersonas={ws.runPersonas}
                onApplyFeedback={ws.applyFeedback}
                onOpenPersonaProfile={ws.openPersonaProfile}
                typingAuthor={ws.typingAuthor}
                onAnswerAsk={ws.answerStudioAsk}
                kickoffAwaitingStage={ws.kickoffAwaitingStage}
                onKickoffUsePlan={ws.onKickoffUsePlan}
                onKickoffWantUpload={ws.onKickoffWantUpload}
                onContinueStudioSection={ws.continueStudioSection}
              />
            </Box>

            <Box sx={{ p: 2, pt: 1.5 }}>
              {/* Chat stays usable the whole time the Sequential Plan Studio is building --
                  `busy` spans the entire multi-minute section-by-section build (it's only
                  cleared at an ask/run_done/error), so gating the composer on it would lock
                  the user out of chatting for most of Stage 1. Only a genuine single in-flight
                  chat request (outside an active studio run) disables it. */}
              <Composer
                disabled={ws.busy && !ws.studio.active}
                onSend={ws.sendMessage}
                onUpload={ws.handleUpload}
                agentName={stageAgent.name}
                {...(ws.stage === 1
                  ? { autoAssume: ws.autoAssume, onAutoAssumeChange: ws.toggleAutoAssume }
                  : {})}
              />
            </Box>
          </>
        )}
      </Box>
      </Box>
      <PersonaProfileModal personaId={ws.profileOpen} onClose={ws.closePersonaProfile} />
    </Box>
  );
}
