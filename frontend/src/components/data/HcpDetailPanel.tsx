import { useEffect, useState } from "react";
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import Typography from "@mui/material/Typography";
import { fetchHcpDetail } from "../../api";
import { accent } from "../../theme/stageTheme";
import { tokens } from "../../theme/tokens";

/** `primary_specialty_description__c` -> `Primary specialty description`. The panel's columns
 *  are Salesforce-style API names; nothing else in the app has to know that, so the humanising
 *  happens here rather than in a hand-maintained label map that would drift from the schema. */
function humanise(key: string): string {
  const words = key.replace(/__c$/, "").replace(/_+/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

const isScalar = (value: unknown): value is string | number =>
  (typeof value === "string" && value !== "") || typeof value === "number";

function KeyValues({ record }: { record: Record<string, unknown> }) {
  const entries = Object.entries(record).filter(([, v]) => isScalar(v));
  if (!entries.length) return null;
  return (
    <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: 1 }}>
      {entries.map(([key, value]) => (
        <Box key={key} sx={{ minWidth: 0 }}>
          <Typography sx={{ fontSize: tokens.fontSize.md, color: "text.secondary" }}>{humanise(key)}</Typography>
          <Typography sx={{ fontSize: tokens.fontSize.md, fontWeight: 700, overflowWrap: "anywhere" }}>
            {String(value)}
          </Typography>
        </Box>
      ))}
    </Box>
  );
}

function Group({ title, record }: { title: string; record: Record<string, unknown> }) {
  return (
    <Box sx={{ mt: 2 }}>
      <Typography sx={{ fontSize: tokens.fontSize.md, fontWeight: 700, color: accent.primary, mb: 0.75 }}>
        {title}
      </Typography>
      <KeyValues record={record} />
    </Box>
  );
}

/** The roster block's per-row drill-down: one HCP's full 360 record, fetched on demand. */
export function HcpDetailPanel({ npi }: { npi: number }) {
  const [record, setRecord] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setRecord(null);
    setError(null);
    fetchHcpDetail(npi)
      .then((data) => { if (!cancelled) setRecord(data); })
      .catch(() => { if (!cancelled) setError("Couldn't load this HCP's 360 record."); });
    return () => { cancelled = true; };
  }, [npi]);

  if (error) return <Typography sx={{ color: "error.main", fontSize: tokens.fontSize.md }}>{error}</Typography>;
  if (!record) return <Box sx={{ display: "flex", justifyContent: "center", py: 3 }}><CircularProgress size={22} /></Box>;

  const nested = Object.entries(record).filter(
    ([, value]) => value && typeof value === "object" && !Array.isArray(value),
  ) as [string, Record<string, unknown>][];
  const trx = Array.isArray(record.trx) ? (record.trx as Record<string, unknown>[]) : [];

  return (
    <Box>
      <KeyValues record={record} />
      {nested.map(([key, value]) => <Group key={key} title={humanise(key)} record={value} />)}
      {trx.length > 0 && (
        <Box sx={{ mt: 2 }}>
          <Typography sx={{ fontSize: tokens.fontSize.md, fontWeight: 700, color: accent.primary, mb: 0.75 }}>
            TRx
          </Typography>
          {trx.map((row, i) => (
            <Box key={i} sx={{ py: 0.5, borderTop: i ? `1px solid ${tokens.color.outline}` : "none" }}>
              <KeyValues record={row} />
            </Box>
          ))}
        </Box>
      )}
    </Box>
  );
}
