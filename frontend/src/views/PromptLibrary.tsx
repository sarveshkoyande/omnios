import { useEffect, useMemo, useState } from "react";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Typography from "@mui/material/Typography";
import { fetchPromptLibrary, type PromptLibraryEntry } from "../api";
import { ConsolePanel } from "../components/ConsolePanel";
import { tokens, indigoTint, light } from "../theme/tokens";

/** Temporary tab: browse every LLM system prompt / agent "skill" this app actually sends
 * to a model, read live from the running code (see strategy/prompt_library.py) rather than
 * a hand-copied snapshot -- so it's always exactly what's really there. */
export function PromptLibrary() {
  const [entries, setEntries] = useState<PromptLibraryEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeStage, setActiveStage] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);

  useEffect(() => {
    fetchPromptLibrary()
      .then(setEntries)
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load the prompt library."));
  }, []);

  const stages = useMemo(() => {
    if (!entries) return [];
    const seen = new Set<string>();
    const order: string[] = [];
    for (const e of entries) {
      if (!seen.has(e.stage)) { seen.add(e.stage); order.push(e.stage); }
    }
    return order;
  }, [entries]);

  const visible = useMemo(() => {
    if (!entries) return [];
    return activeStage ? entries.filter((e) => e.stage === activeStage) : entries;
  }, [entries, activeStage]);

  return (
    <Box
      sx={{
        maxWidth: 1100,
        mx: "auto",
        px: { xs: 3, md: 6 },
        py: 5,
      }}
    >
      <Typography sx={{ fontSize: tokens.fontSize.xxl, fontWeight: 700, color: "text.primary", mb: 0.5 }}>
        Prompt Library
      </Typography>
      <Typography variant="body2" sx={{ color: "text.secondary", mb: 4, maxWidth: 720 }}>
        Every LLM system prompt / agent "skill" wired into Omni OS, read live from the running
        code — not a hand-copied snapshot, so it's always exactly what the app really sends the
        model right now.
      </Typography>

      {error && (
        <Typography variant="body2" sx={{ color: "error.main", mb: 3 }}>
          {error}
        </Typography>
      )}

      {!entries && !error && (
        <Box sx={{ display: "flex", justifyContent: "center", py: 8 }}>
          <CircularProgress size={26} />
        </Box>
      )}

      {entries && (
        <>
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, mb: 3 }}>
            <Chip
              size="small"
              label={`All (${entries.length})`}
              onClick={() => setActiveStage(null)}
              sx={{
                fontWeight: 700,
                color: activeStage === null ? "#fff" : tokens.color.primary,
                background: activeStage === null ? tokens.color.primary : tokens.color.primaryContainer,
              }}
            />
            {stages.map((s) => (
              <Chip
                key={s}
                size="small"
                label={s}
                onClick={() => setActiveStage(s)}
                sx={{
                  fontWeight: 700,
                  color: activeStage === s ? "#fff" : tokens.color.primary,
                  background: activeStage === s ? tokens.color.primary : tokens.color.primaryContainer,
                }}
              />
            ))}
          </Box>

          <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
            {visible.map((entry) => {
              const open = openId === entry.id;
              return (
                <ConsolePanel key={entry.id} sx={{ p: 0, overflow: "hidden" }}>
                  <Box
                    onClick={() => setOpenId(open ? null : entry.id)}
                    sx={{
                      display: "flex",
                      alignItems: "flex-start",
                      justifyContent: "space-between",
                      gap: 2,
                      p: 2.5,
                      cursor: "pointer",
                      "&:hover": { background: indigoTint(0.05) },
                    }}
                  >
                    <Box sx={{ minWidth: 0 }}>
                      <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.5, flexWrap: "wrap" }}>
                        <Typography sx={{ fontWeight: 700, fontSize: tokens.fontSize.md }}>{entry.name}</Typography>
                        <Chip size="small" label={entry.stage} sx={{ height: 20, fontSize: 11, background: tokens.color.canvas }} />
                        <Chip
                          size="small"
                          label={entry.kind === "prompt" ? "system prompt" : "function source"}
                          sx={{ height: 20, fontSize: 11, color: tokens.color.inkSoft, background: "transparent", border: `1px solid ${indigoTint(0.2)}` }}
                        />
                      </Box>
                      <Typography variant="body2" sx={{ color: "text.secondary", mb: 0.5 }}>{entry.blurb}</Typography>
                      <Typography variant="caption" sx={{ color: tokens.color.inkSoft, fontFamily: "monospace" }}>{entry.file}</Typography>
                    </Box>
                    <span className="material-symbols-outlined" style={{ color: tokens.color.inkSoft, flexShrink: 0 }}>
                      {open ? "expand_less" : "expand_more"}
                    </span>
                  </Box>
                  {open && (
                    <Box
                      component="pre"
                      sx={{
                        m: 0,
                        p: 2.5,
                        borderTop: `1px solid ${indigoTint(0.12)}`,
                        background: light(0.5),
                        fontFamily: "'JetBrains Mono', ui-monospace, monospace",
                        fontSize: 12.5,
                        lineHeight: 1.6,
                        whiteSpace: "pre-wrap",
                        wordBreak: "break-word",
                        maxHeight: 480,
                        overflowY: "auto",
                        color: tokens.color.text,
                      }}
                    >
                      {entry.text}
                    </Box>
                  )}
                </ConsolePanel>
              );
            })}
          </Box>
        </>
      )}
    </Box>
  );
}
