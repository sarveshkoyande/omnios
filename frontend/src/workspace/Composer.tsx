import { useRef, useState } from "react";
import Box from "@mui/material/Box";
import IconButton from "@mui/material/IconButton";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import { tokens, glass, glassFallback, indigoTint, gradientBrand, focusRing } from "../theme/tokens";

/** Tier-0 content well: near-opaque white so typed text stays fully legible. */
const Well = styled("div")(({ theme }) => ({
  display: "flex",
  gap: theme.spacing(1.5),
  alignItems: "flex-end",
  padding: theme.spacing(1.25, 1.25, 1.25, 2.5),
  borderRadius: tokens.radius.md,
  background: glassFallback,
  border: `1px solid ${indigoTint(0.18)}`,
  boxShadow: glass.shadow,
  "@supports ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px)))": {
    background: glass.content,
  },
  "&:focus-within": { ...focusRing, outlineOffset: 0, borderColor: tokens.color.primary },
}));

const TextArea = styled("textarea")(({ theme }) => ({
  flex: 1,
  resize: "none",
  border: "none",
  background: "transparent",
  outline: "none",
  font: "inherit",
  fontSize: tokens.fontSize.md,
  color: tokens.color.text,
  maxHeight: 120,
  padding: theme.spacing(1.5, 0),
  fontFamily: tokens.font.primary,
  "&::placeholder": { color: tokens.color.inkSoft },
}));

const IconBtn = styled(IconButton)({
  color: tokens.color.inkSoft,
  "&:hover": { background: indigoTint(0.08), color: tokens.color.primary },
});

const SendKey = styled(IconButton)({
  background: gradientBrand,
  color: "#fff",
  borderRadius: tokens.radius.sm,
  width: 38,
  height: 38,
  boxShadow: "0 3px 10px rgba(79,70,229,0.32)",
  "&:hover": { background: gradientBrand, filter: "brightness(1.08)" },
  "&:active": { transform: "translateY(1px)" },
  "&.Mui-disabled": { background: indigoTint(0.14), color: "rgba(30,27,51,0.35)", boxShadow: "none" },
});

export function Composer({
  disabled,
  onSend,
  onUpload,
}: {
  disabled: boolean;
  onSend: (text: string) => void;
  onUpload: (file: File) => void;
}) {
  const [value, setValue] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const submit = () => {
    const t = value.trim();
    if (!t || disabled) return;
    setValue("");
    onSend(t);
  };

  return (
    <Box>
      <Well>
        <IconBtn
          size="small"
          disabled={disabled}
          onClick={() => fileRef.current?.click()}
          title="Upload a document (e.g. a brand plan) — the agent reads it for the brief"
        >
          <span className="material-symbols-outlined" style={{ fontSize: 20 }}>attach_file</span>
        </IconBtn>
        <input
          ref={fileRef}
          type="file"
          accept=".pdf,.docx,.txt,.md"
          style={{ display: "none" }}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onUpload(f);
            e.target.value = "";
          }}
        />
        <TextArea
          rows={1}
          placeholder="Message the planning agent…"
          value={value}
          disabled={disabled}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
        />
        <IconBtn size="small" disabled={disabled} title="Voice input" aria-label="Voice input">
          <span className="material-symbols-outlined" style={{ fontSize: 20 }}>mic</span>
        </IconBtn>
        <SendKey disabled={disabled || !value.trim()} onClick={submit} aria-label="Send message">
          <span className="material-symbols-outlined" style={{ fontSize: 20 }}>send</span>
        </SendKey>
      </Well>
      <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mt: 1, pl: 0.5 }}>
        Enter to send · Shift+Enter for a new line · attach a file to upload a brand plan (.pdf/.docx/.txt/.md).
        No forms — the agent fills the brief on the right as you talk.
      </Typography>
    </Box>
  );
}
