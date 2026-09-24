import type { ReactNode } from "react";

/** The agents write light markdown: **bold** and line breaks. Rendered as React nodes (never
 *  as HTML) so agent text can't inject markup. */
export function Md({ text }: { text: string }): ReactNode {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") && part.length > 4
      ? <strong key={i}>{part.slice(2, -2)}</strong>
      : <span key={i}>{part}</span>);
}
