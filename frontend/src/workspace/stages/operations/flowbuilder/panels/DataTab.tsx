import { useState } from "react";
import { useWorkflowStore } from "../store/useWorkflowStore";
import { DataFieldEditor } from "./DataFieldEditor";
import type { DataRecord, DataField } from "../schema/dataField";
import { emptyDataField } from "../schema/dataField";
import type { DataSet } from "../schema/stencil";

function fieldFromDef(def: DataSet["fields"][string]): DataField {
  const base = emptyDataField(def.type as DataField["type"]);
  const value = def.defaultValue;
  if (base.type === "fixedList" || base.type === "variableList") {
    return { ...base, options: (def.options as string[]) ?? [], value: (value as string) ?? null } as DataField;
  }
  if (base.type === "currency") {
    return { ...base, currency: (def.currency as string) ?? "USD", value: (value as number) ?? null } as DataField;
  }
  return { ...base, value: value ?? null } as DataField;
}

export function DataTab({
  data,
  onChangeData,
}: {
  data: DataRecord;
  onChangeData: (data: DataRecord) => void;
}) {
  const dataSets = useWorkflowStore((s) => s.document.dataSets);
  const [selectedDataSet, setSelectedDataSet] = useState<string>("");

  const updateField = (name: string, field: DataField) => onChangeData({ ...data, [name]: field });
  const renameField = (oldName: string, newName: string) => {
    if (!newName || newName === oldName || data[newName]) return;
    const { [oldName]: moved, ...rest } = data;
    onChangeData({ ...rest, [newName]: moved });
  };
  const deleteField = (name: string) => {
    const { [name]: _removed, ...rest } = data;
    onChangeData(rest);
  };
  const addField = () => {
    const name = window.prompt("New field name?");
    if (!name || data[name]) return;
    onChangeData({ ...data, [name]: emptyDataField("string") });
  };
  const applyDataSet = () => {
    const ds = dataSets.find((d) => d.id === selectedDataSet);
    if (!ds) return;
    const patch: DataRecord = {};
    for (const [name, def] of Object.entries(ds.fields)) patch[name] = fieldFromDef(def);
    onChangeData({ ...data, ...patch });
  };

  return (
    <div className="wf-tab-data">
      {dataSets.length > 0 && (
        <div className="wf-dataset-apply">
          <select value={selectedDataSet} onChange={(e) => setSelectedDataSet(e.target.value)}>
            <option value="">Apply a Data Set…</option>
            {dataSets.map((ds) => (
              <option key={ds.id} value={ds.id}>{ds.name}</option>
            ))}
          </select>
          <button disabled={!selectedDataSet} onClick={applyDataSet}>Apply</button>
        </div>
      )}

      {Object.entries(data).map(([name, field]) => (
        <DataFieldEditor
          key={name}
          name={name}
          field={field}
          onChange={(f) => updateField(name, f)}
          onRename={(newName) => renameField(name, newName)}
          onDelete={() => deleteField(name)}
        />
      ))}

      <button className="wf-add-field" onClick={addField}>+ Add field</button>
    </div>
  );
}
