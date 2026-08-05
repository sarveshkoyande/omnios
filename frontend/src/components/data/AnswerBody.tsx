import { useMemo } from "react";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { DataBlockView } from "./DataBlockView";
import { parseAnswer, renderInline } from "./markdownAnswer";
import type { DataBlock } from "../../api";
import { tokens } from "../../theme/tokens";

/**
 * An agent's answer, rendered properly.
 *
 * Two sources of tabular content, both ending up in the same renderer:
 *  - `dataBlocks` — structured results the agent pulled straight from the HCP 360 panel
 *    (strategy/data_blocks.py). These drill down, because they carry the query behind them.
 *  - pipe tables inside `text` — anything the model typed out itself. Same grid and chart,
 *    no drill-down, since there's no query to narrow.
 */
export function AnswerBody({ text, dataBlocks }: { text: string; dataBlocks?: DataBlock[] | null }) {
  const nodes = useMemo(() => parseAnswer(text), [text]);

  return (
    <Box sx={{ minWidth: 0, "& code": { fontFamily: "monospace", background: tokens.color.canvas, px: 0.5, borderRadius: tokens.radius.sm } }}>
      {nodes.map((node, i) => {
        switch (node.kind) {
          case "heading":
            return (
              <Typography
                key={i}
                sx={{
                  fontSize: node.level <= 2 ? tokens.fontSize.lg : tokens.fontSize.md,
                  fontWeight: 700,
                  mt: i === 0 ? 0 : 1.5,
                  mb: 0.5,
                }}
                dangerouslySetInnerHTML={{ __html: renderInline(node.text) }}
              />
            );
          case "list":
            return (
              <Box
                key={i}
                component={node.ordered ? "ol" : "ul"}
                sx={{ my: 0.75, pl: 2.5, "& li": { mb: 0.25 } }}
              >
                {node.items.map((item, k) => (
                  <li key={k} dangerouslySetInnerHTML={{ __html: renderInline(item) }} />
                ))}
              </Box>
            );
          case "table":
            return <DataBlockView key={i} block={node.block} />;
          default:
            return (
              <Box
                key={i}
                component="p"
                sx={{ my: i === 0 ? 0 : 0.75, "&:first-of-type": { mt: 0 } }}
                dangerouslySetInnerHTML={{ __html: renderInline(node.text) }}
              />
            );
        }
      })}
      {(dataBlocks ?? []).map((block) => <DataBlockView key={block.id} block={block} />)}
    </Box>
  );
}

/** Whether an answer needs the full lane width — a shrink-wrapped bubble would squash a grid. */
export function answerNeedsFullWidth(text: string, dataBlocks?: DataBlock[] | null): boolean {
  if (dataBlocks?.length) return true;
  return parseAnswer(text).some((node) => node.kind === "table");
}
