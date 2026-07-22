import { toPng, toSvg } from "html-to-image";
import { getNodesBounds, getViewportForBounds, type ReactFlowInstance } from "@xyflow/react";
import { downloadDataUrl } from "./download";

// Section 4 "Export: ... SVG/PNG". Standard React Flow pattern: fit the ELK/user layout
// bounds into a target image size, temporarily apply that viewport transform to
// `.react-flow__viewport`, and rasterize it with html-to-image.
export async function exportCanvasImage(
  rf: ReactFlowInstance,
  kind: "png" | "svg",
  filename: string
): Promise<void> {
  const nodes = rf.getNodes();
  if (nodes.length === 0) return;
  const bounds = getNodesBounds(nodes);
  const width = 1600;
  const height = 1200;
  const viewport = getViewportForBounds(bounds, width, height, 0.1, 2, 0.15);

  const el = window.document.querySelector<HTMLElement>(".react-flow__viewport");
  if (!el) return;

  const fn = kind === "png" ? toPng : toSvg;
  const dataUrl = await fn(el, {
    backgroundColor: "#f8fafc",
    width,
    height,
    style: {
      width: `${width}`,
      height: `${height}`,
      transform: `translate(${viewport.x}px, ${viewport.y}px) scale(${viewport.zoom})`,
    },
  });
  downloadDataUrl(filename, dataUrl);
}
