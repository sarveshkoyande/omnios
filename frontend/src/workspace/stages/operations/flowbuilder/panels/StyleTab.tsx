import type { WorkflowNode, NodeStyle } from "../schema/node";
import type { DataGraphicRuleSchema } from "../schema/node";
import type { z } from "zod";

type DataGraphicRule = z.infer<typeof DataGraphicRuleSchema>;

export function StyleTab({ node, onChange }: { node: WorkflowNode; onChange: (patch: Partial<WorkflowNode>) => void }) {
  const s: NodeStyle = node.style ?? {};
  const classNamesText = (s.classNames ?? []).join(", ");
  const setStyle = (patch: Partial<NodeStyle>) => onChange({ style: { ...s, ...patch } });

  const rules = node.dataGraphics ?? [];
  const setRules = (next: DataGraphicRule[]) => onChange({ dataGraphics: next });
  const addRule = () => setRules([...rules, { rule: "data.status == 'Deprecated'", apply: { opacity: 0.6 } }]);
  const updateRule = (i: number, patch: Partial<DataGraphicRule>) =>
    setRules(rules.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  const updateApply = (i: number, key: string, value: string) => {
    const apply = { ...rules[i].apply };
    if (value === "") delete apply[key];
    else apply[key] = key === "opacity" ? Number(value) : value;
    updateRule(i, { apply });
  };
  const removeRule = (i: number) => setRules(rules.filter((_, idx) => idx !== i));

  return (
    <div className="wf-tab-style">
      <label className="wf-style-row">
        Fill
        <input type="color" value={s.fill ?? "#eeeeee"} onChange={(e) => setStyle({ fill: e.target.value })} />
      </label>
      <label className="wf-style-row">
        Stroke
        <input type="color" value={s.stroke ?? "#333333"} onChange={(e) => setStyle({ stroke: e.target.value })} />
      </label>
      <label className="wf-style-row">
        Stroke width
        <input
          type="number"
          min={0}
          max={10}
          value={s.strokeWidth ?? 2}
          onChange={(e) => setStyle({ strokeWidth: Number(e.target.value) })}
        />
      </label>
      <label className="wf-style-row">
        Class names
        <input
          type="text"
          placeholder="critical, milestone"
          value={classNamesText}
          onChange={(e) => setStyle({ classNames: e.target.value.split(",").map((c) => c.trim()).filter(Boolean) })}
        />
      </label>

      <div className="wf-datagraphics">
        <div className="wf-palette-heading">Data Graphics (conditional formatting)</div>
        {rules.map((r, i) => (
          <div key={i} className="wf-field-row">
            <div className="wf-field-head">
              <span className="wf-field-label">Rule {i + 1}</span>
              <button className="wf-field-delete" onClick={() => removeRule(i)} title="Remove rule">×</button>
            </div>
            <input
              type="text"
              value={r.rule}
              placeholder="data.sla > PT8H"
              onChange={(e) => updateRule(i, { rule: e.target.value })}
            />
            <div className="wf-field-inline">
              <input
                type="color"
                title="fill on match"
                value={(r.apply.fill as string) ?? "#ffffff"}
                onChange={(e) => updateApply(i, "fill", e.target.value)}
              />
              <input
                type="text"
                placeholder="badge icon"
                value={(r.apply.badgeIcon as string) ?? ""}
                onChange={(e) => updateApply(i, "badgeIcon", e.target.value)}
              />
              <input
                type="number"
                step={0.1}
                min={0}
                max={1}
                placeholder="opacity"
                value={(r.apply.opacity as number) ?? ""}
                onChange={(e) => updateApply(i, "opacity", e.target.value)}
              />
            </div>
          </div>
        ))}
        <button className="wf-add-field" onClick={addRule}>+ Add data graphic rule</button>
      </div>
    </div>
  );
}
