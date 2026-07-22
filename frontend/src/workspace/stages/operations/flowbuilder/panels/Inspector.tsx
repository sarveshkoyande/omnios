import { useState } from "react";
import { useWorkflowStore } from "../store/useWorkflowStore";
import { DataTab } from "./DataTab";
import { StyleTab } from "./StyleTab";
import { ValidationTab } from "./ValidationTab";
import { LayersTab } from "./LayersTab";

type TabId = "data" | "style" | "validation" | "layers";

export function Inspector() {
  const [tab, setTab] = useState<TabId>("data");
  const selection = useWorkflowStore((s) => s.selection);
  const page = useWorkflowStore((s) => s.getActivePage());
  const updateNodeDataCmd = useWorkflowStore((s) => s.updateNodeDataCmd);
  const updateNodeCmd = useWorkflowStore((s) => s.updateNodeCmd);

  const selectedNode = selection.nodeIds.length === 1 ? page.nodes.find((n) => n.id === selection.nodeIds[0]) : undefined;
  const selectedEdge = selection.edgeIds.length === 1 && selection.nodeIds.length === 0
    ? page.edges.find((e) => e.id === selection.edgeIds[0])
    : undefined;

  const tabs: { id: TabId; label: string }[] = [
    { id: "data", label: "Data" },
    { id: "style", label: "Style" },
    { id: "validation", label: "Validation" },
    { id: "layers", label: "Layers" },
  ];

  return (
    <aside className="wf-inspector">
      <div className="wf-inspector-tabs">
        {tabs.map((t) => (
          <button
            key={t.id}
            className={`wf-inspector-tab${tab === t.id ? " active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="wf-inspector-body">
        {tab === "data" && (
          selectedNode ? (
            <DataTab data={selectedNode.data} onChangeData={(data) => updateNodeDataCmd(selectedNode.id, data)} />
          ) : selectedEdge ? (
            <p className="wf-inspector-empty">Edges are read-only now. Connection data stays fixed to preserve the flow.</p>
          ) : (
            <p className="wf-inspector-empty">Select a single node or edge to edit its data.</p>
          )
        )}
        {tab === "style" && (
          selectedNode ? (
            <StyleTab node={selectedNode} onChange={(patch) => updateNodeCmd(selectedNode.id, patch)} />
          ) : selectedEdge ? (
            <p className="wf-inspector-empty">Edges are read-only now. Routing, endpoints, and labels are locked.</p>
          ) : (
            <p className="wf-inspector-empty">Select a single node or edge to edit its style.</p>
          )
        )}
        {tab === "validation" && <ValidationTab />}
        {tab === "layers" && (
          selectedEdge ? (
            <p className="wf-inspector-empty">Edges are read-only now. Layer membership is locked with the connection.</p>
          ) : (
            <LayersTab />
          )
        )}
      </div>
    </aside>
  );
}
