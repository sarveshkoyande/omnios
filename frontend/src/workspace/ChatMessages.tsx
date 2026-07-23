import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { AgentAvatar } from "./Avatar";
import { BriefExtractCard } from "./BriefExtractCard";
import { AgentBubble, ClarifyBadge, NarrationLine, StatusLine, TurnBubble, UserBubble } from "./ChatBubble";
import { ClarifyCard } from "./ClarifyCard";
import { PersonaApplyBar, PersonaApplyResultCard } from "./persona/PersonaApplyBar";
import { PersonaOfferCard } from "./persona/PersonaOfferCard";
import { PersonaReviewCard } from "./persona/PersonaReviewCard";
import { AskCard } from "./studio/AskCard";
import { StudioContinueCard } from "./studio/StudioContinueCard";
import { KickoffCard } from "./KickoffCard";
import { TypingDots } from "./TypingDots";
import type { ChatItem } from "./useWorkspace";
import type { StudioAsk } from "./studio/studioTypes";
import type { StageAgentId } from "./types";
import { AGENT_PEOPLE } from "./types";
import { tokens } from "../theme/tokens";

function renderMarkup(text: string) {
  const esc = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return esc.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/\*(.+?)\*/g, "<em>$1</em>").replace(/\n/g, "<br>");
}

