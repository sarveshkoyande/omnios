import type { ReactNode } from "react";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";
import Box from "@mui/material/Box";
import { styled } from "@mui/material/styles";
import { shade, light, tokens } from "../theme/tokens";

/**
 * ConsolePanel — card-stock panel screwed to the desk. Theme's MuiPaper gives
 * the base material; this wrapper adds the engraved header plate and standard
 * panel padding so sections across the app stay identical.
 */
const PanelRoot = styled(Paper)(({ theme }) => ({
  padding: theme.spacing(4),
  borderRadius: tokens.radius.md,
}));

/** Engraved section label: letterpress = dark text with a white under-highlight. */
const EngravedTitle = styled(Typography)({
  fontFamily: tokens.font.mono,
  fontSize: tokens.fontSize.xs,
  fontWeight: 700,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: shade(0.62),
  textShadow: `0 1px 0 ${light(0.9)}`,
});

/** Embossed groove under the header, per the divider recipe. */
const HeaderGroove = styled("div")(({ theme }) => ({
  borderTop: `1px solid ${shade(0.16)}`,
  boxShadow: `0 1px 0 ${light(0.9)}`,
  margin: theme.spacing(2, 0, 3),
}));

export function ConsolePanel({
  title,
  action,
  children,
  ...rest
}: {
  title?: string;
  action?: ReactNode;
  children: ReactNode;
} & React.ComponentProps<typeof PanelRoot>) {
  return (
    <PanelRoot {...rest}>
      {title && (
        <>
          <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2 }}>
            <EngravedTitle>{title}</EngravedTitle>
            {action}
          </Box>
          <HeaderGroove />
        </>
      )}
      {children}
    </PanelRoot>
  );
}
