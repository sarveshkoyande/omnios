import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { GlassPanel } from "../glass/primitives";
import { tokens, indigoTint } from "../theme/tokens";
import type { BriefExtractItem } from "./types";

/**
 * BriefExtractCard — shown after a brand plan is imported. Names WHICH brief fields the agent
 * read out of the document, as tags. Deliberately not the values: the captured values are
 * whole paragraphs lifted from the deck, and rendering them here duplicated the brief panel
 * while pushing the chat rail into a wall of text. The brief panel is where you read them;
 * this card only answers "what did it find?".
 */
export function BriefExtractCard({ items }: { items: BriefExtractItem[] }) {
  return (
    <GlassPanel tier="A" sx={{ p: 3.5, borderLeft: `4px solid ${tokens.color.primary}`, minWidth: 0 }}>
      <Box sx={{ display: "flex", alignItems: "center", gap: 1.25, mb: 0.5 }}>
        <span className="material-symbols-outlined" style={{ fontSize: 22, color: tokens.color.primary }}>
          description
        </span>
        <Typography sx={{ fontSize: tokens.fontSize.md, fontWeight: 700, color: "text.primary" }}>
          Imported from your brand plan
        </Typography>
      </Box>
      <Typography variant="body2" sx={{ color: "text.secondary", mb: 1.5, lineHeight: 1.5 }}>
        {items.length} detail{items.length === 1 ? "" : "s"} pulled from your document. These are now on
        the brief. I'll ask about anything important that's still missing.
      </Typography>
      <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75 }}>
        {items.map((it) => (
          <Box
            key={it.key}
            component="span"
            sx={{
              fontSize: tokens.fontSize.xs,
              fontWeight: 700,
              color: tokens.color.primary,
              background: tokens.color.infoSoft,
              border: `1px solid ${indigoTint(0.18)}`,
              borderRadius: tokens.radius.pill,
              px: 1.5,
              py: 0.5,
              lineHeight: 1.4,
              whiteSpace: "nowrap",
            }}
          >
            {it.label}
          </Box>
        ))}
      </Box>
    </GlassPanel>
  );
}
