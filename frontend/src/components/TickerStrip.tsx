import { keyframes } from "@emotion/react";
import { styled } from "@mui/material/styles";
import { tokens, shade, light } from "../theme/tokens";
import type { FeedItem } from "../api";

/**
 * TickerStrip — airport split-flap departure board: a dark machined strip with
 * mono type, riveted frame, and event tags as illuminated indicators. Marquee
 * motion is killed globally by the prefers-reduced-motion baseline override.
 * Contrast on the dark strip: surface text 17.9:1; warning tag 5.6:1;
 * success LED 5.4:1 — all AA.
 */
const scroll = keyframes`
  from { transform: translateX(0); }
  to { transform: translateX(-50%); }
`;

const Board = styled("div")({
  overflow: "hidden",
  whiteSpace: "nowrap",
  background: `linear-gradient(180deg, ${shade(0.98)}, ${tokens.color.text} 30%, ${shade(0.92)})`,
  borderTop: `1px solid ${shade(0.7)}`,
  borderBottom: `1px solid ${shade(0.7)}`,
  boxShadow: `inset 0 3px 8px rgba(0,0,0,0.5), inset 0 -1px 0 ${light(0.1)}, 0 1px 0 ${light(0.9)}`,
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
  padding: theme.spacing(2, 6),
  color: tokens.color.surface,
  fontFamily: tokens.font.mono,
  fontSize: tokens.fontSize.xs,
  borderRight: `1px solid ${light(0.14)}`,
}));

const Tag = styled("b")({
  color: tokens.color.secondary,
  letterSpacing: "0.06em",
  textTransform: "uppercase",
});

const Led = styled("i")({
  width: 7,
  height: 7,
  borderRadius: "50%",
  background: tokens.color.success,
  boxShadow: `0 0 4px ${tokens.color.success}`,
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
      {/* Sequence duplicated so the -50% loop is seamless. */}
      <Track>{sequence("a")}{sequence("b")}</Track>
    </Board>
  );
}
