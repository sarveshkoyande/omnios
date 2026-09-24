import { useCallback, useEffect, useRef, useState } from "react";
import {
  getBrandKit, getJourney, journeyConfirm, journeyDocument, journeyReopen, journeyKeep, journeyTurn, journeyUndo, startJourney,
} from "../../api";
import type { BrandKit, JourneyState, JourneyStepId } from "../../types";
import { AudienceCanvas, type PersonaScope } from "./AudienceCanvas";
import { BriefCanvas } from "./BriefCanvas";
import { DraftBar } from "./DraftBar";
import type { DraftActions } from "./DraftValue";
import { FlowCanvas } from "./FlowCanvas";
import { KitCanvas } from "./KitCanvas";
import { kitFlags } from "./journeyUtils";
import { MessageCanvas } from "./MessageCanvas";
import { StepChat, type TurnState } from "./StepChat";

const STATUS_LABEL: Record<string, { tone: string; label: string }> = {
  not_started: { tone: "neutral", label: "Not started" },
  drafted: { tone: "warning", label: "Drafted" },
  confirmed: { tone: "success", label: "Confirmed" },
};

const IDLE: TurnState = { pending: false, reply: null, error: null };

/** New brand start panel (R11, F1/F2): upload a plan document or type one sentence. */
function StartPanel({ onStarted, onClose }: { onStarted: (brand: string, step: JourneyStepId) => void; onClose: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [description, setDescription] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const start = () => {
    setBusy(true);
    setError(null);
    startJourney({ file, description: description.trim(), name: name.trim() })
      .then((r) => {
        // With a document, land on the first step that got drafts (review pass); else Brief.
        const first = r.state.steps.find((s) => s.drafts.length > 0)?.step ?? "brief";
        onStarted(r.brand, file ? first : "brief");
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setBusy(false));
  };

  return (
    <div className="journey">
      <div className="kit-update-header">
        <div>
          <div className="kit-update-eyebrow">New brand</div>
          <h1 className="kit-update-title">Tell me about the brand</h1>
        </div>
        <button type="button" className="kit-update-close" onClick={onClose}>Close</button>
      </div>
      <div className="jc-card journey-start">
        <label className="jc-field-label" htmlFor="journey-sentence">In one sentence</label>
        <textarea id="journey-sentence" className="jc-input jc-textarea" rows={3} disabled={busy} value={description}
          placeholder="e.g. Cardiozen is a once-daily SGLT2 inhibitor launching in the US for heart failure."
          onChange={(e) => setDescription(e.target.value)} />
        <div className="journey-start-or">or upload a brand plan</div>
        <label className="kit-update-upload">
          {file ? file.name : "Choose a document"}
          <input type="file" disabled={busy} onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </label>
        <label className="jc-field-label" htmlFor="journey-name">Brand name (optional)</label>
        <input id="journey-name" className="jc-input" value={name} disabled={busy} onChange={(e) => setName(e.target.value)}
          placeholder="Read from the sentence or document if left blank" />
        {error && <div className="step-chat-error" role="alert">{error}</div>}
        <div className="draft-bar-actions">
          <button type="button" className="jc-btn jc-btn-keep" disabled={busy || (!file && !description.trim())} onClick={start}>
            {busy ? "Starting…" : "Start"}
          </button>
        </div>
      </div>
    </div>
  );
}

export function JourneyScreen({ brand, initialStep, onClose, onBrandCreated, onKitChanged }: {
  /** null opens the new-brand start panel. The caller keys this component by brand, so a
   *  new brand (or a different one) remounts on `initialStep` with a clean state. */
  brand: string | null;
  initialStep: JourneyStepId;
  onClose: () => void;
  onBrandCreated: (brand: string, step: JourneyStepId) => void;
  onKitChanged: () => void;
}) {
  const [step, setStep] = useState<JourneyStepId>(initialStep);
  const [state, setState] = useState<JourneyState | null>(null);
  const [kit, setKit] = useState<BrandKit | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [turn, setTurn] = useState<TurnState>(IDLE);
  const [busy, setBusy] = useState(false);
  const [barError, setBarError] = useState<string | null>(null);
  const [scope, setScope] = useState<PersonaScope | null>(null);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const [docNote, setDocNote] = useState<string | null>(null);
  // Bumped on every step switch and every turn, so a reply that lands after the user has
  // moved on (or sent again) can't write into the step chat they are now looking at.
  const turnSeq = useRef(0);

  const refreshKit = useCallback(() => {
    if (!brand) return;
    getBrandKit(brand).then((r) => setKit(r.kit)).catch(() => setKit(null));
  }, [brand]);

  useEffect(() => {
    if (!brand) return;
    getJourney(brand).then(setState).catch((e) => setLoadError(String(e)));
    refreshKit();
  }, [brand, refreshKit]);

  // Each step's chat starts clean on entry (R4).
  const goTo = (s: JourneyStepId) => {
    turnSeq.current += 1;
    setStep(s);
    setTurn(IDLE);
    setBarError(null);
    setScope(null);
  };

  if (!brand) {
    return <StartPanel onClose={onClose} onStarted={onBrandCreated} />;
  }

  const labels: Record<string, string> = Object.fromEntries((state?.steps ?? []).map((s) => [s.step, s.label]));
  const current = state?.steps.find((s) => s.step === step) ?? null;
  const drafts = current?.drafts ?? [];
  const locked = step === "kit" && current?.status === "confirmed";

  const sendTurn = async (message: string): Promise<boolean> => {
    const seq = ++turnSeq.current;
    setTurn((t) => ({ ...t, pending: true, error: null }));
    const scoped = step === "audience" && scope ? `[About the ${scope.group} persona card "${scope.name}"] ${message}` : message;
    try {
      const r = await journeyTurn(brand, step, scoped);
      // The snapshot still carries the old step's new drafts (rail counts); only the reply is stale.
      setState(r.state);
      if (seq !== turnSeq.current) return false;
      setTurn({ pending: false, reply: r.reply, error: null });
      return true;
    } catch (e) {
      if (seq !== turnSeq.current) return false;
      setTurn((t) => ({ ...t, pending: false, error: e instanceof Error ? e.message : String(e) }));
      return false;
    }
  };

  const run = (p: Promise<JourneyState>, kitTouched: boolean) => {
    setBusy(true);
    setBarError(null);
    p.then((s) => { setState(s); if (kitTouched) { refreshKit(); onKitChanged(); } })
      .catch((e) => setBarError(e instanceof Error ? e.message : String(e)))
      .finally(() => setBusy(false));
  };

  const actions: DraftActions = {
    locked,
    busy,
    onKeep: (ids) => run(journeyKeep(brand, step, ids), true),
    onUndo: (ids) => run(journeyUndo(brand, step, ids), false),
  };

  const flags = step === "kit" ? kitFlags(kit, drafts).filter((f) => !dismissed.has(f.key)) : [];
  const confirmBlocked = flags.length > 0
    ? `Resolve ${flags.length} flag${flags.length === 1 ? "" : "s"} before confirming.`
    : drafts.length > 0 ? "Keep or undo the pending drafts first." : null;

  const uploadDoc = (file: File) => {
    setBusy(true);
    setDocNote(null);
    journeyDocument(brand, file)
      .then((r) => {
        setState(r.state);
        setDocNote(r.changed_steps.length
          ? `New drafts on ${r.changed_steps.map((s) => labels[s] ?? s).join(", ")}.`
          : "The document didn't change any step.");
        if (r.changed_steps.length) goTo(r.changed_steps[0]);
      })
      .catch((e) => setDocNote(`Upload failed: ${e instanceof Error ? e.message : String(e)}`))
      .finally(() => setBusy(false));
  };

  const canvas = () => {
    switch (step) {
      case "brief": return <BriefCanvas brand={brand} kit={kit} drafts={drafts} actions={actions} onSend={(m) => { void sendTurn(m); }} />;
      case "audience": return <AudienceCanvas kit={kit} drafts={drafts} actions={actions} scope={scope} onScope={setScope} />;
      case "message": return <MessageCanvas kit={kit} drafts={drafts} actions={actions} />;
      case "kit": return <KitCanvas kit={kit} drafts={drafts} actions={actions} flags={kitFlags(kit, drafts)} dismissed={dismissed}
        onDismiss={(k) => setDismissed((d) => new Set(d).add(k))} />;
      case "flow": return current ? <FlowCanvas key={brand} brand={brand} labels={labels} step={current} onState={setState} /> : null;
    }
  };

  return (
    <div className="journey">
      <div className="kit-update-header">
        <div>
          <div className="kit-update-eyebrow">Brand journey</div>
          <h1 className="kit-update-title">{brand}</h1>
        </div>
        <div className="journey-head-actions">
          <label className="kit-update-upload" title="Upload a revised plan; only the steps it changes get drafts">
            Upload revised plan
            <input type="file" disabled={busy} onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadDoc(f); e.target.value = ""; }} />
          </label>
          <button type="button" className="kit-update-close" onClick={onClose}>Close</button>
        </div>
      </div>
      {docNote && <div className="jc-waiting">{docNote}</div>}
      {loadError && <div className="error-banner">Couldn't load the journey: {loadError}</div>}

      <nav className="journey-rail" aria-label="Journey steps">
        {(state?.steps ?? []).map((s) => {
          const st = STATUS_LABEL[s.status] ?? STATUS_LABEL.not_started;
          return (
            <button key={s.step} type="button" className={`journey-rail-step ${s.step === step ? "active" : ""}`}
              aria-current={s.step === step ? "step" : undefined} onClick={() => goTo(s.step)}>
              <span className="journey-rail-label">{s.label}</span>
              <span className={`pill tone-${st.tone}`}>{st.label}{s.drafts.length > 0 ? ` · ${s.drafts.length}` : ""}</span>
              {s.waiting.length > 0 && s.status !== "confirmed" && (
                <span className="journey-rail-waiting">Waiting on {s.waiting.map((w) => labels[w] ?? w).join(", ")}</span>
              )}
            </button>
          );
        })}
      </nav>

      {state && current && (
        <>
          {current.waiting.length > 0 && current.status !== "confirmed" && step !== "flow" && (
            <div className="jc-waiting">This step is waiting on {current.waiting.map((w) => labels[w] ?? w).join(", ")}. You can still work on it.</div>
          )}
          <div className="journey-canvas">{canvas()}</div>
          {step !== "flow" && (
            <>
              <DraftBar draftCount={drafts.length} status={current.status} busy={busy} error={barError}
                confirmBlocked={confirmBlocked}
                onKeepAll={() => run(journeyKeep(brand, step, "all"), true)}
                onUndoAll={() => run(journeyUndo(brand, step, drafts.map((d) => d.id)), false)}
                onConfirm={() => run(journeyConfirm(brand, step), false)}
                onReopen={() => run(journeyReopen(brand, step), false)} />
              <StepChat key={step} brand={brand} step={step} question={current.question} earlierCount={current.earlier_count}
                turn={turn} locked={locked} onSend={sendTurn}
                scopeLabel={step === "audience" && scope ? scope.name : null} onClearScope={() => setScope(null)} />
            </>
          )}
        </>
      )}
      {!state && !loadError && <div className="loading">Loading journey&hellip;</div>}
    </div>
  );
}
