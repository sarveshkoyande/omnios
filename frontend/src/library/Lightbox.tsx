import Box from "@mui/material/Box";
import Dialog from "@mui/material/Dialog";
import IconButton from "@mui/material/IconButton";
import Link from "@mui/material/Link";
import Typography from "@mui/material/Typography";

export interface LightboxImage {
  full: string;
  caption: string;
  sourceUrl?: string;
}

export function Lightbox({ image, onClose }: { image: LightboxImage | null; onClose: () => void }) {
  return (
    <Dialog
      open={!!image}
      onClose={onClose}
      maxWidth="lg"
      slotProps={{ paper: { sx: { background: "transparent", boxShadow: "none", overflow: "visible" } } }}
    >
      {image && (
        <Box sx={{ position: "relative", display: "flex", flexDirection: "column", gap: 1.5, alignItems: "center" }}>
          <IconButton
            onClick={onClose}
            aria-label="Close"
            sx={{ position: "absolute", top: -18, right: -18, background: "rgba(255,255,255,0.9)", "&:hover": { background: "#fff" } }}
          >
            <span className="material-symbols-outlined">close</span>
          </IconButton>
          <Box
            component="img"
            src={image.full}
            alt={image.caption}
            sx={{ maxWidth: "88vw", maxHeight: "78vh", objectFit: "contain", background: "#fff", borderRadius: 2, p: 1.5 }}
          />
          <Typography sx={{ color: "#fff", fontSize: 12, textAlign: "center" }}>
            {image.caption}
            {image.sourceUrl && (
              <>
                {" — "}
                <Link href={image.sourceUrl} target="_blank" rel="noreferrer" sx={{ color: "#9fd8ff" }}>
                  view on DailyMed
                </Link>
              </>
            )}
          </Typography>
        </Box>
      )}
    </Dialog>
  );
}
