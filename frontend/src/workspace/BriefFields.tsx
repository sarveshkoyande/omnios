import type { ReactNode } from "react";
import Box from "@mui/material/Box";
import { tokens } from "../theme/tokens";

/**
 * The brief as a label-over-value grid rather than a stack of label-left/value-right rows.
 *
 * Short scalar fields (brand, lifecycle, duration) pair up two to a row; long prose fields
 * (objective, constraints) take the full width, because a captured paragraph squeezed into a
 * half column wraps to five lines and stops being scannable. Each field declares its own
 * `span` so that choice lives with the field, not in the layout code.
 */
export interface BriefField {
  label: string;
  /** Pre-rendered so callers can pass an ExpandableValue, chips, or plain text. */
  value: ReactNode;
  /** 2 = full width. Clamped to the column count, so span-2 is simply full width at 1 column. */
  span?: 1 | 2;
}

/**
 * Which cells open a row. Needed because full-width fields break the even/odd alternation a
 * CSS-only `nth-child` rule would rely on — with a span-2 field in the middle, "every second
 * cell" stops meaning "second column" and the dividers land in the wrong places.
 */
function layout(fields: BriefField[], columns: number) {
  let col = 0;
  return fields.map((field) => {
    const span = Math.min(field.span ?? 1, columns);
    if (col + span > columns) col = 0;
    const rowStart = col === 0;
    col = (col + span) % columns;
    return { rowStart, span };
  });
}

export function BriefFields({
  fields,
  columns = 2,
}: {
  fields: BriefField[];
  /** 1 in the chat rail — it is far too narrow for two columns regardless of viewport width,
   *  which is why this is a prop and not a viewport breakpoint. */
  columns?: 1 | 2;
}) {
  if (!fields.length) return null;
  const meta = layout(fields, columns);
  return (
    <Box sx={{ display: "grid", gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}>
      {fields.map((field, i) => {
        const { rowStart, span } = meta[i];
        return (
          <Box
            key={field.label}
            sx={{
              minWidth: 0,
              gridColumn: span === 2 ? "1 / -1" : "auto",
              py: 1.5,
              // The divider between columns hangs off the cell that is NOT starting the row,
              // so it never draws at the left edge of the panel.
              pl: rowStart ? 0 : 3,
              borderTop: `1px solid ${tokens.color.outline}`,
              borderLeft: rowStart ? "none" : `1px solid ${tokens.color.outline}`,
            }}
          >
            <Box
              component="div"
              sx={{ fontSize: tokens.fontSize.xs, color: tokens.color.inkSecondary, mb: 0.5, lineHeight: 1.4 }}
            >
              {field.label}
            </Box>
            <Box
              component="div"
              sx={{
                fontSize: tokens.fontSize.sm,
                fontWeight: 700,
                color: tokens.color.text,
                lineHeight: 1.5,
                minWidth: 0,
                overflowWrap: "anywhere",
              }}
            >
              {field.value}
            </Box>
          </Box>
        );
      })}
    </Box>
  );
}
