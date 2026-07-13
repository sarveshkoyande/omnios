import { useEffect, useState } from "react";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Dialog from "@mui/material/Dialog";
import IconButton from "@mui/material/IconButton";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import { fetchPersonaDetail } from "../../api";
import type { PersonaDetail } from "../types";
import { personaInitials } from "./personaUtils";
import { shade, panelShadow } from "../../theme/tokens";

const Fact = styled(Box)(({ theme }) => ({
  background: shade(0.03),
  border: `1px solid ${shade(0.14)}`,
  borderRadius: 9,
  padding: theme.spacing(1.25, 1.5),
  textAlign: "center",
}));

const ChanRow = styled(Box)(({ theme }) => ({
  display: "flex",
  justifyContent: "space-between",
  fontSize: 12,
  padding: theme.spacing(0.5, 0),
}));

export function PersonaProfileModal({ personaId, onClose }: { personaId: string | null; onClose: () => void }) {
  const [detail, setDetail] = useState<PersonaDetail | null>(null);

  useEffect(() => {
    if (!personaId) {
      setDetail(null);
      return;
    }
    fetchPersonaDetail(personaId).then(setDetail).catch(() => setDetail(null));
  }, [personaId]);

  return (
    <Dialog open={!!personaId} onClose={onClose} maxWidth="sm" fullWidth slotProps={{ paper: { sx: { boxShadow: panelShadow } } }}>
      {detail && (
        <Box sx={{ p: 4, position: "relative" }}>
          <IconButton onClick={onClose} sx={{ position: "absolute", top: 12, right: 12 }} aria-label="Close">
            <span className="material-symbols-outlined">close</span>
          </IconButton>
          <Box sx={{ display: "flex", gap: 2, alignItems: "center", mb: 1 }}>
            <Box
              sx={{
                width: 54, height: 54, borderRadius: "50%", flex: "0 0 auto",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 18, fontWeight: 700, color: "#fff",
                background: "linear-gradient(135deg,#1768D1,#4AA6F2)",
              }}
            >
              {personaInitials(detail.name)}
            </Box>
            <Box>
              <Typography variant="h3" sx={{ fontSize: 18 }}>{detail.name}</Typography>
              <Typography variant="caption" sx={{ color: "text.secondary", display: "block" }}>
                {detail.specialty} · {detail.age ?? "—"} · {detail.gender} · {detail.ethnicity}
              </Typography>
              <Typography variant="caption" sx={{ color: "text.secondary", display: "block" }}>
                {detail.location} {detail.years_in_practice ? `· ${detail.years_in_practice} yrs in practice` : ""}
              </Typography>
            </Box>
          </Box>

          {detail.tagline && (
            <Typography sx={{ fontStyle: "italic", color: "primary.dark", my: 1.5 }}>{detail.tagline}</Typography>
          )}

          <Box sx={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 1, mb: 2 }}>
            <Fact><b>{detail.prescribing?.monthly_trx ?? "—"}</b><br /><Typography variant="caption">Monthly TRx</Typography></Fact>
            <Fact><b>{detail.prescribing?.monthly_nrx ?? "—"}</b><br /><Typography variant="caption">Monthly NRx</Typography></Fact>
            <Fact><b>{detail.digital?.affinity ?? "—"}</b><br /><Typography variant="caption">Digital ({detail.digital?.affinity_score ?? "—"})</Typography></Fact>
          </Box>

          {detail.bio && <Typography variant="body2" sx={{ mb: 2 }}>{detail.bio}</Typography>}
          {detail.voice_sample && (
            <Typography sx={{ borderLeft: "3px solid", borderColor: "primary.main", pl: 1.5, fontStyle: "italic", mb: 2 }}>
              &ldquo;{detail.voice_sample}&rdquo;
            </Typography>
          )}

          <Box sx={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1.5, mb: 1.5 }}>
            <Box>
              <Typography variant="overline" sx={{ display: "block", mb: 0.5 }}>Prefers</Typography>
              {detail.channels?.preferred?.map((c) => <Chip key={c} size="small" label={c} sx={{ mr: 0.5, mb: 0.5 }} />)}
            </Box>
            <Box>
              <Typography variant="overline" sx={{ display: "block", mb: 0.5 }}>Avoids</Typography>
              {detail.channels?.avoided?.map((c) => <Chip key={c} size="small" label={c} sx={{ mr: 0.5, mb: 0.5 }} />)}
            </Box>
          </Box>

          <Box sx={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1.5, mb: 1.5 }}>
            <Box>
              <Typography variant="overline" sx={{ display: "block", mb: 0.5 }}>Decision drivers</Typography>
              <Box component="ul" sx={{ m: 0, pl: 2, fontSize: 12 }}>
                {detail.decision_drivers?.map((x, i) => <li key={i}>{x}</li>)}
              </Box>
            </Box>
            <Box>
              <Typography variant="overline" sx={{ display: "block", mb: 0.5 }}>Frustrations</Typography>
              <Box component="ul" sx={{ m: 0, pl: 2, fontSize: 12 }}>
                {detail.frustrations?.map((x, i) => <li key={i}>{x}</li>)}
              </Box>
            </Box>
          </Box>

          <ChanRow><span>In-person stance</span><b>{detail.channels?.f2f_stance ?? "—"}</b></ChanRow>
          <ChanRow><span>Email stance</span><b>{detail.channels?.email_stance ?? "—"}</b></ChanRow>
          <ChanRow><span>Adoption curve</span><b>{detail.prescribing?.adoption_curve ?? "—"}</b></ChanRow>
          <ChanRow><span>Rep access</span><b>{detail.digital?.rep_access ?? "—"}</b></ChanRow>
        </Box>
      )}
    </Dialog>
  );
}
