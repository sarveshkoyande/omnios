import { useMemo, useState } from "react";
import { useWorkflowStore } from "../store/useWorkflowStore";
import { BUILT_IN_CATALOG, CATEGORY_LABELS, CATEGORY_ORDER, catalogByCategory, type CatalogEntry } from "./stencilCatalog";
import { DRAG_NODE_TYPE, DRAG_MASTER_ID } from "../interactions/dragTypes";
import type { StencilMaster } from "../schema/stencil";
import type { NodeType } from "../schema/nodeTypes";

function PaletteItem({ label, onDragStart }: { label: string; onDragStart: (e: React.DragEvent) => void }) {
  return (
    <div
      className="wf-palette-item"
      draggable
      onDragStart={onDragStart}
      title={`Drag onto canvas to add "${label}"`}
    >
      {label}
    </div>
  );
}

export function Palette() {
  const [search, setSearch] = useState("");
  const customMasters = useWorkflowStore((s) => s.document.customMasters);
  const selection = useWorkflowStore((s) => s.selection);
  const saveNodeAsMasterCmd = useWorkflowStore((s) => s.saveNodeAsMasterCmd);
  const quickShapeTypes = useWorkflowStore((s) => s.quickShapeTypes);
  const setQuickShapeTypes = useWorkflowStore((s) => s.setQuickShapeTypes);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return BUILT_IN_CATALOG;
    return BUILT_IN_CATALOG.filter((e) => e.label.toLowerCase().includes(q) || e.type.includes(q));
  }, [search]);

  const grouped = useMemo(() => catalogByCategory(filtered), [filtered]);

  const onNodeTypeDragStart = (e: React.DragEvent, type: NodeType) => {
    e.dataTransfer.setData(DRAG_NODE_TYPE, type);
    e.dataTransfer.effectAllowed = "copy";
  };

  const onMasterDragStart = (e: React.DragEvent, master: StencilMaster) => {
    e.dataTransfer.setData(DRAG_MASTER_ID, master.id);
    e.dataTransfer.effectAllowed = "copy";
  };

  const canSaveMaster = selection.nodeIds.length === 1;
  const onSaveMaster = () => {
    if (!canSaveMaster) return;
    const name = window.prompt("Name for this custom master?", "My Shape");
    if (name) saveNodeAsMasterCmd(selection.nodeIds[0], name);
  };

  return (
    <aside className="wf-palette">
      <input
        className="wf-palette-search"
        type="search"
        placeholder="Search shapes…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        aria-label="Search stencil palette"
      />

      <div className="wf-quickshapes">
        <div className="wf-palette-heading">Quick Shapes</div>
        <div className="wf-quickshapes-strip">
          {quickShapeTypes.map((type) => {
            const entry = BUILT_IN_CATALOG.find((e) => e.type === type);
            if (!entry) return null;
            return (
              <div
                key={type}
                className="wf-quickshape"
                draggable
                onDragStart={(e) => onNodeTypeDragStart(e, type)}
                title={entry.label}
              >
                {entry.label}
              </div>
            );
          })}
        </div>
      </div>

      {customMasters.length > 0 && (
        <section className="wf-palette-section">
          <div className="wf-palette-heading">My Shapes</div>
          {customMasters.map((m) => (
            <PaletteItem key={m.id} label={m.label} onDragStart={(e) => onMasterDragStart(e, m)} />
          ))}
        </section>
      )}

      {CATEGORY_ORDER.map((cat) => {
        const entries: CatalogEntry[] = grouped.get(cat) ?? [];
        if (entries.length === 0) return null;
        return (
          <section key={cat} className="wf-palette-section">
            <div className="wf-palette-heading">{CATEGORY_LABELS[cat]}</div>
            {entries.map((entry) => (
              <PaletteItem
                key={entry.type}
                label={entry.label}
                onDragStart={(e) => onNodeTypeDragStart(e, entry.type)}
              />
            ))}
          </section>
        );
      })}

      <button className="wf-save-master" disabled={!canSaveMaster} onClick={onSaveMaster}>
        Save selected as custom master
      </button>
      {quickShapeTypes.length > 0 && selection.nodeIds.length === 1 && (
        <button
          className="wf-save-master"
          onClick={() => {
            // pin the selected node's type as a quick shape (drop the oldest favorite)
            const page = useWorkflowStore.getState().getActivePage();
            const node = page.nodes.find((n) => n.id === selection.nodeIds[0]);
            if (!node) return;
            setQuickShapeTypes([node.type, ...quickShapeTypes.filter((t) => t !== node.type)].slice(0, 4));
          }}
        >
          Pin selected as Quick Shape
        </button>
      )}
    </aside>
  );
}
