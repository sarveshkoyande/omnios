import type { ReactNode } from "react";
import { SectionCard } from "../glass/primitives";

/**
 * ConsolePanel — retained name/API (many screens import it), now a thin adapter
 * over the glass SectionCard primitive so every section across the app renders
 * as a Tier-A milk-glass panel with a small-caps indigo label. Pass `icon`
 * (a material-symbol name) for the reference-style icon + label header.
 */
export function ConsolePanel({
  title,
  icon,
  action,
  children,
  ...rest
}: {
  title?: string;
  icon?: string;
  action?: ReactNode;
  children: ReactNode;
} & Omit<React.ComponentProps<typeof SectionCard>, "label" | "children" | "action">) {
  if (!title) {
    // Headerless panel: still a Tier-A glass surface.
    return (
      <SectionCard label="" {...rest}>
        {children}
      </SectionCard>
    );
  }
  return (
    <SectionCard label={title} icon={icon} action={action} {...rest}>
      {children}
    </SectionCard>
  );
}