export function ChatMessages({
  items,
  onSkipPersonaOffer,
  onRunPersonas,
  onApplyFeedback,
  onOpenPersonaProfile,
  typingAuthor,
  onAnswerAsk,
  kickoffAwaitingStage,
  onKickoffUsePlan,
  onKickoffWantUpload,
  onContinueStudioSection,
}: {
  items: ChatItem[];
  onSkipPersonaOffer: (itemId: string) => void;
  onRunPersonas: (itemId: string, ids: string[]) => void;
  onApplyFeedback: (itemId: string) => Promise<void>;
  onOpenPersonaProfile: (id: string) => void;
  typingAuthor?: string | null;
  onAnswerAsk?: (itemId: string, ask: StudioAsk, value: string) => void;
  kickoffAwaitingStage?: StageAgentId | null;
  onKickoffUsePlan?: (itemId: string, stageId: StageAgentId) => void;
  onKickoffWantUpload?: (itemId: string, stageId: StageAgentId) => void;
  onContinueStudioSection?: (itemId: string) => void;
}) {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 4, py: 2.5 }}>
      {items.map((item) => {
        switch (item.kind) {
          case "user":
            return (
              <Box key={item.id} sx={{ display: "flex", justifyContent: "flex-end", minWidth: 0 }}>
                <UserBubble dangerouslySetInnerHTML={{ __html: renderMarkup(item.text ?? "") }} />
              </Box>
            );
          case "agent":
            return (
              <Box key={item.id} sx={{ display: "flex", gap: 2, minWidth: 0, justifyContent: "flex-start" }}>
                <AgentBubble>
                  <span dangerouslySetInnerHTML={{ __html: renderMarkup(item.text ?? "") }} />
                  {item.clarify && (
                    <Box sx={{ mt: 2, pt: 2, borderTop: `1px dashed rgba(17,24,39,0.16)` }}>
                      <ClarifyCard clarify={item.clarify} />
                    </Box>
                  )}
                </AgentBubble>
              </Box>
            );
          case "plan-update":
            return (
              <AgentBubble key={item.id}>
                <b>Plan updated</b>
                <Typography variant="body2" sx={{ mt: 0.5, mb: 0.5 }}>
                  Your answer was folded straight in. The plan now reflects:
                </Typography>
                {item.updatedSections?.length ? (
                  <Box component="ul" sx={{ m: 0, pl: 2 }}>
                    {item.updatedSections.map((s) => (
                      <li key={s}>{s}</li>
                    ))}
                  </Box>
                ) : (
                  <Typography variant="caption" sx={{ color: "text.secondary" }}>Folded into the plan.</Typography>
                )}
              </AgentBubble>
            );
          case "brief-extract":
            return item.extracted?.length ? (
              <BriefExtractCard key={item.id} items={item.extracted} />
            ) : null;
          case "narration":
            return <NarrationLine key={item.id}>{item.text}</NarrationLine>;
          case "turn": {
            const p = AGENT_PEOPLE[item.agentId ?? ""] ?? { c1: tokens.color.primary, name: item.agentId ?? "Agent" };
            return (
              <Box key={item.id} sx={{ display: "flex", gap: 2, minWidth: 0, justifyContent: "flex-start" }}>
                <AgentAvatar id={item.agentId ?? ""} />
                <TurnBubble accent={p.c1}>
                  <Typography variant="caption" sx={{ fontWeight: 700, color: p.c1, display: "block", mb: 0.5 }}>
                    {p.name}
                  </Typography>
                  <span dangerouslySetInnerHTML={{ __html: renderMarkup(item.text ?? "") }} />
                </TurnBubble>
              </Box>
            );
          }
          case "banter":
            // Ambient background activity from the agent's internal work-steps —
            // deliberately not attributed to a second persona, just a quiet caption.
            return <StatusLine key={item.id}>{item.text}</StatusLine>;
          case "clarify":
            return (
              <Box key={item.id} sx={{ display: "flex", gap: 2, minWidth: 0, justifyContent: "flex-start" }}>
                <AgentBubble>
                  <ClarifyBadge sx={{ mb: 1.5 }}>Sign-off needed</ClarifyBadge>
                  {item.clarify && <ClarifyCard clarify={item.clarify} />}
                </AgentBubble>
              </Box>
            );
          case "typing":
            return (
              <AgentBubble key={item.id} sx={{ display: "inline-block" }}>
                <TypingDots />
              </AgentBubble>
            );
          case "persona-offer":
            return item.personaOffer ? (
              <PersonaOfferCard
                key={item.id}
                offer={item.personaOffer}
                onRun={(ids) => onRunPersonas(item.id, ids)}
                onSkip={() => onSkipPersonaOffer(item.id)}
                onOpenProfile={onOpenPersonaProfile}
              />
            ) : null;
          case "persona-review":
            return item.personaReview ? (
              <PersonaReviewCard key={item.id} review={item.personaReview} onOpenProfile={onOpenPersonaProfile} />
            ) : null;
          case "persona-apply-bar":
            return <PersonaApplyBar key={item.id} onApply={() => onApplyFeedback(item.id)} />;
          case "persona-apply-result":
            return <PersonaApplyResultCard key={item.id} changes={item.applyChanges ?? []} />;
          case "studio-ask":
            return item.ask ? (
              <AskCard
                key={item.id}
                ask={item.ask}
                ownerName={item.askOwnerName || "The team"}
                answered={item.askAnswered}
                onAnswer={(value) => onAnswerAsk?.(item.id, item.ask!, value)}
              />
            ) : null;
          case "studio-continue":
            return (
              <StudioContinueCard
                key={item.id}
                sectionTitle={item.continueSectionTitle}
                resolved={item.continueResolved}
                onContinue={() => onContinueStudioSection?.(item.id)}
              />
            );
          case "kickoff-choice":
            return item.kickoffStage ? (
              <KickoffCard
                key={item.id}
                stageId={item.kickoffStage}
                resolved={!!item.kickoffResolved}
                awaitingInput={kickoffAwaitingStage === item.kickoffStage && !item.kickoffResolved}
                onUsePlan={() => onKickoffUsePlan?.(item.id, item.kickoffStage!)}
                onWantUpload={() => onKickoffWantUpload?.(item.id, item.kickoffStage!)}
              />
            ) : null;
          default:
            return null;
        }
      })}
      {typingAuthor && (
        <Box sx={{ display: "flex", gap: 2, alignItems: "center" }}>
          {AGENT_PEOPLE[typingAuthor] && <AgentAvatar id={typingAuthor} size={30} />}
          <AgentBubble sx={{ display: "inline-block", py: 1.25 }}>
            <TypingDots />
          </AgentBubble>
        </Box>
      )}
    </Box>
  );
}
