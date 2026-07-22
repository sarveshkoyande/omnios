import { memo } from "react";
import { NodeResizer, type NodeProps, type Node } from "@xyflow/react";
import type { Group } from "../schema/group";
import { useWorkflowStore } from "../store/useWorkflowStore";

export type LaneRFNodeData = { schemaGroup: Group };
export type LaneRFNode = Node<LaneRFNodeData, "lane">;

const KIND_COLOR: Record<Group["kind"], string> = {
  group: "#e2e8f0",
  lane: "#e0e7ff",
  pool: "#ede9fe",
  container: "#dcfce7",
  list: "#fef9c3",
  subgraph: "#e2e8f0",
  phase: "#fde2e2",
};

function LaneNodeImpl({ data, selected }: NodeProps<LaneRFNode>) {
  const group = data.schemaGroup;
  const updateGroupCmd = useWorkflowStore((s) => s.updateGroupCmd);
  const deleteGroupCmd = useWorkflowStore((s) => s.deleteGroupCmd);
  const w = group.bounds?.w ?? 320;
  const h = group.bounds?.h ?? 220;

  const rename = () => {
    const next = window.prompt("Lane / container name?", group.label);
    if (next) updateGroupCmd(group.id, { label: next });
  };

  const remove = () => {
    if (window.confirm(`Delete "${group.label}"? Members will be ungrouped.`)) {
      deleteGroupCmd(group.id, false);
    }
  };

  return (
    <div
      className="wf-lane"
      style={{
        width: w,
        height: h,
        background: KIND_COLOR[group.kind] ?? "#e2e8f0",
        outline: selected ? "2px solid #2563eb" : "1px solid #94a3b8",
      }}
    >
      <NodeResizer
        isVisible={selected}
        minWidth={160}
        minHeight={120}
        onResizeEnd={(_, params) =>
          updateGroupCmd(group.id, { bounds: { x: params.x, y: params.y, w: params.width, h: params.height } })
        }
      />
      <div className="wf-lane-header" onDoubleClick={rename} title="Drag to move · double-click to rename">
        <span className="wf-lane-kind">{group.kind}</span>
        <span className="wf-lane-label">{group.label}</span>
        <button className="wf-lane-delete" onClick={remove} title="Delete">×</button>
      </div>
    </div>
  );
}

export const LaneNode = memo(LaneNodeImpl);
