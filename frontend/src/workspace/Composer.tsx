import { useEffect, useRef, useState } from "react";
import Box from "@mui/material/Box";
import GlobalStyles from "@mui/material/GlobalStyles";
import IconButton from "@mui/material/IconButton";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";
import { keyframes } from "@emotion/react";
import { tokens, glass, indigoTint, shade, focusRing } from "../theme/tokens";

/** The traveling glow's two colour stops: the brand gradient's blue and violet. */
const GLOW_A = tokens.color.primary;
const GLOW_B = tokens.color.secondary;

/**
 * A thin pink/blue/purple light that travels counter-clockwise around the
 * input while there is text, plus a soft breathing pulse. The colours are
 * driven by an animated custom property so the light sweeps around the border
 * without the ring shape itself rotating (no gaps). Kept deliberately subtle:
 * low opacity, a thin ring, a small blur.
 */
const travelCCW = keyframes`
  to { --omni-glow-angle: -360deg; }
`;
const glowBreath = keyframes`
  0%, 100% { opacity: 0.21; }
  50% { opacity: 0.3; }
`;
/** Send button: a slow diagonal gradient drift, no glow. */
const slideGradient = keyframes`
  0% { background-position: 0% 0%; }
  100% { background-position: 100% 100%; }
`;

/**
 * Glow wrapper: the traveling backlight lives on THIS element's pseudos, and the
 * white box (Well) is rendered as a child that paints on top of them. That layering
 * is deliberate — a negative-z pseudo on the Well itself paints ABOVE the Well's own
 * background, which bled the glow through the interior. Here the opaque Well covers
 * the centre and only the blurred overhang peeks out around the edges.
 */
const GlowWrap = styled("div", { shouldForwardProp: (prop) => prop !== "active" })<{ active?: boolean }>(
  ({ active }) => ({
    position: "relative",
    borderRadius: tokens.radius.md,
    ...(active && {
      "&::before": {
        content: '""',
        position: "absolute",
        inset: -3,
        borderRadius: "inherit",
        background:
          `conic-gradient(from var(--omni-glow-angle, 0deg), ${GLOW_A}, ${GLOW_B}, ${GLOW_A})`,
        filter: "blur(7px)",
        opacity: 0.6,
        pointerEvents: "none",
        animation: `${travelCCW} 6s linear infinite, ${glowBreath} 2.8s ease-in-out infinite`,
      },
      // A wider, softer halo further back for a diffuse spread.
      "&::after": {
        content: '""',
        position: "absolute",
        inset: -7,
        borderRadius: "inherit",
        background:
          `conic-gradient(from var(--omni-glow-angle, 0deg), ${GLOW_A}, ${GLOW_B}, ${GLOW_A})`,
        filter: "blur(15px)",
        opacity: 0.45,
        pointerEvents: "none",
        animation: `${travelCCW} 6s linear infinite, ${glowBreath} 2.8s ease-in-out infinite`,
      },
    }),
  })
);

/** Tier-0 content well: fully opaque white, sits on top of the glow so text stays crisp. */
const Well = styled("div")(({ theme }) => ({
  position: "relative",
  zIndex: 1,
  display: "flex",
  gap: theme.spacing(1.5),
  alignItems: "center",
  padding: theme.spacing(1, 1.25, 1, 2),
  borderRadius: tokens.radius.md,
  background: "#fff",
  border: `1px solid ${indigoTint(0.18)}`,
  boxShadow: glass.shadow,
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
  lineHeight: 1.5,
  color: tokens.color.text,
  maxHeight: 240,
  overflowY: "auto",
  minHeight: 24,
  padding: theme.spacing(0.75, 0),
  fontFamily: tokens.font.primary,
  "&::placeholder": { color: tokens.color.inkSoft },
}));

const IconBtn = styled(IconButton)({
  color: tokens.color.inkSoft,
  width: 34,
  height: 34,
  alignSelf: "center",
  "&:hover": { background: indigoTint(0.08), color: tokens.color.primary },
});

const SendKey = styled(IconButton, { shouldForwardProp: (prop) => prop !== "active" })<{ active?: boolean }>(
  ({ active }) => ({
    color: "#fff",
    borderRadius: tokens.radius.sm,
    width: 38,
    height: 38,
    backgroundImage: `linear-gradient(45deg, ${GLOW_A}, ${GLOW_B})`,
    backgroundSize: "300% 300%",
    boxShadow: `0 3px 10px ${indigoTint(0.32)}`,
    animation: active ? `${slideGradient} 15s linear infinite` : "none",
    "&:hover": { filter: "brightness(1.08)" },
    "&:active": { transform: "translateY(1px)" },
    "&.Mui-disabled": {
      backgroundImage: "none",
      background: indigoTint(0.14),
      color: shade(0.35),
      boxShadow: "none",
      animation: "none",
    },
  })
);

const SymbolIcon = styled("span")({
  display: "block",
  fontSize: 20,
  lineHeight: 1,
});

/** The installed TS DOM lib ships SpeechRecognitionResult(List) but not the two event
 * shapes below -- declared locally rather than widening the global lib. Both prefixed and
 * unprefixed constructors are accessed dynamically, so the recognizer instance is untyped. */
interface SpeechRecognitionEvent extends Event {
  readonly resultIndex: number;
  readonly results: SpeechRecognitionResultList;
}
interface SpeechRecognitionErrorEvent extends Event {
  readonly error: string;
}

