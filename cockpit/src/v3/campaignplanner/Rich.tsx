import type { ReactNode } from "react";

/** Light formatting for agent text (Camille's FormattedText): paragraphs, "- " / "* " bullets,
 *  "1. " numbered lists, **bold** and `code`. Built as React nodes, never HTML, so model output
 *  can't inject markup. A `---JSON_START---` block (the agents' structured output) is shown
 *  as preformatted data. */
function inline(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /\*\*(.+?)\*\*|`([^`]+)`/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let k = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index));
    out.push(m[1] !== undefined ? <strong key={k++}>{m[1]}</strong> : <code key={k++}>{m[2]}</code>);
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

function blocks(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  let list: string[] = [];
  let ordered = false;
  let k = 0;
  const flush = () => {
    if (!list.length) return;
    const items = list.map((t, i) => <li key={i}>{inline(t)}</li>);
    out.push(ordered ? <ol key={k++}>{items}</ol> : <ul key={k++}>{items}</ul>);
    list = [];
  };
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    if (!line) { flush(); continue; }
    const num = /^\d+[.)]\s+(.+)$/.exec(line);
    const bullet = /^[-*•]\s+(.+)$/.exec(line);
    if (num || bullet) {
      const isNum = Boolean(num);
      if (list.length && isNum !== ordered) flush();
      ordered = isNum;
      list.push((num ?? bullet)![1]);
      continue;
    }
    flush();
    out.push(<p key={k++}>{inline(line)}</p>);
  }
  flush();
  return out;
}

export function Rich({ text, className }: { text: string; className?: string }) {
  const split = text.split(/-{2,}\s*JSON_START\s*-{2,}/);
  return (
    <div className={`v3-cc-rich ${className ?? ""}`}>
      {blocks(split[0])}
      {split.length > 1 && split[1].trim() && (
        <div className="v3-cc-rich-json">
          <span>Structured output</span>
          <pre>{split[1].trim()}</pre>
        </div>
      )}
    </div>
  );
}
