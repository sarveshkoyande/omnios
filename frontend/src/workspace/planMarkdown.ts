/**
 * Best-effort DOM -> the same GitHub-flavored markdown shape strategy/plan_export.py
 * parses (headings, paragraphs, '- ' bullets, '| a | b |' tables), so an inline edit
 * still exports cleanly to Word/the markdown-fallback PDF. Ported verbatim from the
 * legacy domToMarkdown/domInlineText — runs client-side, no server HTML parser needed.
 */
function domInlineText(el: Element): string {
  let out = "";
  el.childNodes.forEach((n) => {
    if (n.nodeType === 3) { out += n.textContent ?? ""; return; }
    if (n.nodeType !== 1) return;
    const child = n as Element;
    const tag = child.tagName;
    const inner = domInlineText(child);
    if (tag === "STRONG" || tag === "B") out += `**${inner}**`;
    else if (tag === "EM" || tag === "I") out += `*${inner}*`;
    else if (tag === "BR") out += " ";
    else out += inner; // spans/icons/links -- keep the text, drop the wrapper
  });
  return out.replace(/\s+/g, " ").trim();
}

export function domToMarkdown(root: Element): string {
  const lines: string[] = [];
  function walk(node: Element) {
    node.childNodes.forEach((child) => {
      if (child.nodeType !== 1) return;
      const el = child as Element;
      const tag = el.tagName;
      if (/^H[1-4]$/.test(tag)) {
        lines.push("#".repeat(Number(tag[1])) + " " + domInlineText(el), "");
      } else if (tag === "P") {
        const t = domInlineText(el);
        if (t) lines.push(t, "");
      } else if (tag === "UL" || tag === "OL") {
        el.querySelectorAll(":scope > li").forEach((li) => lines.push("- " + domInlineText(li)));
        lines.push("");
      } else if (tag === "TABLE") {
        const rows = [...el.querySelectorAll("tr")].map((tr) => [...tr.children].map((c) => domInlineText(c) || " "));
        if (rows.length) {
          lines.push("| " + rows[0].join(" | ") + " |", "|" + rows[0].map(() => "---").join("|") + "|");
          rows.slice(1).forEach((r) => lines.push("| " + r.join(" | ") + " |"));
          lines.push("");
        }
      } else if (tag === "HR") {
        lines.push("---", "");
      } else {
        walk(el); // divs/sections/details -- recurse to find nested text blocks
      }
    });
  }
  walk(root);
  return lines.join("\n").replace(/\n{3,}/g, "\n\n").trim();
}

/** Cells holding a widget (Gantt bar, budget bar, nested table/list) are skipped --
 * editing the text would risk mangling that markup. */
export function isRiskyCell(cell: Element): boolean {
  return [...cell.children].some((c) => ["DIV", "TABLE", "UL", "OL", "BUTTON", "SVG"].includes(c.tagName));
}
