import { useState } from "react";
import { styled } from "@mui/material/styles";
import { AGENT_PEOPLE } from "./types";
import { shade } from "../theme/tokens";

/** Laminated ID-badge portrait: photo over a gradient-monogram fallback. */
const Ring = styled("span")<{ size: number }>(({ size }) => ({
  position: "relative",
  display: "inline-flex",
  width: size,
  height: size,
  borderRadius: "50%",
  overflow: "hidden",
  boxShadow: `0 0 0 2px ${shade(0.06)}, 0 1px 3px ${shade(0.25)}`,
  flex: `0 0 ${size}px`,
}));

const Photo = styled("img")({
  position: "absolute",
  inset: 0,
  width: "100%",
  height: "100%",
  objectFit: "cover",
});

export function AgentAvatar({ id, size = 38 }: { id: string; size?: number }) {
  const p = AGENT_PEOPLE[id] ?? { initials: "?", c1: "#1768D1", c2: "#4AA6F2", name: id, photo: "" };
  const [photoFailed, setPhotoFailed] = useState(false);
  const gradId = `ag-${id}-${size}`;
  return (
    <Ring size={size}>
      <svg viewBox="0 0 40 40" width={size} height={size} aria-hidden="true">
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor={p.c1} />
            <stop offset="1" stopColor={p.c2} />
          </linearGradient>
        </defs>
        <circle cx="20" cy="20" r="20" fill={`url(#${gradId})`} />
        <text x="20" y="22" textAnchor="middle" dominantBaseline="central" fontSize="14" fontWeight={700} fill="#fff">
          {p.initials}
        </text>
      </svg>
      {p.photo && !photoFailed && (
        <Photo src={p.photo} alt="" loading="lazy" onError={() => setPhotoFailed(true)} />
      )}
    </Ring>
  );
}
