export function personaInitials(name: string): string {
  const parts = (name || "")
    .replace(/^(Dr\.|Prof\.|Mr\.|Ms\.|Mrs\.)\s*/, "")
    .trim()
    .split(/\s+/);
  return (((parts[0] || "")[0] || "") + ((parts[parts.length - 1] || "")[0] || "")).toUpperCase();
}

export const SENTIMENT_COLOR: Record<string, "success" | "secondary" | "warning" | "error"> = {
  enthusiastic: "success",
  interested: "secondary",
  skeptical: "warning",
  resistant: "error",
};
