import { useMemo, useState } from "react";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import IconButton from "@mui/material/IconButton";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { DataGrid, type GridColDef, type GridRowParams } from "@mui/x-data-grid";
import { BlockChart, chartableColumns, type ChartMode } from "./BlockChart";
import { HcpDetailPanel } from "./HcpDetailPanel";
import { fetchHcpCrossTab, type DataBlock, type DataBlockColumn } from "../../api";
import { accent } from "../../theme/stageTheme";
import { tokens } from "../../theme/tokens";

const DIM_LABELS: Record<string, string> = {
  specialty: "Specialty",
  state: "State",
  preferred_channel: "Preferred channel",
  segment: "Segment",
  writing_persona: "Writing persona",
  brand: "Brand",
};

type Row = Record<string, string | number | null>;
type ViewMode = "table" | ChartMode;

/**
 * One step of the drill-down. Level 0 is the block the agent returned; each further level is
 * a /api/hcp360/cross-tab result narrowed by the row that was clicked to open it.
 */
type Level = {
  title: string;
  columns: DataBlockColumn[];
  rows: Row[];
  groupBy: string[];
  filters: Record<string, string>;
  drillDims: string[];
  total: number;
};

const dimLabel = (dim: string) => DIM_LABELS[dim] ?? dim;

const filterCaption = (filters: Record<string, string>) =>
  Object.entries(filters).map(([k, v]) => `${dimLabel(k).toLowerCase()}: ${v}`).join(", ");

function baseLevel(block: DataBlock): Level {
  return {
    title: block.title,
    columns: block.columns ?? [],
    rows: block.rows ?? [],
    groupBy: block.group_by ?? [],
    filters: block.filters ?? {},
    drillDims: block.drill_dims ?? [],
    total: block.total ?? 0,
  };
}

