import type { WorkflowEdge } from "../schema/edge";
import { ArrowheadSchema, RoutingSchema, CurveSchema, LineStyleSchema, LineJumpsSchema, EdgeTypeSchema } from "../schema/edge";

export function EdgeStyleTab({ edge, onChange }: { edge: WorkflowEdge; onChange: (patch: Partial<WorkflowEdge>) => void }) {
  const line = edge.line;
  const setLine = (patch: Partial<WorkflowEdge["line"]>) => onChange({ line: { ...line, ...patch } });

  return (
    <div className="wf-tab-style">
      <label className="wf-style-row">
        Edge type
        <select value={edge.type} onChange={(e) => onChange({ type: e.target.value as WorkflowEdge["type"] })}>
          {EdgeTypeSchema.options.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </label>
      <label className="wf-style-row">
        Color
        <input type="color" value={line.color} onChange={(e) => setLine({ color: e.target.value })} />
      </label>
      <label className="wf-style-row">
        Weight
        <input type="number" min={1} max={10} value={line.weight} onChange={(e) => setLine({ weight: Number(e.target.value) })} />
      </label>
      <label className="wf-style-row">
        Line style
        <select value={line.style} onChange={(e) => setLine({ style: e.target.value as typeof line.style })}>
          {LineStyleSchema.options.map((v) => <option key={v} value={v}>{v}</option>)}
        </select>
      </label>
      <label className="wf-style-row">
        Routing
        <select value={line.routing} onChange={(e) => setLine({ routing: e.target.value as typeof line.routing })}>
          {RoutingSchema.options.map((v) => <option key={v} value={v}>{v}</option>)}
        </select>
      </label>
      <label className="wf-style-row">
        Line jumps
        <select value={line.lineJumps} onChange={(e) => setLine({ lineJumps: e.target.value as typeof line.lineJumps })}>
          {LineJumpsSchema.options.map((v) => <option key={v} value={v}>{v}</option>)}
        </select>
      </label>
      <label className="wf-style-row">
        Curve
        <select value={line.curve} onChange={(e) => setLine({ curve: e.target.value as typeof line.curve })}>
          {CurveSchema.options.map((v) => <option key={v} value={v}>{v}</option>)}
        </select>
      </label>
      <label className="wf-style-row">
        Arrow start
        <select value={line.arrowStart} onChange={(e) => setLine({ arrowStart: e.target.value as typeof line.arrowStart })}>
          {ArrowheadSchema.options.map((v) => <option key={v} value={v}>{v}</option>)}
        </select>
      </label>
      <label className="wf-style-row">
        Arrow end
        <select value={line.arrowEnd} onChange={(e) => setLine({ arrowEnd: e.target.value as typeof line.arrowEnd })}>
          {ArrowheadSchema.options.map((v) => <option key={v} value={v}>{v}</option>)}
        </select>
      </label>
      <label className="wf-style-row">
        Animated
        <input
          type="checkbox"
          checked={edge.animation?.enabled ?? false}
          onChange={(e) => onChange({ animation: { ...edge.animation, enabled: e.target.checked } })}
        />
      </label>
      <label className="wf-style-row">
        Source glue
        <select
          value={edge.source.glue}
          onChange={(e) => onChange({ source: { ...edge.source, glue: e.target.value as "static" | "dynamic" } })}
        >
          <option value="static">static</option>
          <option value="dynamic">dynamic</option>
        </select>
      </label>
      <label className="wf-style-row">
        Target glue
        <select
          value={edge.target.glue}
          onChange={(e) => onChange({ target: { ...edge.target, glue: e.target.value as "static" | "dynamic" } })}
        >
          <option value="static">static</option>
          <option value="dynamic">dynamic</option>
        </select>
      </label>
      <label className="wf-style-row">
        Label
        <input type="text" value={edge.label ?? ""} onChange={(e) => onChange({ label: e.target.value })} />
      </label>
    </div>
  );
}
