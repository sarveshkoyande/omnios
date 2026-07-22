import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Link from "@mui/material/Link";
import Typography from "@mui/material/Typography";
import { ConsolePanel } from "../components/ConsolePanel";
import { glass, indigoTint, tokens } from "../theme/tokens";
import type { ContentAsset, ContentModule } from "./types";

export function ModuleCard({ module: m }: { module: ContentModule }) {
  return (
    <ConsolePanel>
      <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 1, mb: 1 }}>
        <Chip size="small" variant="outlined" label={m.module_type.replace("_", " ")} />
        <Chip size="small" label={m.status.replace("_", " ")} />
        {m.material_number && (
          <Typography sx={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.02em", fontVariantNumeric: "tabular-nums", color: "text.secondary" }}>
            {m.material_number}
          </Typography>
        )}
      </Box>
      <Typography sx={{ fontWeight: 700, fontSize: 13 }}>{m.name}</Typography>
      {m.business_rules && (
        <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mt: 0.5 }}>{m.business_rules}</Typography>
      )}
      {m.claims.length > 0 && (
        <Box component="details" sx={{ mt: 1, fontSize: 11 }}>
          <Box component="summary" sx={{ cursor: "pointer", color: "primary.main", fontWeight: 700 }}>
            {m.claims.length} claim{m.claims.length === 1 ? "" : "s"}
          </Box>
          <Box component="ul" sx={{ m: "6px 0 0", pl: 2 }}>
            {m.claims.map((c, i) => <li key={i}>{c.text}</li>)}
          </Box>
        </Box>
      )}
    </ConsolePanel>
  );
}

export function AssetRow({ asset }: { asset: ContentAsset }) {
  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, background: glass.content, border: `1px solid ${indigoTint(0.12)}`, borderRadius: 2, p: 1.5 }}>
      <Chip size="small" label={asset.asset_format} sx={{ background: tokens.color.secondary, color: "#fff", fontWeight: 700 }} />
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography sx={{ fontWeight: 700, fontSize: 12 }}>{asset.title}</Typography>
        {asset.description && (
          <Typography variant="caption" sx={{ color: "text.secondary", display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {asset.description}
          </Typography>
        )}
      </Box>
      <Chip size="small" variant="outlined" label={asset.branded ? "Branded" : "Unbranded"} />
      {asset.id_code && (
        <Typography sx={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.02em", fontVariantNumeric: "tabular-nums", color: "text.secondary" }}>
          {asset.id_code}
        </Typography>
      )}
      {asset.blob_key && (
        <Link href={`/api/blob/${asset.blob_key}`} target="_blank" rel="noreferrer" sx={{ fontSize: 11, fontWeight: 700 }}>
          Open
        </Link>
      )}
    </Box>
  );
}
