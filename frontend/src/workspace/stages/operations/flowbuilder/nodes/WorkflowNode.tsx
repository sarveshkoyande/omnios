import { memo, useState } from "react";
import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import type { WorkflowNode as SchemaNode } from "../schema/node";
import type { Port, PortSide } from "../schema/port";
import { shapeKeyFor } from "../schema/nodeDefaults";
import { ShapeGeometry } from "./geometry";
import { defaultColorsFor } from "./styleDefaults";
import { evaluateDataGraphics } from "./dataGraphics";
import { AutoConnectOverlay } from "../interactions/AutoConnectOverlay";

export type WorkflowRFNodeData = { schemaNode: SchemaNode };
export type WorkflowRFNode = Node<WorkflowRFNodeData, "workflow">;

const SIDE_TO_POSITION: Record<PortSide, Position> = {
  top: Position.Top,
  right: Position.Right,
  bottom: Position.Bottom,
  left: Position.Left,
};

function portStyle(port: Port): React.CSSProperties {
  const pct = `${port.offset * 100}%`;
  if (port.side === "top" || port.side === "bottom") return { left: pct };
  return { top: pct };
}

function WorkflowNodeImpl({ id, data, selected }: NodeProps<WorkflowRFNode>) {
  const node = data.schemaNode;
  const { w, h } = node.size;
  const shapeKey = shapeKeyFor(node.type);
  const defaults = defaultColorsFor(node.type);
  const graphics = evaluateDataGraphics(node);
  const [hovered, setHovered] = useState(false);

  const fill = graphics.fill ?? node.style?.fill ?? defaults.fill;
  const stroke = graphics.stroke ?? node.style?.stroke ?? defaults.stroke;
  const strokeWidth = node.style?.strokeWidth ?? 2;
  const opacity = graphics.opacity ?? 1;

  return (
    <div
      className={`wf-node${selected ? " wf-node-selected" : ""}`}
      style={{ width: w, height: h, opacity }}
      aria-label={node.a11y?.title ?? node.label}
      role="group"
      tabIndex={0}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="wf-node-svg">
        <ShapeGeometry shapeKey={shapeKey} w={w} h={h} fill={fill} stroke={stroke} strokeWidth={strokeWidth} />
      </svg>
      <div className="wf-node-label">
        {node.label}
        {node.richLabel && <div className="wf-node-rich">{node.richLabel.markdown}</div>}
      </div>
      {graphics.badgeIcon && <div className="wf-node-badge" title={graphics.badgeIcon}>●</div>}
      {node.ports.map((port) => (
        <Handle
          key={port.id}
          id={port.id}
          type={port.direction === "in" ? "target" : "source"}
          position={SIDE_TO_POSITION[port.side]}
          style={portStyle(port)}
          title={port.name}
        />
      ))}
      {hovered && !node.locks?.move && <AutoConnectOverlay nodeId={id} />}
    </div>
  );
}

export const WorkflowNode = memo(WorkflowNodeImpl);

export const nodeTypes = { workflow: WorkflowNode };
