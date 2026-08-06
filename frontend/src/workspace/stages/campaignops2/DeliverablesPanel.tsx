import { useMemo, useState } from "react";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Collapse from "@mui/material/Collapse";
import Typography from "@mui/material/Typography";
import Tooltip from "@mui/material/Tooltip";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import { styled } from "@mui/material/styles";
import { ConsolePanel } from "../../../components/ConsolePanel";
import { glass, indigoTint, shade, tokens } from "../../../theme/tokens";
import { CATEGORIES, COVERAGE_STYLE } from "./derive";
import type { CategoryId, Coverage, Deliverable } from "./types";

const REVIEW_LABEL: Record<Deliverable["review"], string> = {
  none: "", abbreviated: "Abbreviated review", full: "Full review",
};

const Row = styled(Box)({
  display: "flex",
  alignItems: "flex-start",
  gap: 12,
  padding: "10px 12px",
  borderBottom: `1px dashed ${shade(0.08)}`,
  "&:last-of-type": { borderBottom: "none" },
  "&:hover": { background: indigoTint(0.04) },
});

const CatHeader = styled(Box)<{ open?: boolean }>(({ open }) => ({
  display: "flex",
  alignItems: "center",
  gap: 12,
  padding: "11px 14px",
  cursor: "pointer",
  background: open ? indigoTint(0.07) : glass.content,
  borderRadius: open ? `${tokens.radius.sm} ${tokens.radius.sm} 0 0` : tokens.radius.sm,
  border: `1px solid ${indigoTint(0.12)}`,
  "&:hover": { borderColor: indigoTint(0.3) },
}));

/** Small four-segment bar showing a category's coverage mix at a glance. */
function MixBar({ items }: { items: Deliverable[] }) {
  const order: Coverage[] = ["reuse", "adapt", "build", "blocked"];
  return (
    <Box sx={{ display: "flex", width: 84, height: 7, borderRadius: 4, overflow: "hidden", flex: "0 0 auto" }}>
      {order.map((c) => {
        const n = items.filter((i) => i.coverage === c).length;
        return n ? <Box key={c} sx={{ flex: n, background: COVERAGE_STYLE[c].color }} /> : null;
      })}
    </Box>
  );
}

/**
 * The deliverables list — requirement and coverage in one place rather than two.
 *
 * "What is built" and "what is remaining" are two states of the same item, so they live in
 * one list with coverage as a facet. Splitting them into separate sections would mean moving
 * rows between panels as they resolve, and losing the single view of a category's real state.
 */
export function DeliverablesPanel({ items }: { items: Deliverable[] }) {
  const [filter, setFilter] = useState<Coverage | "all">("all");
  const [open, setOpen] = useState<Record<string, boolean>>({ creative: true });

  const shown = useMemo(
    () => (filter === "all" ? items : items.filter((i) => i.coverage === filter)),
    [items, filter],
  );

  const byCategory = useMemo(() => {
    const map = new Map<CategoryId, Deliverable[]>();
    for (const it of shown) {
      const arr = map.get(it.category) ?? [];
      arr.push(it);
      map.set(it.category, arr);
    }
    return map;
  }, [shown]);

  return (
    <ConsolePanel
      id="ops2-deliverables"
      title="Deliverables & coverage"
      icon="inventory_2"
      sx={{ mb: 3 }}
      action={
        <ToggleButtonGroup
          size="small"
          exclusive
          value={filter}
          onChange={(_e, v) => v && setFilter(v)}
          sx={{ "& .MuiToggleButton-root": { textTransform: "none", fontSize: 13, py: 0.3, px: 1.1 } }}
        >
          <ToggleButton value="all">All {items.length}</ToggleButton>
          {(["reuse", "adapt", "build", "blocked"] as Coverage[]).map((c) => (
            <ToggleButton key={c} value={c} sx={{ color: COVERAGE_STYLE[c].color }}>
              {COVERAGE_STYLE[c].label} {items.filter((i) => i.coverage === c).length}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
      }
    >
      <Typography variant="body2" sx={{ color: "text.secondary", mb: 2 }}>
        Every deliverable the journey implies, each checked against what already exists before
        it is called work. <b>Adapt</b> is the tier the current build has no concept of — the claim is
        approved and the asset exists, but this campaign needs a new rendition of it.
      </Typography>

      {CATEGORIES.map((cat) => {
        const catItems = byCategory.get(cat.id) ?? [];
        if (!catItems.length) return null;
        const isOpen = !!open[cat.id];
        const days = catItems.filter((i) => i.coverage !== "reuse").reduce((s, i) => s + i.effortDays, 0);
        return (
          <Box key={cat.id} sx={{ mb: 1.25 }}>
            <CatHeader open={isOpen} onClick={() => setOpen((o) => ({ ...o, [cat.id]: !o[cat.id] }))}>
              <span className="material-symbols-outlined" style={{ fontSize: 20, color: tokens.color.primary }}>
                {cat.icon}
              </span>
              <Typography sx={{ fontWeight: 700, fontSize: 15, flex: 1, minWidth: 0 }}>{cat.name}</Typography>
              <MixBar items={catItems} />
              <Typography variant="caption" sx={{ color: "text.secondary", flex: "0 0 auto", width: 92, textAlign: "right" }}>
                {catItems.length} item{catItems.length === 1 ? "" : "s"} · {days}d
              </Typography>
              <span className="material-symbols-outlined" style={{ fontSize: 20, color: tokens.color.inkSoft }}>
                {isOpen ? "expand_less" : "expand_more"}
              </span>
            </CatHeader>
            <Collapse in={isOpen} unmountOnExit>
              <Box sx={{ border: `1px solid ${indigoTint(0.12)}`, borderTop: "none", borderRadius: `0 0 ${tokens.radius.sm} ${tokens.radius.sm}` }}>
                {catItems.map((it) => {
                  const cs = COVERAGE_STYLE[it.coverage];
                  return (
                    <Row key={it.id}>
                      <Chip
                        size="small"
                        label={cs.label}
                        sx={{ flex: "0 0 auto", height: 22, fontWeight: 700, fontSize: 13, color: cs.color, background: cs.bg }}
                      />
                      <Box sx={{ flex: 1, minWidth: 0 }}>
                        <Typography variant="body2" sx={{ fontWeight: 600 }}>{it.title}</Typography>
                        <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mt: 0.15 }}>
                          {it.coverageReason}
                        </Typography>
                        <Box sx={{ display: "flex", gap: 0.75, mt: 0.5, flexWrap: "wrap", alignItems: "center" }}>
                          <Chip size="small" variant="outlined" label={it.source} sx={{ height: 20, fontSize: 12 }} />
                          {it.review !== "none" && (
                            <Tooltip title="Review is a queue with round-trips — plan two to three rounds, not one pass.">
                              <Chip size="small" color="warning" variant="outlined" label={REVIEW_LABEL[it.review]} sx={{ height: 20, fontSize: 12 }} />
                            </Tooltip>
                          )}
                        </Box>
                      </Box>
                      <Box sx={{ flex: "0 0 150px", textAlign: "right" }}>
                        <Typography variant="caption" sx={{ display: "block", fontWeight: 700 }}>
                          {it.effortDays}d
                        </Typography>
                        <Typography variant="caption" sx={{ display: "block", color: "text.secondary", lineHeight: 1.25 }}>
                          {it.owner}
                        </Typography>
                      </Box>
                    </Row>
                  );
                })}
              </Box>
            </Collapse>
          </Box>
        );
      })}
    </ConsolePanel>
  );
}
