import type { Page } from "../../schema/document";
import type { Direction } from "../../schema/document";
import type { WorkflowNode } from "../../schema/node";
import type { NodeType } from "../../schema/nodeTypes";
import { generateNodeId, generateEdgeId, generateGroupId } from "../../schema/ids";
import { defaultPortsFor, defaultDataFor } from "../../schema/nodeDefaults";
import { createEdge, createPage } from "../../schema/factories";
import { SHAPE_ALIAS_TO_TYPE, CLASSIC_BRACKET_PATTERNS } from "./shapeMap";

// Section 6 CONVERT (import direction) + Appendix A crib sheet. Line-oriented parser —
// not a full Mermaid grammar, but covers: direction header, subgraphs (-> lanes),
// classic bracket node shapes (inline in edge statements or standalone), the v11
// `@{ shape: x, label: y }` syntax, bare/labeled/dotted/thick/blocked/reads/association/
// invisible edges (including A --> B --> C chains), click links, and our own
// `%% metadata: id.key=value; ...` comments. Positions are always (0,0); callers should
// run auto-layout immediately after import since Mermaid text carries no coordinates.

const DIRECTION_ALIASES: Record<string, Direction> = { TD: "TB", TB: "TB", BT: "BT", LR: "LR", RL: "RL" };

const OP_REGEX = /(-->|<-->|-\.->|==>|--x|--o|---|-\.-|===|~~~)(\|[^|]*\|)?/g;