type SpeechRecognizer = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((e: SpeechRecognitionEvent) => void) | null;
  onerror: ((e: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};

function getSpeechRecognitionCtor(): (new () => SpeechRecognizer) | null {
  const w = window as Window & {
    SpeechRecognition?: new () => SpeechRecognizer;
    webkitSpeechRecognition?: new () => SpeechRecognizer;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

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
  const [recording, setRecording] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const textAreaRef = useRef<HTMLTextAreaElement>(null);
  const baseHeightRef = useRef<number | null>(null);
  const recognizerRef = useRef<SpeechRecognizer | null>(null);
  const recordingRef = useRef(false); // mirrors `recording` for use inside async event handlers
  const baseTextRef = useRef(""); // committed text at the moment dictation started, so interim results never clobber it
  const hasText = value.trim().length > 0;
  const speechSupported = !!getSpeechRecognitionCtor();

  useEffect(() => {
    const el = textAreaRef.current;
    if (!el) return;
    const styles = window.getComputedStyle(el);
    const lineHeight = Number.parseFloat(styles.lineHeight || "0") || 24;
    const paddingTop = Number.parseFloat(styles.paddingTop || "0") || 0;
    const paddingBottom = Number.parseFloat(styles.paddingBottom || "0") || 0;
    const borderTop = Number.parseFloat(styles.borderTopWidth || "0") || 0;
    const borderBottom = Number.parseFloat(styles.borderBottomWidth || "0") || 0;
    const currentBase = lineHeight + paddingTop + paddingBottom + borderTop + borderBottom;
    baseHeightRef.current = Number.isFinite(currentBase) && currentBase > 0 ? currentBase : 44;
  }, []);

  useEffect(() => {
    const el = textAreaRef.current;
    if (!el) return;
    const baseHeight = baseHeightRef.current ?? 44;
    const maxHeight = baseHeight * 4;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`;
  }, [value]);

  const submit = () => {
    const t = value.trim();
    if (!t || disabled) return;
    setValue("");
    baseTextRef.current = "";
    onSend(t);
  };

  const stopDictation = () => {
    recordingRef.current = false;
    setRecording(false);
    recognizerRef.current?.stop();
  };

  const startDictation = () => {
    const Ctor = getSpeechRecognitionCtor();
    if (!Ctor) return;
    baseTextRef.current = value ? `${value} ` : "";
    const rec = new Ctor();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = "en-US";
    rec.onresult = (e) => {
      let finalChunk = "";
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const transcript = e.results[i][0].transcript;
        if (e.results[i].isFinal) finalChunk += transcript;
        else interim += transcript;
      }
      if (finalChunk) baseTextRef.current += finalChunk;
      setValue((baseTextRef.current + interim).trimStart());
    };
    rec.onerror = (e) => {
      // "no-speech"/"aborted" fire during normal long pauses (silence, background restart) --
      // keep the mic open through those; only a real permission/device failure stops it.
      if (e.error === "not-allowed" || e.error === "audio-capture") stopDictation();
    };
    rec.onend = () => {
      // Chrome ends the recognizer after each utterance even in continuous mode -- restart
      // it transparently so dictation keeps going until the user explicitly stops it.
      if (recordingRef.current) rec.start();
    };
    recognizerRef.current = rec;
    recordingRef.current = true;
    setRecording(true);
    rec.start();
  };

  useEffect(() => () => { recordingRef.current = false; recognizerRef.current?.stop(); }, []);

  return (
    <Box>
      {/* Registered so the conic gradient angle can be smoothly animated. */}
      <GlobalStyles
        styles={{
          "@property --omni-glow-angle": {
            syntax: "'<angle>'",
            inherits: "false",
            initialValue: "0deg",
          },
        }}
      />
      <GlowWrap active={hasText && !disabled}>
      <Well>
        <IconBtn
          size="small"
          disabled={disabled}
          onClick={() => fileRef.current?.click()}
          title="Upload a document (e.g. a brand plan): the agent reads it for the brief"
        >
          <SymbolIcon className="material-symbols-outlined">attach_file</SymbolIcon>
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
          ref={textAreaRef}
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
        <IconBtn
          size="small"
          disabled={disabled || !speechSupported}
          onClick={() => (recording ? stopDictation() : startDictation())}
          title={speechSupported ? (recording ? "Stop dictation" : "Voice input") : "Voice input not supported in this browser"}
          aria-label={recording ? "Stop dictation" : "Voice input"}
          sx={recording ? { color: tokens.color.danger, "&:hover": { color: tokens.color.danger } } : undefined}
        >
          <SymbolIcon className="material-symbols-outlined">{recording ? "stop_circle" : "mic"}</SymbolIcon>
        </IconBtn>
        <SendKey active={hasText && !disabled} disabled={disabled || !value.trim()} onClick={submit} aria-label="Send message">
          <SymbolIcon className="material-symbols-outlined">send</SymbolIcon>
        </SendKey>
      </Well>
      </GlowWrap>
      <Typography variant="caption" sx={{ color: "text.secondary", display: "block", mt: 1, pl: 0.5 }}>
        Enter to send. Shift+Enter for a new line. Attach a file to upload a brand plan (.pdf/.docx/.txt/.md).
      </Typography>
    </Box>
  );
}
