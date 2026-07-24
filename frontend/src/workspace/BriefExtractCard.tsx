import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { GlassPanel, DefinitionRow } from "../glass/primitives";
import { ExpandableValue } from "./BriefCard";
import { tokens } from "../theme/tokens";
import type { BriefExtractItem } from "./types";

/**
 * BriefExtractCard — shown after a brand plan is imported. Lists exactly which brief fields
 * the agent read out of the document, so the user can see what was captured (and what wasn't)
 * before the run. Mirrors the brief panel's DefinitionRow styling.
 */
export function BriefExtractCard({ items }: { items: BriefExtractItem[] }) {
  return (
    <GlassPanel tier="A" sx={{ p: 3.5, borderLeft: `4px solid ${tokens.color.primary}`, minWidth: 0 }}>
      <Box sx={{ display: "flex", alignItems: "center", gap: 1.25, mb: 0.5 }}>
        <span className="material-symbols-outlined" style={{ fontSize: 22, color: tokens.color.primary }}>
          description
        </span>
        <Typography sx={{ fontSize: 15, fontWeight: 600, color: "text.primary" }}>
          Imported from your brand plan
        </Typography>
      </Box>
      <Typography variant="body2" sx={{ color: "text.secondary", mb: 1.5, lineHeight: 1.5 }}>
        {items.length} detail{items.length === 1 ? "" : "s"} pulled from your document. These are now on
        the brief. I'll ask about anything important that's still missing.
      </Typography>
      <Box>
        {items.map((it) => (
          <DefinitionRow
            key={it.key}
            label={it.label}
            // Same one-line + "See more" treatment as the workspace brief panel: these values
            // are whole paragraphs lifted from the deck, and this card sits in the narrow chat rail.
            value={<ExpandableValue short={String(it.value ?? "")} full={String(it.value ?? "")} />}
          />
        ))}
      </Box>
    </GlassPanel>
  );
}
