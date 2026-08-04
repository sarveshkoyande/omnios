import { Suspense, lazy } from "react";

// The Spline runtime is heavy (WebGL + scene loader) — lazy-load it so it never
// blocks the dashboard's first paint. Adapted from the shadcn/Tailwind original to
// this repo's MUI/Vite stack: the loading fallback is styled with inline styles
// (no Tailwind here), and the public `scene`/`className` API is unchanged.
const Spline = lazy(() => import("@splinetool/react-spline"));

interface InteractiveRobotSplineProps {
  scene: string;
  className?: string;
  style?: React.CSSProperties;
}

export function InteractiveRobotSpline({ scene, className, style }: InteractiveRobotSplineProps) {
  return (
    <Suspense
      fallback={
        <div
          className={className}
          style={{
            width: "100%",
            height: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 12,
            background: "#0B1220",
            color: "#fff",
            ...style,
          }}
        >
          <svg
            style={{ height: 20, width: 20, animation: "spline-spin 0.9s linear infinite" }}
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle style={{ opacity: 0.25 }} cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path
              style={{ opacity: 0.75 }}
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l2-2.647z"
            />
          </svg>
          <span style={{ fontSize: 15, fontWeight: 600 }}>Loading 3D scene…</span>
          <style>{"@keyframes spline-spin { to { transform: rotate(360deg); } }"}</style>
        </div>
      }
    >
      <Spline scene={scene} className={className} style={style} />
    </Suspense>
  );
}
