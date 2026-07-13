import { useRef, useState } from "react";
import Box from "@mui/material/Box";
import IconButton from "@mui/material/IconButton";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import { tokens, shade, insetShadow, focusRing } from "../theme/tokens";

const Well = styled("div")(({ theme }) => ({
  display: "flex",
  gap: theme.spacing(2),
  alignItems: "flex-end",
  padding: theme.spacing(2, 2, 2, 3),
  borderRadius: tokens.radius.md,
  background: tokens.color.surface,
  border: `1px solid ${shade(0.22)}`,
  boxShadow: insetShadow,
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
  padding: theme.spacing(1, 0),
  fontFamily: tokens.font.primary,
}));

const SendKey = styled(IconButton)({
  background: tokens.color.primary,
  color: tokens.color.text,
  "&:hover": { background: tokens.color.primary, filter: "brightness(1.08)" },
  "&:active": { boxShadow: `inset 0 2px 4px ${shade(0.35)}` },
  "&.Mui-disabled": { background: shade(0.12), color: shade(0.45) },
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
        <IconButton
          size="small"
          disabled={disabled}
          onClick={() => fileRef.current?.click()}
          title="Upload a document (e.g. a brand plan) — the agent reads it for the brief"
        >
          <span className="material-symbols-outlined" style={{ fontSize: 20 }}>attach_file</span>
        </IconButton>
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
