/** Indegene DS 4.Ai outline icon set (INDEGENE-DS-4AI-DESIGN-GUIDELINES.md Section 2:
 *  "Icon stroke: 1.7px, round caps, round joins, 24px viewBox"). Replaces the emoji
 *  pictographs this app used before -- every icon prop that used to hold an HTML entity
 *  now holds `<Icon name="..." />`. One shared wrapper keeps every icon's stroke width,
 *  cap/join style, and viewBox identical, the way the DS's own components.css icons are
 *  drawn (see 12-app-shell-nav.html's nav-item icons for the reference shape grammar). */
import type { SVGProps } from "react";

const PATHS: Record<string, React.ReactNode> = {
  persona: <><circle cx="12" cy="8" r="4" /><path d="M4 21c0-4 3.6-7 8-7s8 3 8 7" /></>,
  users: <><circle cx="9" cy="8" r="3.5" /><path d="M2.5 21c0-3.5 3-6 6.5-6s6.5 2.5 6.5 6" /><path d="M16 4.5a3.5 3.5 0 0 1 0 7" /><path d="M17.5 15c2.8.6 4.5 2.8 4.5 6" /></>,
  shield: <path d="M12 2 20 5.5v6c0 5-3.4 8.8-8 10.5-4.6-1.7-8-5.5-8-10.5v-6L12 2z" />,
  star: <path d="M12 2.5 15 9l7 .8-5.2 4.9L18.2 21.5 12 17.8 5.8 21.5 7.2 14.7 2 9.8 9 9z" />,
  alertTriangle: <><path d="M10.6 3.5 2 19h20L13.4 3.5a1.6 1.6 0 0 0-2.8 0z" /><path d="M12 9.5v4.5" /><circle cx="12" cy="17" r=".7" fill="currentColor" stroke="none" /></>,
  barChart: <><path d="M4 20V10" /><path d="M12 20V4" /><path d="M20 20v-7" /></>,
  document: <><path d="M6 2h9l5 5v15H6z" /><path d="M15 2v5h5" /><path d="M9 13h6M9 17h6" /></>,
  palette: <><path d="M12 3a9 9 0 1 0 0 18c1.2 0 2-.9 2-2 0-.6-.2-1-.5-1.4-.3-.4-.5-.8-.5-1.4 0-1.1.9-2 2-2H17a4 4 0 0 0 4-4c0-4-4-7.2-9-7.2z" /><circle cx="7.5" cy="10.5" r="1.1" fill="currentColor" stroke="none" /><circle cx="11" cy="7" r="1.1" fill="currentColor" stroke="none" /><circle cx="15.5" cy="8.5" r="1.1" fill="currentColor" stroke="none" /></>,
  mic: <><path d="M12 2.5a3 3 0 0 0-3 3v6.5a3 3 0 0 0 6 0V5.5a3 3 0 0 0-3-3z" /><path d="M6 11a6 6 0 0 0 12 0" /><path d="M12 17v4M9 21h6" /></>,
  mail: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m4 6.5 8 6.5 8-6.5" /></>,
  smartphone: <><rect x="7" y="2.5" width="10" height="19" rx="2" /><path d="M11 18h2" /></>,
  scale: <><path d="M12 3v18M8 21h8" /><path d="M12 3 5 6.5 3 12h4l2-5.5z" /><path d="M12 3 19 6.5 21 12h-4l-2-5.5z" /><path d="M3 12a2 2 0 0 0 4 0M17 12a2 2 0 0 0 4 0" /></>,
  map: <><path d="M9 3 4 5v16l5-2 6 2 5-2V3l-5 2-6-2z" /><path d="M9 3v16M15 5v16" /></>,
  heartPulse: <path d="M20 8.5c0-2.5-2-4.5-4.5-4.5-1.5 0-2.8.7-3.5 1.8-.7-1.1-2-1.8-3.5-1.8C6 4 4 6 4 8.5c0 4 5 7 8 9.7 1.1-1 2.5-2.2 3.8-3.5H13l-1.5-3-2 4.5-1.5-3H4.8" />,
  zap: <path d="M13 2 4 14h6l-1 8 9-12h-6l1-8z" />,
  wallet: <><path d="M3 7a2 2 0 0 1 2-2h13a1 1 0 0 1 1 1v3" /><path d="M3 7v11a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-6a1 1 0 0 0-1-1h-4a2.5 2.5 0 0 0 0 5h5" /></>,
  link: <><path d="M9.5 14.5 14.5 9.5" /><path d="M11 6.5 12.8 4.7a3.5 3.5 0 0 1 5 5L15.8 11.5" /><path d="M13 17.5 11.2 19.3a3.5 3.5 0 0 1-5-5L8.2 12.5" /></>,
  eye: <><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7z" /><circle cx="12" cy="12" r="3" /></>,
  message: <path d="M4 4h16v12H8l-4 4V4z" />,
  check: <path d="M4 12.5 9.5 18 20 6" />,
  user: <><circle cx="12" cy="8" r="4" /><path d="M4 21c0-4 3.6-7 8-7s8 3 8 7" /></>,
  chevronDown: <path d="m6 9 6 6 6-6" />,
  arrowRight: <path d="M5 12h14M13 6l6 6-6 6" />,
  plus: <path d="M12 5v14M5 12h14" />,
  arrowLeft: <path d="M19 12H5M11 6l-6 6 6 6" />,
  target: <><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="5" /><circle cx="12" cy="12" r="1.2" fill="currentColor" stroke="none" /></>,
  radar: <><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="5" /><path d="M12 12 18 6" /></>,
  layers: <><path d="m12 3 9 5-9 5-9-5 9-5z" /><path d="m3 13 9 5 9-5" /></>,
  route: <><circle cx="6" cy="19" r="2" /><circle cx="18" cy="5" r="2" /><path d="M8 19h8a3 3 0 0 0 0-6H8a3 3 0 0 1 0-6h8" /></>,
  branch: <><circle cx="6" cy="5" r="2" /><circle cx="6" cy="19" r="2" /><circle cx="18" cy="9" r="2" /><path d="M6 7v10M18 11c0 4-6 3-12 6" /></>,
  flask: <><path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 1.7 3h10.6a2 2 0 0 0 1.7-3l-5-9V3" /><path d="M7.5 15h9" /></>,
  refresh: <><path d="M20 11a8 8 0 0 0-14.5-4.5L4 8" /><path d="M4 3v5h5" /><path d="M4 13a8 8 0 0 0 14.5 4.5L20 16" /><path d="M20 21v-5h-5" /></>,
  sparkles: <><path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8z" /><path d="M19 15l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z" /></>,
};

export function Icon({ name, size = 24, ...rest }: { name: keyof typeof PATHS; size?: number } & SVGProps<SVGSVGElement>) {
  return (
    <svg
      width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true"
      {...rest}
    >
      {PATHS[name]}
    </svg>
  );
}
