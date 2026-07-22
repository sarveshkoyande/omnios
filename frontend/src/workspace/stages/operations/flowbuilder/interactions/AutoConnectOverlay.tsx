import type { PortSide } from "../schema/port";
import { DRAG_AUTOCONNECT_SOURCE } from "./dragTypes";

// Section 4: "AutoConnect: hovering a node shows 4 directional arrows; drag an arrow
// onto an existing node to connect to it." Drag-only by design — new nodes are only
// ever created explicitly (palette drag-drop, or drop on an edge to insert), never as
// a side effect of starting a connection. Pure presentational overlay — WorkflowNode
// owns the store calls (it already has the schema node in scope).

const ARROW_POSITION: Record<PortSide, React.CSSProperties> = {
  top: { top: -22, left: "50%", transform: "translateX(-50%)" },
  right: { right: -22, top: "50%", transform: "translateY(-50%)" },
  bottom: { bottom: -22, left: "50%", transform: "translateX(-50%)" },
  left: { left: -22, top: "50%", transform: "translateY(-50%)" },
};

const ARROW_GLYPH: Record<PortSide, string> = { top: "↑", right: "→", bottom: "↓", left: "←" };

export function AutoConnectOverlay({ nodeId }: { nodeId: string }) {
  return (
    <>
      {(["top", "right", "bottom", "left"] as PortSide[]).map((side) => (
        <button
          key={side}
          type="button"
          // "nodrag" exempts the button from React Flow's node-drag handler, whose
          // mousedown preventDefault otherwise swallows the HTML5 dragstart entirely.
          className="wf-autoconnect-arrow nodrag"
          style={ARROW_POSITION[side]}
          draggable
          onDragStart={(e) => {
            e.dataTransfer.setData(DRAG_AUTOCONNECT_SOURCE, nodeId);
            e.dataTransfer.effectAllowed = "link";
          }}
          onClick={(e) => e.stopPropagation()}
          title={`Drag onto an existing node to connect (${side})`}
        >
          {ARROW_GLYPH[side]}
        </button>
      ))}
    </>
  );
}
