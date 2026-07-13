import { styled } from "@mui/material/styles";
import { personaInitials } from "./personaUtils";
import { shade } from "../../theme/tokens";

const Circle = styled("span")<{ size: number }>(({ size }) => ({
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  width: size,
  height: size,
  borderRadius: "50%",
  flex: `0 0 ${size}px`,
  fontSize: size * 0.36,
  fontWeight: 700,
  color: "#fff",
  background: "linear-gradient(135deg,#1768D1,#4AA6F2)",
  boxShadow: `0 0 0 2px ${shade(0.06)}, 0 1px 3px ${shade(0.25)}`,
}));

export function PersonaAvatar({ name, size = 32 }: { name: string; size?: number }) {
  return <Circle size={size}>{personaInitials(name)}</Circle>;
}
