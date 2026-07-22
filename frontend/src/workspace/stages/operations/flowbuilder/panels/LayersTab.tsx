import { useWorkflowStore } from "../store/useWorkflowStore";
import type { GroupKind } from "../schema/group";

const GROUP_KINDS: { kind: GroupKind; label: string }[] = [
  { kind: "lane", label: "+ Add Lane" },
  { kind: "pool", label: "+ Add Pool" },
  { kind: "container", label: "+ Add Container" },
];

export function LayersTab() {
  const page = useWorkflowStore((s) => s.getActivePage());
  const selection = useWorkflowStore((s) => s.selection);
  const createLayerCmd = useWorkflowStore((s) => s.createLayerCmd);
  const updateLayerCmd = useWorkflowStore((s) => s.updateLayerCmd);
  const deleteLayerCmd = useWorkflowStore((s) => s.deleteLayerCmd);
  const createGroupCmd = useWorkflowStore((s) => s.createGroupCmd);
  const deleteGroupCmd = useWorkflowStore((s) => s.deleteGroupCmd);
  const setElementLayersCmd = useWorkflowStore((s) => s.setElementLayersCmd);
  const select = useWorkflowStore((s) => s.select);

  const selectedNode = selection.nodeIds.length === 1 ? page.nodes.find((n) => n.id === selection.nodeIds[0]) : undefined;
  const selectedEdge = !selectedNode && selection.edgeIds.length === 1 ? page.edges.find((e) => e.id === selection.edgeIds[0]) : undefined;
  const membershipTarget = selectedNode
    ? { id: selectedNode.id, kind: "node" as const, layerIds: selectedNode.layerIds }
    : selectedEdge
    ? { id: selectedEdge.id, kind: "edge" as const, layerIds: selectedEdge.layerIds }
    : undefined;

  const addLayer = () => {
    const name = window.prompt("New layer name?", `Layer ${page.layers.length + 1}`);
    if (name) createLayerCmd(name);
  };

  const addGroup = (kind: GroupKind) => {
    const label = window.prompt(`${kind} name?`, kind[0].toUpperCase() + kind.slice(1));
    if (!label) return;
    const offset = page.groups.length * 40;
    createGroupCmd(kind, label, { x: offset, y: 520 + offset, w: 360, h: 240 });
  };

  const lanes = page.groups.filter((g) => g.kind === "lane" || g.kind === "pool" || g.kind === "container");

  return (
    <div className="wf-tab-layers">
      <div className="wf-palette-heading">Lanes & Containers</div>
      <div className="wf-lane-add-row">
        {GROUP_KINDS.map((g) => (
          <button key={g.kind} className="wf-add-field" onClick={() => addGroup(g.kind)}>{g.label}</button>
        ))}
      </div>
      {lanes.map((g) => (
        <div key={g.id} className="wf-layer-row" onClick={() => select({ groupIds: [g.id] })}>
          <span className="wf-layer-name">{g.kind}: {g.label}</span>
          <button
            className="wf-field-delete"
            onClick={(e) => { e.stopPropagation(); deleteGroupCmd(g.id, false); }}
            title="Delete"
          >
            ×
          </button>
        </div>
      ))}

      <div className="wf-palette-heading" style={{ marginTop: 14 }}>Layers</div>
      {page.layers.map((l) => (
        <div key={l.id} className="wf-layer-row">
          <input
            className="wf-layer-name-input"
            value={l.name}
            onChange={(e) => updateLayerCmd(l.id, { name: e.target.value })}
          />
          <label title="Visible"><input type="checkbox" checked={l.visible} onChange={(e) => updateLayerCmd(l.id, { visible: e.target.checked })} />👁</label>
          <label title="Locked"><input type="checkbox" checked={l.locked} onChange={(e) => updateLayerCmd(l.id, { locked: e.target.checked })} />🔒</label>
          <label title="Glue (allow new connections)"><input type="checkbox" checked={l.glue} onChange={(e) => updateLayerCmd(l.id, { glue: e.target.checked })} />🧲</label>
          <button className="wf-field-delete" onClick={() => deleteLayerCmd(l.id)} title="Delete layer">×</button>
        </div>
      ))}
      <button className="wf-add-field" onClick={addLayer}>+ Add layer</button>

      {membershipTarget && page.layers.length > 0 && (
        <>
          <div className="wf-palette-heading" style={{ marginTop: 14 }}>Selected element's layers</div>
          {page.layers.map((l) => {
            const checked = membershipTarget.layerIds.includes(l.id);
            return (
              <label key={l.id} className="wf-layer-membership-row">
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={(e) => {
                    const next = e.target.checked
                      ? [...membershipTarget.layerIds, l.id]
                      : membershipTarget.layerIds.filter((id) => id !== l.id);
                    setElementLayersCmd(membershipTarget.id, membershipTarget.kind, next);
                  }}
                />
                {l.name}
              </label>
            );
          })}
        </>
      )}
    </div>
  );
}
