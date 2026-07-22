import type { DataField, DataFieldType } from "../schema/dataField";
import { emptyDataField } from "../schema/dataField";

// Section 3.2/2.4 typed Shape Data editors — one control per of the eight field types.

const DURATION_UNITS = [
  { code: "H", label: "hours" },
  { code: "D", label: "days" },
] as const;

function parseDuration(iso: string | null): { amount: number; unit: "H" | "D" } {
  const match = iso ? /^P(?:(\d+)D)?(?:T(?:(\d+)H)?)?$/.exec(iso) : null;
  if (match?.[1]) return { amount: Number(match[1]), unit: "D" };
  if (match?.[2]) return { amount: Number(match[2]), unit: "H" };
  return { amount: 0, unit: "H" };
}
function formatDuration(amount: number, unit: "H" | "D"): string {
  if (!amount) return "";
  return unit === "D" ? `P${amount}D` : `PT${amount}H`;
}

export function DataFieldEditor({
  name,
  field,
  onChange,
  onRename,
  onDelete,
}: {
  name: string;
  field: DataField;
  onChange: (field: DataField) => void;
  onRename?: (newName: string) => void;
  onDelete?: () => void;
}) {
  const label = field.label ?? name;

  return (
    <div className="wf-field-row" title={field.prompt}>
      <div className="wf-field-head">
        <label className="wf-field-label">{label}</label>
        <select
          className="wf-field-type"
          value={field.type}
          onChange={(e) => onChange(emptyDataField(e.target.value as DataFieldType))}
        >
          {(["string", "number", "fixedList", "variableList", "duration", "date", "currency", "boolean"] as DataFieldType[]).map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        {onDelete && <button className="wf-field-delete" onClick={onDelete} title="Remove field">×</button>}
      </div>

      {field.type === "string" && (
        <input
          type="text"
          value={field.value ?? ""}
          onChange={(e) => onChange({ ...field, value: e.target.value })}
        />
      )}

      {field.type === "number" && (
        <input
          type="number"
          value={field.value ?? ""}
          onChange={(e) => onChange({ ...field, value: e.target.value === "" ? null : Number(e.target.value) })}
        />
      )}

      {field.type === "boolean" && (
        <label className="wf-toggle">
          <input
            type="checkbox"
            checked={field.value ?? false}
            onChange={(e) => onChange({ ...field, value: e.target.checked })}
          />
          {field.value ? "true" : "false"}
        </label>
      )}

      {field.type === "date" && (
        <input
          type="date"
          value={field.value ?? ""}
          onChange={(e) => onChange({ ...field, value: e.target.value || null })}
        />
      )}

      {field.type === "currency" && (
        <div className="wf-field-inline">
          <input
            type="number"
            value={field.value ?? ""}
            onChange={(e) => onChange({ ...field, value: e.target.value === "" ? null : Number(e.target.value) })}
          />
          <input
            type="text"
            className="wf-currency-code"
            value={field.currency}
            maxLength={3}
            onChange={(e) => onChange({ ...field, currency: e.target.value.toUpperCase() })}
          />
        </div>
      )}

      {field.type === "duration" && (
        <div className="wf-field-inline">
          {(() => {
            const { amount, unit } = parseDuration(field.value);
            return (
              <>
                <input
                  type="number"
                  min={0}
                  value={amount || ""}
                  onChange={(e) => onChange({ ...field, value: formatDuration(Number(e.target.value) || 0, unit) || null })}
                />
                <select value={unit} onChange={(e) => onChange({ ...field, value: formatDuration(amount, e.target.value as "H" | "D") || null })}>
                  {DURATION_UNITS.map((u) => (
                    <option key={u.code} value={u.code}>{u.label}</option>
                  ))}
                </select>
              </>
            );
          })()}
        </div>
      )}

      {field.type === "fixedList" && (
        <select value={field.value ?? ""} onChange={(e) => onChange({ ...field, value: e.target.value || null })}>
          <option value="" disabled>Select…</option>
          {field.options.map((o) => (
            <option key={o} value={o}>{o}</option>
          ))}
        </select>
      )}

      {field.type === "variableList" && (
        <>
          <input
            list={`wf-datalist-${name}`}
            value={field.value ?? ""}
            onChange={(e) => onChange({ ...field, value: e.target.value || null })}
          />
          <datalist id={`wf-datalist-${name}`}>
            {(field.options ?? []).map((o) => (
              <option key={o} value={o} />
            ))}
          </datalist>
        </>
      )}

      {onRename && (
        <input
          className="wf-field-name"
          value={name}
          onChange={(e) => onRename(e.target.value)}
          title="Field name (internal key)"
        />
      )}
    </div>
  );
}
