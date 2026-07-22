import type { WorkflowNode } from "../schema/node";
import type { DataField } from "../schema/dataField";

// Section 3.2 node.dataGraphics — "conditional formatting for diagrams" (Visio's Data
// Graphics: text callouts, data bars, icon sets, color-by-value). Rules are small boolean
// expressions like "data.sla > PT8H" or "data.status == 'Deprecated'" evaluated against
// node.data; matching rules apply their `apply` patch (fill/stroke/opacity/badgeIcon),
// later rules winning on conflicting keys. No eval()/new Function — hand-rolled
// tokenizer + recursive-descent parser over a tiny, closed grammar.

export interface DataGraphicsResult {
  fill?: string;
  stroke?: string;
  opacity?: number;
  badgeIcon?: string;
}

// ISO 8601 duration (subset: P?Y?M?W?D?T?H?M?S?) -> minutes, for numeric comparison.
export function durationToMinutes(iso: string): number {
  const match = /^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$/.exec(iso.trim());
  if (!match) return NaN;
  const [, days, hours, minutes, seconds] = match;
  return (
    (Number(days) || 0) * 1440 +
    (Number(hours) || 0) * 60 +
    (Number(minutes) || 0) +
    (Number(seconds) || 0) / 60
  );
}

type Token =
  | { kind: "ident"; value: string }
  | { kind: "number"; value: number }
  | { kind: "string"; value: string }
  | { kind: "duration"; value: number }
  | { kind: "op"; value: string }
  | { kind: "lparen" }
  | { kind: "rparen" };

function tokenize(expr: string): Token[] {
  const tokens: Token[] = [];
  let i = 0;
  while (i < expr.length) {
    const c = expr[i];
    if (/\s/.test(c)) { i++; continue; }
    if (c === "(") { tokens.push({ kind: "lparen" }); i++; continue; }
    if (c === ")") { tokens.push({ kind: "rparen" }); i++; continue; }
    if (c === "'" || c === '"') {
      const quote = c;
      let j = i + 1;
      let value = "";
      while (j < expr.length && expr[j] !== quote) { value += expr[j]; j++; }
      tokens.push({ kind: "string", value });
      i = j + 1;
      continue;
    }
    const twoChar = expr.slice(i, i + 2);
    if (["==", "!=", ">=", "<=", "&&", "||"].includes(twoChar)) {
      tokens.push({ kind: "op", value: twoChar });
      i += 2;
      continue;
    }
    if ("><!".includes(c)) { tokens.push({ kind: "op", value: c }); i++; continue; }
    const durMatch = /^P(?:\d+D)?(?:T(?:\d+H)?(?:\d+M)?(?:\d+S)?)?/.exec(expr.slice(i));
    if (durMatch && durMatch[0].length > 1) {
      tokens.push({ kind: "duration", value: durationToMinutes(durMatch[0]) });
      i += durMatch[0].length;
      continue;
    }
    const numMatch = /^-?\d+(\.\d+)?/.exec(expr.slice(i));
    if (numMatch) { tokens.push({ kind: "number", value: Number(numMatch[0]) }); i += numMatch[0].length; continue; }
    const identMatch = /^[A-Za-z_][A-Za-z0-9_.]*/.exec(expr.slice(i));
    if (identMatch) { tokens.push({ kind: "ident", value: identMatch[0] }); i += identMatch[0].length; continue; }
    i++; // skip unrecognized char rather than throwing on a malformed rule
  }
  return tokens;
}

type Ctx = Record<string, unknown>;

function resolveIdent(path: string, ctx: Ctx): unknown {
  if (path === "true") return true;
  if (path === "false") return false;
  if (path === "null") return null;
  const parts = path.split(".");
  let cur: unknown = ctx;
  for (const part of parts) {
    if (cur == null || typeof cur !== "object") return undefined;
    cur = (cur as Record<string, unknown>)[part];
  }
  return cur;
}

// Recursive-descent: expr := and ( '||' and )* ; and := cmp ( '&&' cmp )* ;
// cmp := atom ( ('=='|'!='|'>'|'<'|'>='|'<=') atom )? ; atom := literal | ident | '(' expr ')'
function parseAndEval(tokens: Token[], ctx: Ctx): boolean {
  let pos = 0;
  const peek = () => tokens[pos];
  const next = () => tokens[pos++];

  function parseAtom(): unknown {
    const t = next();
    if (!t) return undefined;
    if (t.kind === "lparen") {
      const v = parseExpr();
      if (peek()?.kind === "rparen") next();
      return v;
    }
    if (t.kind === "number" || t.kind === "string" || t.kind === "duration") return t.value;
    if (t.kind === "ident") return resolveIdent(t.value, ctx);
    return undefined;
  }

  function parseCmp(): unknown {
    const left = parseAtom();
    const t = peek();
    if (t?.kind === "op" && ["==", "!=", ">", "<", ">=", "<="].includes(t.value)) {
      next();
      const right = parseAtom();
      switch (t.value) {
        case "==": return left === right;
        case "!=": return left !== right;
        case ">": return Number(left) > Number(right);
        case "<": return Number(left) < Number(right);
        case ">=": return Number(left) >= Number(right);
        case "<=": return Number(left) <= Number(right);
      }
    }
    return left;
  }

  function parseAnd(): unknown {
    let left = parseCmp();
    for (let t = peek(); t?.kind === "op" && t.value === "&&"; t = peek()) {
      next();
      const right = parseCmp();
      left = Boolean(left) && Boolean(right);
    }
    return left;
  }

  function parseExpr(): unknown {
    let left = parseAnd();
    for (let t = peek(); t?.kind === "op" && t.value === "||"; t = peek()) {
      next();
      const right = parseAnd();
      left = Boolean(left) || Boolean(right);
    }
    return left;
  }

  return Boolean(parseExpr());
}

function fieldToPlainValue(field: DataField): unknown {
  if (field.type === "duration" && typeof field.value === "string") return durationToMinutes(field.value);
  return field.value;
}

export function evaluateRule(rule: string, node: WorkflowNode): boolean {
  const data: Record<string, unknown> = {};
  for (const [key, field] of Object.entries(node.data)) data[key] = fieldToPlainValue(field);
  try {
    return parseAndEval(tokenize(rule), { data });
  } catch {
    return false;
  }
}

export function evaluateDataGraphics(node: WorkflowNode): DataGraphicsResult {
  if (!node.dataGraphics || node.dataGraphics.length === 0) return {};
  let result: DataGraphicsResult = {};
  for (const rule of node.dataGraphics) {
    if (evaluateRule(rule.rule, node)) {
      result = { ...result, ...(rule.apply as DataGraphicsResult) };
    }
  }
  return result;
}