function unescapeLabel(s: string): string {
  return s.replace(/#quot;/g, '"').trim();
}

function edgeTypeFromOp(op: string): { type: string; animated?: never } {
  switch (op) {
    case "-.->": return { type: "dataflow" };
    case "-.-": return { type: "dataflow" };
    case "==>": return { type: "critical" };
    case "===": return { type: "critical" };
    case "--x": return { type: "blocked" };
    case "--o": return { type: "reads" };
    case "---": return { type: "association" };
    case "<-->": return { type: "bidirectional" };
    case "~~~": return { type: "invisible" };
    default: return { type: "sequence" };
  }
}

export function mermaidToPage(text: string, pageName = "Imported"): { page: Page; direction: Direction } {
  const page = createPage(pageName);
  const mermaidIdToNodeId = new Map<string, string>();
  const groupStack: string[] = [];
  let direction: Direction = "TB";
  let lastDeclaredMermaidId: string | null = null;

  const upsertNode = (mermaidId: string, type: NodeType | null, label: string | null): string => {
    let nodeId = mermaidIdToNodeId.get(mermaidId);
    if (!nodeId) {
      const resolvedType = type ?? "process";
      const node: WorkflowNode = {
        id: generateNodeId(label ?? mermaidId),
        type: resolvedType,
        label: label ?? mermaidId,
        position: { x: 0, y: 0 },
        size: { w: 160, h: 80, resizable: true },
        ports: defaultPortsFor(resolvedType),
        data: defaultDataFor(),
        layerIds: [],
        groupId: groupStack[groupStack.length - 1] ?? null,
      };
      page.nodes.push(node);
      nodeId = node.id;
      mermaidIdToNodeId.set(mermaidId, nodeId);
    } else if (type || label) {
      const idx = page.nodes.findIndex((n) => n.id === nodeId);
      page.nodes[idx] = {
        ...page.nodes[idx],
        type: type ?? page.nodes[idx].type,
        label: label ?? page.nodes[idx].label,
        ports: type ? defaultPortsFor(type) : page.nodes[idx].ports,
      };
    }
    return nodeId;
  };

  const resolveToken = (token: string): string | null => {
    const trimmed = token.trim();
    const m = /^([A-Za-z_][\w-]*)/.exec(trimmed);
    if (!m) return null;
    const mermaidId = m[1];
    const rest = trimmed.slice(mermaidId.length).trim();
    if (!rest) return upsertNode(mermaidId, null, null);
    for (const { regex, type } of CLASSIC_BRACKET_PATTERNS) {
      const bm = regex.exec(rest);
      if (bm) return upsertNode(mermaidId, type, unescapeLabel(bm[1]));
    }
    return upsertNode(mermaidId, null, null);
  };

  for (const raw of text.split("\n")) {
    const line = raw.trim();
    if (!line) continue;

    const dirMatch = /^(?:flowchart|graph)\s+(\w+)/i.exec(line);
    if (dirMatch) { direction = DIRECTION_ALIASES[dirMatch[1].toUpperCase()] ?? "TB"; continue; }

    if (/^%%\s*metadata:/i.test(line) && lastDeclaredMermaidId) {
      const nodeId = mermaidIdToNodeId.get(lastDeclaredMermaidId);
      const idx = page.nodes.findIndex((n) => n.id === nodeId);
      if (idx >= 0) {
        const body = line.replace(/^%%\s*metadata:\s*/i, "");
        for (const pair of body.split(";")) {
          const eq = pair.indexOf("=");
          if (eq < 0) continue;
          const key = pair.slice(0, eq).trim().split(".").pop()!;
          const value = pair.slice(eq + 1).trim();
          const existing = page.nodes[idx].data[key];
          if (existing) {
            if (existing.type === "number" || existing.type === "currency") {
              page.nodes[idx].data[key] = { ...existing, value: Number(value) };
            } else if (existing.type === "boolean") {
              page.nodes[idx].data[key] = { ...existing, value: value === "true" };
            } else {
              page.nodes[idx].data[key] = { ...existing, value };
            }
          }
        }
      }
      continue;
    }
    if (line.startsWith("%%")) continue; // ordinary comment
    if (/^click\s+(\S+)\s+"([^"]*)"(?:\s+"([^"]*)")?/.test(line)) {
      const m = /^click\s+(\S+)\s+"([^"]*)"(?:\s+"([^"]*)")?/.exec(line)!;
      const nodeId = mermaidIdToNodeId.get(m[1]);
      const idx = page.nodes.findIndex((n) => n.id === nodeId);
      if (idx >= 0) {
        page.nodes[idx] = {
          ...page.nodes[idx],
          links: [...(page.nodes[idx].links ?? []), { kind: "url", href: m[2], tooltip: m[3] }],
        };
      }
      continue;
    }
    if (/^(classDef|linkStyle|class\s)/.test(line)) continue; // styling — not roundtripped on import

    const subgraphMatch = /^subgraph\s+(\S+)(?:\s*\[(.*)\])?/.exec(line) ?? /^subgraph\s*\[(.*)\]/.exec(line);
    if (/^subgraph\b/.test(line)) {
      const idPart = /^subgraph\s+(\S+)/.exec(line)?.[1];
      const titlePart = /\[(.*)\]/.exec(line)?.[1];
      const groupId = generateGroupId(titlePart ?? idPart ?? "lane");
      page.groups.push({
        id: groupId,
        kind: "lane",
        label: unescapeLabel(titlePart ?? idPart ?? "Lane"),
        order: groupStack.length,
        collapsed: false,
        memberBehavior: { moveWith: true, deleteWith: "prompt", autoResize: true },
      });
      groupStack.push(groupId);
      void subgraphMatch;
      continue;
    }
    if (/^end$/i.test(line)) { groupStack.pop(); continue; }
    if (/^direction\s+/i.test(line)) continue;

    const shapeDeclMatch = /^(\S+)@\{\s*shape:\s*([\w-]+)\s*,\s*label:\s*"([^"]*)"\s*\}/.exec(line);
    if (shapeDeclMatch) {
      const [, mermaidId, shapeKey, label] = shapeDeclMatch;
      const type = SHAPE_ALIAS_TO_TYPE[shapeKey] ?? "process";
      upsertNode(mermaidId, type, unescapeLabel(label));
      lastDeclaredMermaidId = mermaidId;
      continue;
    }
    const edgeAnimMatch = /^(\S+)@\{\s*animate:\s*true\s*\}/.exec(line);
    if (edgeAnimMatch) continue; // animation flag on a named edge — best-effort skip on import

    // Edge statement (possibly chained: A --> B --> C), operators found via OP_REGEX.
    OP_REGEX.lastIndex = 0;
    const matches = [...line.matchAll(OP_REGEX)];
    if (matches.length > 0) {
      const segments: string[] = [];
      let cursor = 0;
      for (const m of matches) {
        segments.push(line.slice(cursor, m.index));
        cursor = m.index + m[0].length;
      }
      segments.push(line.slice(cursor));

      // Edge id prefix like "e1@A --> B" on the first segment — strip it before resolving.
      const edgeIdPrefixMatch = /^(\S+)@(.*)$/.exec(segments[0].trim());
      if (edgeIdPrefixMatch) segments[0] = edgeIdPrefixMatch[2];

      let leftId = resolveToken(segments[0]);
      for (let i = 0; i < matches.length; i++) {
        const rightId = resolveToken(segments[i + 1]);
        if (leftId && rightId) {
          const op = matches[i][1];
          const inlineLabel = matches[i][2]?.slice(1, -1);
          const { type } = edgeTypeFromOp(op);
          page.edges.push({
            ...createEdge(leftId, rightId, { type: type as WorkflowEdgeTypeLiteral, label: inlineLabel ? unescapeLabel(inlineLabel) : undefined }),
            id: generateEdgeId(),
          });
        }
        leftId = rightId;
      }
      continue;
    }
  }

  return { page, direction };
}

type WorkflowEdgeTypeLiteral =
  | "sequence" | "association" | "optional" | "dataflow" | "critical"
  | "message" | "bidirectional" | "blocked" | "reads" | "invisible";
