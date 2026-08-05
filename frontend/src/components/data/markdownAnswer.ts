/**
 * Markdown-lite parser for agent chat answers.
 *
 * The chat pane used to render an answer with one regex pass for `**bold**`, `*italic*` and
 * `\n` -> `<br>`, which meant a GitHub-flavored pipe table arrived as a wall of literal `|`
 * characters. This splits an answer into the handful of block shapes the agents actually
 * emit — heading, bullet/numbered list, pipe table, paragraph — so a table can be handed to
 * the real table renderer instead of being printed as text.
 *
 * Deliberately not a full markdown implementation: no links, images, blockquotes or nested
 * lists. Those don't appear in these answers, and a real parser is a dependency (and an
 * XSS surface) this pane doesn't need.
 */
import type { DataBlock, DataBlockColumn } from "../../api";

export type AnswerNode =
  | { kind: "heading"; level: number; text: string }
  | { kind: "paragraph"; text: string }
  | { kind: "list"; ordered: boolean; items: string[] }
  | { kind: "table"; block: DataBlock };

const TABLE_ROW = /^\s*\|.*\|\s*$/;
/** `|---|:--:|` — the header/body divider, which carries no data. */
const TABLE_DIVIDER = /^\s*\|[\s:|-]+\|\s*$/;
const HEADING = /^(#{1,4})\s+(.*)$/;
const BULLET = /^\s*[-*•]\s+(.*)$/;
const ORDERED = /^\s*\d+[.)]\s+(.*)$/;

/** A trailing summary row must not become a chart category — it would dwarf every real one. */
const TOTAL_ROW = /^\s*(?:\*\*)?\s*(total|totals|grand total|all|sum)\b/i;

const splitCells = (line: string): string[] =>
  line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());

/** Strip the inline markers so a cell sorts and charts on its actual value, not on `**361**`. */
const plainCell = (text: string): string => text.replace(/\*\*|__|\*|`/g, "").trim();

/** Numbers in these answers arrive as `1,240`, `18%`, `$4.2` — all of which should sort and
 *  chart as numbers rather than as strings. Returns null when the cell isn't numeric. */
export function parseNumericCell(text: string): number | null {
  const cleaned = plainCell(text).replace(/[,\s$£€]/g, "").replace(/%$/, "");
  if (!cleaned || !/^-?\d*\.?\d+$/.test(cleaned)) return null;
  const value = Number(cleaned);
  return Number.isFinite(value) ? value : null;
}

function tableToBlock(lines: string[], id: string): DataBlock | null {
  const grid = lines.filter((l) => !TABLE_DIVIDER.test(l)).map(splitCells);
  if (grid.length < 2) return null;
  const header = grid[0].map(plainCell);
  const body = grid.slice(1).filter((cells) => cells.some((c) => plainCell(c) !== ""));
  if (!header.length || !body.length) return null;

  const dataRows = body.filter((cells) => !TOTAL_ROW.test(cells[0] ?? ""));
  const totalRow = body.find((cells) => TOTAL_ROW.test(cells[0] ?? ""));

  const columns: DataBlockColumn[] = header.map((label, i) => {
    const values = dataRows.map((cells) => cells[i] ?? "").filter((c) => plainCell(c) !== "");
    const numeric = values.length > 0 && values.every((c) => parseNumericCell(c) !== null);
    return { key: `c${i}`, label: label || `Column ${i + 1}`, type: numeric ? "number" : "text" };
  });

  const rows = (dataRows.length ? dataRows : body).map((cells) =>
    Object.fromEntries(
      columns.map((col, i) => {
        const raw = cells[i] ?? "";
        return [col.key, col.type === "number" ? parseNumericCell(raw) : plainCell(raw)];
      }),
    ),
  );

  // A markdown table carries no query behind it, so it gets no drill-down — just a real
  // sortable grid and a chart. Tables the agent pulled from the panel arrive as structured
  // data_blocks instead, and those do drill.
  const totalCell = totalRow && columns.find((c) => c.type === "number");
  return {
    id,
    kind: "breakdown",
    title: header.filter(Boolean).join(" · ") || "Table",
    columns,
    rows,
    drill_dims: [],
    total: totalCell ? parseNumericCell(totalRow[columns.indexOf(totalCell)] ?? "") ?? 0 : 0,
  };
}

export function parseAnswer(text: string): AnswerNode[] {
  const lines = (text ?? "").split("\n");
  const nodes: AnswerNode[] = [];
  let paragraph: string[] = [];
  let tableId = 0;

  const flushParagraph = () => {
    const joined = paragraph.join(" ").trim();
    if (joined) nodes.push({ kind: "paragraph", text: joined });
    paragraph = [];
  };

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];

    if (!line.trim()) { flushParagraph(); continue; }

    if (TABLE_ROW.test(line)) {
      const start = i;
      while (i + 1 < lines.length && TABLE_ROW.test(lines[i + 1])) i += 1;
      const block = tableToBlock(lines.slice(start, i + 1), `md${(tableId += 1)}`);
      flushParagraph();
      if (block) nodes.push({ kind: "table", block });
      else nodes.push({ kind: "paragraph", text: lines.slice(start, i + 1).join(" ") });
      continue;
    }

    const heading = HEADING.exec(line);
    if (heading) {
      flushParagraph();
      nodes.push({ kind: "heading", level: heading[1].length, text: heading[2] });
      continue;
    }

    const isBullet = BULLET.test(line);
    const isOrdered = !isBullet && ORDERED.test(line);
    if (isBullet || isOrdered) {
      const pattern = isBullet ? BULLET : ORDERED;
      const items: string[] = [];
      while (i < lines.length && pattern.test(lines[i])) {
        items.push(pattern.exec(lines[i])![1]);
        i += 1;
      }
      i -= 1;
      flushParagraph();
      nodes.push({ kind: "list", ordered: isOrdered, items });
      continue;
    }

    paragraph.push(line);
  }
  flushParagraph();
  return nodes;
}

/** Inline markup only — the caller has already split blocks out, so this never sees a table. */
export function renderInline(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>");
}
