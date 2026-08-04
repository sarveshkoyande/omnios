import { useMemo, useState } from "react";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import { ClaimCard } from "./ClaimCard";
import type { LightboxImage } from "./Lightbox";
import { ModuleCard, AssetRow } from "./ModuleAndAssetCards";
import { CLAIM_TYPE_LABEL } from "./types";
import type { LibraryDetail } from "./types";
import { glass, glassFallback, indigoTint, tokens } from "../theme/tokens";

const Section = styled("section")(({ theme }) => ({ marginBottom: theme.spacing(8) }));
const SectionHead = styled(Typography)(({ theme }) => ({
  display: "flex",
  alignItems: "center",
  gap: theme.spacing(1.5),
  fontSize: tokens.fontSize.lg,
  marginBottom: theme.spacing(1),
}));
const CountChip = styled(Chip)({ marginLeft: 8 });

const GalleryTile = styled("figure")(({ theme }) => ({
  margin: 0,
  background: glassFallback,
  border: `1px solid ${indigoTint(0.14)}`,
  borderRadius: tokens.radius.md,
  overflow: "hidden",
  cursor: "zoom-in",
  boxShadow: glass.shadow,
  transition: "transform 160ms ease, box-shadow 160ms ease",
  "&:hover": { transform: "translateY(-2px)", boxShadow: glass.shadowElevated },
  "& img": { display: "block", width: "100%", height: 120, objectFit: "contain", background: "#fff", padding: theme.spacing(1.5) },
  "& figcaption": {
    fontSize: 15,
    color: tokens.color.inkSoft,
    padding: theme.spacing(1, 1.5),
    borderTop: `1px solid ${indigoTint(0.1)}`,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
}));

const FilterChip = styled(Chip)<{ on: boolean }>(({ on }) => ({
  cursor: "pointer",
  ...(on && { background: tokens.color.primary, color: "#fff", borderColor: "transparent" }),
}));

export function LibraryDetailView({
  detail,
  onBack,
  onOpenImage,
}: {
  detail: LibraryDetail;
  onBack: () => void;
  onOpenImage: (img: LightboxImage) => void;
}) {
  const [status, setStatus] = useState("all");
  const [type, setType] = useState("all");
  const c = detail.counts;

  const statusOptions = ["all", "approved", "in_review", "draft"].filter((s) => s === "all" || c.by_status[s]);
  const typeOptions = ["all", ...Object.keys(c.by_type)];

  const filteredClaims = useMemo(
    () => detail.claims.filter((cl) => (status === "all" || cl.status === status) && (type === "all" || cl.claim_type === type)),
    [detail.claims, status, type],
  );

  return (
    <Box>
      <Box sx={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 2, mb: 4 }}>
        <Button variant="outlined" onClick={onBack}>← All brands</Button>
        <Box sx={{ flex: 1, minWidth: 220 }}>
          <Typography variant="h1" sx={{ fontSize: 24 }}>
            {detail.brand} <Typography component="span" sx={{ fontSize: 15, color: "text.secondary", fontWeight: 400 }}>{detail.generic}</Typography>
          </Typography>
          <Typography variant="body2" sx={{ color: "text.secondary" }}>
            {detail.client} · {detail.therapy_area} · {detail.indications.length} indication{detail.indications.length === 1 ? "" : "s"}
          </Typography>
        </Box>
        <Box sx={{ display: "flex", gap: 3 }}>
          {[["claims", c.claims], ["approved", c.approved], ["modules", c.modules], ["images", c.images]].map(([label, n]) => (
            <Box key={label as string} sx={{ textAlign: "center" }}>
              <Typography sx={{ fontSize: 19, fontWeight: 800, color: "primary.dark" }}>{n}</Typography>
              <Typography sx={{ fontSize: 15, color: "text.secondary", textTransform: "uppercase" }}>{label}</Typography>
            </Box>
          ))}
        </Box>
      </Box>

      {detail.indications.length > 0 && (
        <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, mb: 5 }}>
          {detail.indications.map((i) => <Chip key={i} size="small" label={i} />)}
        </Box>
      )}

      <Section>
        <SectionHead variant="h2">Label imagery<CountChip size="small" label={detail.images.length} /></SectionHead>
        <Typography variant="body2" sx={{ color: "text.secondary", mb: 2 }}>
          Real figures from this brand's FDA Structured Product Label (public-domain). Click to enlarge.
        </Typography>
        {detail.images.length ? (
          <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: 2 }}>
            {detail.images.map((im) => (
              <GalleryTile
                key={im.blob_key}
                onClick={() =>
                  onOpenImage({ full: `/api/blob/${im.blob_key}`, caption: im.file_name || im.title, sourceUrl: im.url })
                }
              >
                <img src={`/api/blob/${im.blob_key}`} alt={im.title} loading="lazy" />
                <figcaption>{im.file_name || im.title}</figcaption>
              </GalleryTile>
            ))}
          </Box>
        ) : (
          <Typography variant="body2" sx={{ color: "text.secondary", fontStyle: "italic" }}>No label images captured.</Typography>
        )}
      </Section>

      <Section>
        <SectionHead variant="h2">Claims<CountChip size="small" label={c.claims} /></SectionHead>
        <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, mb: 1 }}>
          {statusOptions.map((s) => (
            <FilterChip key={s} on={status === s} onClick={() => setStatus(s)} label={`${s === "all" ? "All statuses" : s.replace("_", " ")} ${s === "all" ? c.claims : c.by_status[s] ?? 0}`} />
          ))}
        </Box>
        <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, mb: 3 }}>
          {typeOptions.map((t) => (
            <FilterChip key={t} on={type === t} onClick={() => setType(t)} label={`${t === "all" ? "All types" : CLAIM_TYPE_LABEL[t] ?? t} ${t === "all" ? c.claims : c.by_type[t] ?? 0}`} />
          ))}
        </Box>
        {filteredClaims.length ? (
          filteredClaims.map((cl) => <ClaimCard key={cl.id} claim={cl} />)
        ) : (
          <Typography variant="body2" sx={{ color: "text.secondary", fontStyle: "italic" }}>No claims match this filter.</Typography>
        )}
      </Section>

      <Section>
        <SectionHead variant="h2">Reusable modules<CountChip size="small" label={detail.modules.length} /></SectionHead>
        <Typography variant="body2" sx={{ color: "text.secondary", mb: 2 }}>
          Pre-approved building blocks. Approve once, assemble into many assets.
        </Typography>
        <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))", gap: 2 }}>
          {detail.modules.map((m, i) => <ModuleCard key={i} module={m} />)}
        </Box>
      </Section>

      <Section>
        <SectionHead variant="h2">Other assets<CountChip size="small" label={detail.assets.length} /></SectionHead>
        <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
          {detail.assets.map((a, i) => <AssetRow key={i} asset={a} />)}
        </Box>
      </Section>
    </Box>
  );
}
