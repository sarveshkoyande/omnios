import TextField from "@mui/material/TextField";
import { styled } from "@mui/material/styles";
import { tokens } from "../theme/tokens";

/**
 * InsetTextField — a milled input well. The theme's MuiOutlinedInput override
 * already recesses every field (inset shadow, AA focus ring); this wrapper adds
 * the "instrument readout" treatment for data-entry wells: mono value type and
 * an engraved uppercase label. Use for search boxes and numeric/config fields.
 */
export const InsetTextField = styled(TextField)(({ theme }) => ({
  "& .MuiOutlinedInput-input": {
    fontFamily: tokens.font.mono,
    fontSize: tokens.fontSize.sm,
  },
  "& .MuiInputLabel-root": {
    fontFamily: tokens.font.mono,
    fontSize: tokens.fontSize.xs,
    fontWeight: 700,
    letterSpacing: "0.08em",
    textTransform: "uppercase",
    color: theme.palette.text.secondary,
    "&.Mui-focused": { color: theme.palette.primary.main },
  },
}));
