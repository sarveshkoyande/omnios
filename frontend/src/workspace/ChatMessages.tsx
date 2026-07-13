import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { AgentAvatar } from "./Avatar";
import { AgentBubble, BanterBubble, ClarifyBadge, NarrationLine, TurnBubble, UserBubble } from "./ChatBubble";
import { ClarifyCard } from "./ClarifyCard";
import { PersonaApplyBar, PersonaApplyResultCard } from "./persona/PersonaApplyBar";
import { PersonaOfferCard } from "./persona/PersonaOfferCard";
import { PersonaReviewCard } from "./persona/PersonaReviewCard";
import { TypingDots } from "./TypingDots";
import type { ChatItem } from "./useWorkspace";
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
}: {
  items: ChatItem[];
  onSkipPersonaOffer: (itemId: string) => void;
  onRunPersonas: (itemId: string, ids: string[]) => void;
  onApplyFeedback: (itemId: string) => Promise<void>;
  onOpenPersonaProfile: (id: string) => void;
}) {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3, py: 2 }}>
      {items.map((item) => {
        switch (item.kind) {
          case "user":
            return (
              <UserBubble key={item.id} dangerouslySetInnerHTML={{ __html: renderMarkup(item.text ?? "") }} />
            );
          case "agent":
            return (
              <Box key={item.id} sx={{ display: "flex", gap: 2 }}>
                <AgentBubble sx={{ flex: 1 }}>
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
                  Your answer was folded straight in — the plan now reflects:
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
          case "narration":
            return <NarrationLine key={item.id}>{item.text}</NarrationLine>;
          case "turn": {
            const p = AGENT_PEOPLE[item.agentId ?? ""] ?? { c1: tokens.color.primary, name: item.agentId ?? "Agent" };
            return (
              <Box key={item.id} sx={{ display: "flex", gap: 2 }}>
                <AgentAvatar id={item.agentId ?? ""} />
                <TurnBubble accent={p.c1} sx={{ flex: 1 }}>
                  <Typography variant="caption" sx={{ fontWeight: 700, color: p.c1, display: "block", mb: 0.5 }}>
                    {p.name}
                  </Typography>
                  <span dangerouslySetInnerHTML={{ __html: renderMarkup(item.text ?? "") }} />
                </TurnBubble>
              </Box>
            );
          }
          case "banter": {
            const p = AGENT_PEOPLE[item.agentId ?? ""] ?? { c1: tokens.color.primary, name: item.agentId ?? "Agent" };
            return (
              <BanterBubble key={item.id} accent={p.c1}>
                <b>{p.name}</b> → {item.to}: {item.text}
              </BanterBubble>
            );
          }
          case "clarify":
            return (
              <Box key={item.id} sx={{ display: "flex", gap: 2 }}>
                <AgentBubble sx={{ flex: 1 }}>
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
          default:
            return null;
        }
      })}
    </Box>
  );
}