/** CSV of exactly what's on screen — the one export people actually ask a chat answer for. */
function toCsv(columns: DataBlockColumn[], rows: Row[]): string {
  const cell = (value: unknown) => {
    const text = value == null ? "" : String(value);
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  return [
    columns.map((c) => cell(c.label)).join(","),
    ...rows.map((r) => columns.map((c) => cell(r[c.key])).join(",")),
  ].join("\n");
}

/**
 * An agent answer's panel result, rendered as a real table rather than a pasted markdown one:
 * sortable/filterable grid, a chart of the same rows, and click-through drill-down.
 *
 * Drill-down is driven entirely by the block's own `filters` + `drill_dims` (see
 * strategy/data_blocks.py) — clicking a row pins that row's dimension values as filters and
 * re-queries grouped by whichever dimension you pick, so the component never needs to know
 * what the HCP 360 panel contains.
 */
export function DataBlockView({ block }: { block: DataBlock }) {
  const [trail, setTrail] = useState<Level[]>(() => [baseLevel(block)]);
  const [view, setView] = useState<ViewMode>("table");
  const [menu, setMenu] = useState<{ anchor: HTMLElement; row: Row } | null>(null);
  const [detailNpi, setDetailNpi] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const level = trail[trail.length - 1];
  const isRoster = block.kind === "roster" && trail.length === 1;
  // A roster's only numeric column is the NPI, so it *looks* chartable while a bar chart of
  // NPI numbers means nothing. Rosters are a list of people, not a measure.
  const canChart = !isRoster && !!chartableColumns(level.columns);

  const gridColumns = useMemo<GridColDef[]>(
    () =>
      level.columns.map((col) => ({
        field: col.key,
        headerName: col.label,
        flex: col.type === "number" ? 0.5 : 1,
        minWidth: col.type === "number" ? 110 : 150,
        type: col.type === "number" ? ("number" as const) : ("string" as const),
      })),
    [level.columns],
  );

  const gridRows = useMemo(
    () => level.rows.map((row, i) => ({ id: i, ...row })),
    [level.rows],
  );

  async function drillInto(row: Row, dim: string) {
    setMenu(null);
    setBusy(true);
    setError(null);
    // The clicked row pins every dimension currently in view, on top of the filters that
    // already produced this level — that combination IS the row the user clicked on.
    const filters = { ...level.filters };
    level.groupBy.forEach((d) => {
      const value = row[d];
      if (value != null && value !== "") filters[d] = String(value);
    });
    try {
      const result = await fetchHcpCrossTab([dim], filters);
      setTrail((prev) => [
        ...prev,
        {
          title: `HCPs by ${dimLabel(dim).toLowerCase()} — ${filterCaption(filters)}`,
          columns: [
            { key: dim, label: dimLabel(dim), type: "text" },
            { key: "count", label: "HCPs", type: "number" },
          ],
          rows: result.rows,
          groupBy: [dim],
          filters,
          drillDims: Object.keys(DIM_LABELS).filter((d) => d !== dim && !(d in filters)),
          total: result.total,
        },
      ]);
      setView("table");
    } catch {
      setError("Couldn't drill into that row.");
    } finally {
      setBusy(false);
    }
  }

  function onRowClick(params: GridRowParams, event: React.MouseEvent) {
    const row = params.row as Row;
    if (isRoster) {
      const key = block.row_key ?? "npi_number__c";
      const npi = Number(row[key]);
      setDetailNpi(Number.isFinite(npi) && detailNpi !== npi ? npi : null);
      return;
    }
    if (!level.drillDims.length) return;
    setMenu({ anchor: event.currentTarget as HTMLElement, row });
  }

  if (block.kind === "stat") {
    return (
      <Box sx={{ my: 1.5, p: 2, borderRadius: tokens.radius.md, border: `1px solid ${tokens.color.outline}`, background: accent.container }}>
        <Typography sx={{ fontSize: tokens.fontSize.md, color: accent.onContainer }}>{block.title}</Typography>
        <Typography sx={{ fontSize: tokens.fontSize.display, fontWeight: 800, color: accent.primary, lineHeight: 1.1 }}>
          {(block.value ?? 0).toLocaleString()}
        </Typography>
        <Typography sx={{ fontSize: tokens.fontSize.md, color: "text.secondary" }}>{block.label ?? "HCPs"}</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ my: 1.5, borderRadius: tokens.radius.md, border: `1px solid ${tokens.color.outline}`, background: tokens.color.surface, overflow: "hidden" }}>
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap", px: 1.5, py: 1.25, borderBottom: `1px solid ${tokens.color.outline}`, background: accent.tint04 }}>
        <Box sx={{ minWidth: 0, flex: 1 }}>
          <Typography sx={{ fontSize: tokens.fontSize.md, fontWeight: 700 }}>{level.title}</Typography>
          <Typography sx={{ fontSize: tokens.fontSize.md, color: "text.secondary" }}>
            {level.rows.length.toLocaleString()} row{level.rows.length === 1 ? "" : "s"}
            {/* Only worth stating when it isn't just the row count restated — on a roster the
                two are the same number, on a breakdown the total is the population behind it. */}
            {!isRoster && level.total ? ` · ${level.total.toLocaleString()} HCPs` : ""}
            {block.source ? ` · ${block.source}` : ""}
          </Typography>
        </Box>
        {canChart && (
          <ToggleButtonGroup
            size="small"
            exclusive
            value={view}
            onChange={(_, next) => next && setView(next)}
            sx={{ "& .MuiToggleButton-root": { px: 1.25, py: 0.4, fontSize: tokens.fontSize.md, textTransform: "none" } }}
          >
            <ToggleButton value="table">Table</ToggleButton>
            <ToggleButton value="bar">Bar</ToggleButton>
            <ToggleButton value="pie">Pie</ToggleButton>
          </ToggleButtonGroup>
        )}
        <Tooltip title="Copy as CSV">
          <IconButton size="small" onClick={() => navigator.clipboard?.writeText(toCsv(level.columns, level.rows))}>
            <span className="material-symbols-outlined" style={{ fontSize: 20 }}>content_copy</span>
          </IconButton>
        </Tooltip>
      </Box>

      {trail.length > 1 && (
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.75, flexWrap: "wrap", px: 1.5, py: 1, borderBottom: `1px solid ${tokens.color.outline}` }}>
          {trail.map((step, i) => (
            <Chip
              key={i}
              size="small"
              label={i === 0 ? "All results" : filterCaption(step.filters)}
              variant={i === trail.length - 1 ? "filled" : "outlined"}
              onClick={i === trail.length - 1 ? undefined : () => setTrail((prev) => prev.slice(0, i + 1))}
              sx={{ fontSize: tokens.fontSize.md, maxWidth: "100%" }}
            />
          ))}
        </Box>
      )}

      <Box sx={{ p: view === "table" ? 0 : 1.5 }}>
        {view === "table" ? (
          <DataGrid
            rows={gridRows}
            columns={gridColumns}
            density="compact"
            showToolbar
            loading={busy}
            onRowClick={onRowClick}
            disableRowSelectionOnClick
            initialState={{ pagination: { paginationModel: { pageSize: 10 } } }}
            pageSizeOptions={[10, 25, 50, 100]}
            sx={{
              border: "none",
              fontSize: tokens.fontSize.md,
              "& .MuiDataGrid-row": { cursor: isRoster || level.drillDims.length ? "pointer" : "default" },
              "& .MuiDataGrid-columnHeaderTitle": { fontWeight: 700 },
            }}
          />
        ) : (
          <BlockChart rows={level.rows} columns={level.columns} mode={view} />
        )}
      </Box>

      {error && (
        <Typography sx={{ px: 1.5, pb: 1, color: "error.main", fontSize: tokens.fontSize.md }}>{error}</Typography>
      )}

      {(isRoster || level.drillDims.length > 0) && view === "table" && (
        <Typography sx={{ px: 1.5, pb: 1, color: "text.secondary", fontStyle: "italic", fontSize: tokens.fontSize.md }}>
          {isRoster ? "Click a row for that HCP's full 360 record." : "Click a row to break it down further."}
        </Typography>
      )}

      {detailNpi != null && (
        <Box sx={{ px: 1.5, pb: 1.5, pt: 1, borderTop: `1px solid ${tokens.color.outline}` }}>
          <HcpDetailPanel npi={detailNpi} />
        </Box>
      )}

      <Menu anchorEl={menu?.anchor} open={!!menu} onClose={() => setMenu(null)}>
        <MenuItem disabled sx={{ fontSize: tokens.fontSize.md, opacity: 1, fontWeight: 700 }}>
          Break down by…
        </MenuItem>
        {level.drillDims.map((dim) => (
          <MenuItem key={dim} sx={{ fontSize: tokens.fontSize.md }} onClick={() => menu && drillInto(menu.row, dim)}>
            {dimLabel(dim)}
          </MenuItem>
        ))}
      </Menu>
    </Box>
  );
}
