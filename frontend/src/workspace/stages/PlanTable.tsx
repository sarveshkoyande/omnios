import { styled } from "@mui/material/styles";
import { shade, tokens } from "../../theme/tokens";

/** Shared data-table look for the workflow stages — plain, dense, printed-ledger style. */
export const PlanTable = styled("table")({
  width: "100%",
  borderCollapse: "collapse",
  margin: "6px 0",
  fontSize: tokens.fontSize.xs + 1,
  "th, td": {
    border: `1px solid ${shade(0.14)}`,
    padding: "6px 8px",
    textAlign: "left",
    verticalAlign: "top",
  },
  th: { color: shade(0.55), fontWeight: 700, background: shade(0.03) },
});
