import { useEffect, useMemo, useState } from "react";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { fetchLibraryBrand, fetchLibraryIndex } from "../api";
import { StatOdometer } from "../components/StatOdometer";
import { InsetTextField } from "../components/InsetTextField";
import { LibraryBrandCard } from "./LibraryBrandCard";
import { LibraryDetailView } from "./LibraryDetailView";
import { Lightbox } from "./Lightbox";
import type { LightboxImage } from "./Lightbox";
import type { LibraryDetail, LibraryIndex } from "./types";

export function Library() {
  const [index, setIndex] = useState<LibraryIndex | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [brandName, setBrandName] = useState<string | null>(null);
  const [detail, setDetail] = useState<LibraryDetail | null>(null);
  const [lightboxImage, setLightboxImage] = useState<LightboxImage | null>(null);

  useEffect(() => {
    fetchLibraryIndex().then(setIndex).catch((e) => setError(String(e)));
  }, []);

  const openBrand = (name: string) => {
    setBrandName(name);
    setDetail(null);
    fetchLibraryBrand(name).then(setDetail).catch(() => setDetail(null));
  };

  const grouped = useMemo(() => {
    if (!index) return [];
    const q = query.trim().toLowerCase();
    const shown = index.brands.filter(
      (b) => !q || [b.brand, b.generic_name, b.therapy_area, b.client].some((v) => (v ?? "").toLowerCase().includes(q)),
    );
    const byClient = new Map<string, typeof shown>();
    shown.forEach((b) => {
      const key = b.client || "Other";
      if (!byClient.has(key)) byClient.set(key, []);
      byClient.get(key)!.push(b);
    });
    return [...byClient.entries()];
  }, [index, query]);

  if (brandName) {
    return (
      <Box sx={{ maxWidth: 1240, mx: "auto", px: 6, py: 6 }}>
        {detail ? (
          <LibraryDetailView
            detail={detail}
            onBack={() => { setBrandName(null); setDetail(null); }}
            onOpenImage={setLightboxImage}
          />
        ) : (
          <Typography sx={{ fontStyle: "italic", color: "text.secondary" }}>Loading {brandName}…</Typography>
        )}
        <Lightbox image={lightboxImage} onClose={() => setLightboxImage(null)} />
      </Box>
    );
  }

  const totals = index?.totals ?? {};
  return (
    <Box sx={{ maxWidth: 1240, mx: "auto", px: 6, py: 6, display: "flex", flexDirection: "column", gap: 6 }}>
      <Box>
        <Typography variant="h1">Claims Library</Typography>
        <Typography variant="body2" sx={{ color: "text.secondary", mt: 1 }}>
          Every governed claim, its substantiating references, the reusable modules built from it, and the
          brand's real FDA label imagery. Pick a brand to review its content.
        </Typography>
        {error && (
          <Typography variant="body2" sx={{ color: "error.main", mt: 2 }}>Could not reach /api/library ({error})</Typography>
        )}
      </Box>

      <Box sx={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
        <StatOdometer value={totals.claims ?? 0} label="Claims" />
        <StatOdometer value={totals.claims_approved ?? 0} label="MLR-approved" />
        <StatOdometer value={totals.references ?? 0} label="References" />
        <StatOdometer value={totals.content_modules ?? 0} label="Modules" />
        <StatOdometer value={totals.content_assets ?? 0} label="Assets" />
        {totals.unsubstantiated_claims ? (
          <StatOdometer value={totals.unsubstantiated_claims} label="Unsubstantiated" alert />
        ) : null}
      </Box>

      <InsetTextField
        placeholder="Search brands, generics or therapy areas…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        sx={{ maxWidth: 420 }}
      />

      {grouped.map(([client, brands]) => (
        <Box key={client}>
          <Box sx={{ display: "flex", alignItems: "baseline", gap: 2, mb: 3 }}>
            <Typography variant="h2">{client}</Typography>
            <Typography variant="caption" sx={{ color: "text.secondary" }}>{brands.length} brands</Typography>
          </Box>
          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr", lg: "1fr 1fr 1fr" }, gap: 4 }}>
            {brands.map((b) => <LibraryBrandCard key={b.brand} brand={b} onOpen={openBrand} />)}
          </Box>
        </Box>
      ))}

      {index && grouped.length === 0 && (
        <Typography sx={{ color: "text.secondary", fontStyle: "italic" }}>No brands match "{query}".</Typography>
      )}
    </Box>
  );
}
