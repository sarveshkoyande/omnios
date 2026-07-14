import { styled } from "@mui/material/styles";
import { indigoTint, tokens } from "../../theme/tokens";

/** Shared data-table look for the workflow stages — dense, legible, glass-tinted. */
export const PlanTable = styled("table")({
  width: "100%",
  borderCollapse: "collapse",
  margin: "6px 0",
  fontSize: tokens.fontSize.sm,
  "th, td": {
    border: `1px solid ${indigoTint(0.12)}`,
    padding: "7px 10px",
    textAlign: "left",
    verticalAlign: "top",
  },
  th: { color: tokens.color.primary, fontWeight: 700, background: indigoTint(0.06) },
});
