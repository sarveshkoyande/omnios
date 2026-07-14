import { keyframes } from "@emotion/react";
import { styled } from "@mui/material/styles";
import { tokens, glass, glassFallback, indigoTint } from "../theme/tokens";
import type { FeedItem } from "../api";

/**
 * TickerStrip — a translucent frosted rail of live market events. Ink text on
 * glass (AA), indigo event tags, a green LED for live-provenance items. Marquee
 * motion is paused on hover/focus and killed by the reduced-motion baseline.
 */
const scroll = keyframes`
  from { transform: translateX(0); }
  to { transform: translateX(-50%); }
`;

const Board = styled("div")({
  overflow: "hidden",
  whiteSpace: "nowrap",
  background: glassFallback,
  borderBottom: `1px solid ${indigoTint(0.12)}`,
  "@supports ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px)))": {
    background: glass.panel,
    backdropFilter: glass.blurLight,
    WebkitBackdropFilter: glass.blurLight,
  },
  "&:hover > div, &:focus-within > div": { animationPlayState: "paused" },
});

const Track = styled("div")({
  display: "inline-flex",
  alignItems: "center",
  animation: `${scroll} 90s linear infinite`,
});

const Item = styled("span")(({ theme }) => ({
  display: "inline-flex",
  alignItems: "center",
  gap: theme.spacing(2),
  padding: theme.spacing(1.5, 6),
  color: tokens.color.text,
  fontSize: tokens.fontSize.sm,
  borderRight: `1px solid ${indigoTint(0.1)}`,
}));

const Tag = styled("b")({
  color: tokens.color.primary,
  letterSpacing: "0.06em",
  textTransform: "uppercase",
  fontSize: tokens.fontSize.xs,
});

const Led = styled("i")({
  width: 7,
  height: 7,
  borderRadius: "50%",
  background: tokens.color.success,
  boxShadow: `0 0 5px ${tokens.color.success}`,
});

const TAG: Record<string, string> = {
  approval: "Approval", launch: "Launch", indication_change: "Indication",
  notice: "Notice", label_update: "Label", trial: "New trial", literature: "Literature",
};

export function TickerStrip({ feed }: { feed: FeedItem[] }) {
  if (!feed.length) return null;
  const sequence = (prefix: string) =>
    feed.map((f, i) => (
      <Item key={`${prefix}${i}`}>
        <Tag>{TAG[f.type] ?? f.type}</Tag>
        {f.provenance === "live" && <Led aria-label="live" />}
        {f.brand && <b>{f.brand}</b>}
        <span>{f.text}</span>
      </Item>
    ));
  return (
    <Board role="marquee" aria-label="Market events ticker">
      <Track>{sequence("a")}{sequence("b")}</Track>
    </Board>
  );
}
