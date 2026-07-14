import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Link from "@mui/material/Link";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import { CLAIM_SRC_LABEL, CLAIM_TYPE_LABEL } from "./types";
import type { Claim } from "./types";
import { glass, indigoTint, shade, tokens } from "../theme/tokens";

const STATUS_COLOR: Record<string, string> = {
  approved: tokens.color.success,
  in_review: tokens.color.warning,
  draft: shade(0.35),
};

const Card = styled("article")<{ status: string }>(({ theme, status }) => ({
  background: glass.content,
  border: `1px solid ${indigoTint(0.12)}`,
  borderLeft: `3px solid ${STATUS_COLOR[status] ?? shade(0.3)}`,
  borderRadius: tokens.radius.md,
  padding: theme.spacing(3),
  marginBottom: theme.spacing(2),
  boxShadow: glass.shadow,
}));

export function ClaimCard({ claim }: { claim: Claim }) {
  return (
    <Card status={claim.status}>
      <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 1, mb: 1 }}>
        <Chip size="small" label={CLAIM_TYPE_LABEL[claim.claim_type] ?? claim.claim_type} />
        <Chip
          size="small"
          label={claim.status.replace("_", " ")}
          sx={{ background: STATUS_COLOR[claim.status], color: claim.status === "draft" ? "#fff" : tokens.color.text }}
        />
        {claim.material_number && (
          <Typography sx={{ fontFamily: tokens.font.mono, fontSize: 10, color: "text.secondary", background: shade(0.05), px: 1, borderRadius: 1 }}>
            {claim.material_number}
          </Typography>
        )}
        {claim.indication && <Chip size="small" variant="outlined" label={claim.indication} />}
      </Box>

      <Typography sx={{ fontSize: 13, lineHeight: 1.5, mb: 1.5 }}>{claim.text}</Typography>

      <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
        {claim.references.length ? (
          claim.references.map((r, i) => {
            const label = CLAIM_SRC_LABEL[r.source_type] ?? r.source_type;
            const text = `${label}${r.external_id ? ` ${r.external_id}` : ""}`;
            return r.url ? (
              <Link key={i} href={r.url} target="_blank" rel="noreferrer" title={r.citation} sx={{ fontSize: 10.5, fontWeight: 600 }}>
                {text}
              </Link>
            ) : (
              <Typography key={i} sx={{ fontSize: 10.5, color: "text.secondary" }}>{text}</Typography>
            );
          })
        ) : (
          <Chip size="small" color="error" label="No reference — MLR risk" />
        )}
      </Box>

      {claim.expires_at && (
        <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mt: 1 }}>
          Re-substantiate by {claim.expires_at.slice(0, 10)}
        </Typography>
      )}
    </Card>
  );
}
