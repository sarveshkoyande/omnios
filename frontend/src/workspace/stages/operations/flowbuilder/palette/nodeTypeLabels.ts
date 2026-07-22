import type { NodeType } from "../schema/nodeTypes";

function titleCase(word: string): string {
  return word.charAt(0).toUpperCase() + word.slice(1);
}

export function humanizeNodeType(type: NodeType): string {
  if (type.includes(".")) {
    const [family, a, b] = type.split(".");
    if (family === "event") return `${titleCase(b)} (${titleCase(a)} Event)`;
    if (family === "task") return `${titleCase(a)} Task`;
    if (family === "gateway") return `${titleCase(a)} Gateway`;
  }
  return type
    .split("-")
    .map(titleCase)
    .join(" ");
}
