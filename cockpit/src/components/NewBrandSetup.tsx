import { useState } from "react";
import { generateRandomBrandPlan, inferBrandName, setupBrand } from "../api";
import { Icon } from "./Icon";

type Step = "upload" | "territory";

/** The "+" next to Brands in the rail lands here instead of a window.prompt popup.
 *  Two steps: (1) upload a brand-plan document -- the agent reads the brand name off
 *  it rather than asking the user to type it blind; (2) confirm the territory this
 *  brand plan applies to, starting from an honest "unknown" rather than a silently
 *  assumed default, as a real single-select question with a free-text "Other" escape
 *  hatch. Finishing creates the brand and immediately ingests the same document
 *  against all 5 kit-update sections, so onComplete lands on a guided screen that
 *  already has drafts waiting, not an empty shell. */
export function NewBrandSetup({ knownTerritories, onComplete, onCancel }: {
  knownTerritories: string[];
  onComplete: (brand: string) => void;
  onCancel: () => void;
}) {
  const [step, setStep] = useState<Step>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [inferring, setInferring] = useState(false);
  const [name, setName] = useState("");
  const [nameWasInferred, setNameWasInferred] = useState(false);
  const [territory, setTerritory] = useState<string | null>(null);
  const [customTerritory, setCustomTerritory] = useState("");
  const [usingCustom, setUsingCustom] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  const handleFile = async (f: File) => {
    setFile(f);
    setError(null);
    setInferring(true);
    try {
      const r = await inferBrandName(f);
      if (r.name) {
        setName(r.name);
        setNameWasInferred(true);
      }
    } catch (e) {
      // Name inference failing is not fatal -- the user can still type the name.
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setInferring(false);
    }
  };

  /** Hidden escape hatch for when there's no real brand-plan document handy: fabricates
   *  a complete fictional one, wraps it in a synthetic .txt File, and runs it through the
   *  exact same handleFile() path a real upload takes -- no separate ingestion code path
   *  to keep in sync with the real one. */
  const generateRandom = async () => {
    setError(null);
    setGenerating(true);
    try {
      const { text } = await generateRandomBrandPlan();
      const f = new File([text], "generated-brand-plan.txt", { type: "text/plain" });
      await handleFile(f);
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setGenerating(false);
    }
  };

  const effectiveTerritory = usingCustom ? customTerritory.trim() : territory;

  const finish = async () => {
    if (!file || !name.trim() || !effectiveTerritory) return;
    setSubmitting(true);
    setError(null);
    try {
      const r = await setupBrand(file, name.trim(), effectiveTerritory);
      onComplete(r.brand);
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
      setSubmitting(false);
    }
  };

  return (
    <div className="new-brand-setup">
      <div className="new-brand-header">
        <div className="new-brand-eyebrow">Set up a new brand</div>
        <h1 className="new-brand-title">
          {step === "upload" ? "Add a brand plan" : "Confirm the territory"}
        </h1>
        {step === "upload" && (
          <button
            type="button"
            className="new-brand-secret-generate"
            title="Don't have a brand plan handy? Generate a fictional one to try the flow."
            aria-label="Generate a random brand plan"
            disabled={generating || inferring}
            onClick={generateRandom}
          >
            <Icon name="zap" size={13} />
          </button>
        )}
        <button type="button" className="kit-update-close" onClick={onCancel}>Cancel</button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {step === "upload" && (
        <div className="new-brand-card">
          <p className="new-brand-help">
            Upload the brand-plan document for the new brand. We'll read the brand name
            off it -- you can still edit it before continuing.
          </p>
          <label className="new-brand-upload">
            {file ? file.name : "Choose a file (.pdf, .docx, .txt, .md)"}
            <input
              type="file"
              accept=".pdf,.docx,.txt,.md"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
            />
          </label>

          {file && (
            <div className="new-brand-name-field">
              <label htmlFor="new-brand-name">Brand name</label>
              <input
                id="new-brand-name"
                type="text"
                value={inferring ? "Reading the document…" : name}
                disabled={inferring}
                onChange={(e) => { setName(e.target.value); setNameWasInferred(false); }}
                placeholder="e.g. CardioPulse"
              />
              {nameWasInferred && !inferring && (
                <p className="new-brand-inferred-note">
                  <Icon name="check" size={12} /> Read from the document -- edit it if that's not right.
                </p>
              )}
            </div>
          )}

          <button
            type="button"
            className="new-brand-next"
            disabled={!file || inferring || !name.trim()}
            onClick={() => setStep("territory")}
          >
            Next
          </button>
        </div>
      )}

      {step === "territory" && (
        <div className="new-brand-card">
          <p className="new-brand-help">
            Which territory does this brand plan apply to? This starts unknown on
            purpose -- pick one, or add your own if it's not in the list.
          </p>
          <div className="new-brand-territory-grid">
            {knownTerritories.map((t) => (
              <button
                key={t}
                type="button"
                className={`new-brand-territory-pill ${!usingCustom && territory === t ? "active" : ""}`}
                onClick={() => { setTerritory(t); setUsingCustom(false); }}
              >
                {t}
              </button>
            ))}
            <button
              type="button"
              className={`new-brand-territory-pill ${usingCustom ? "active" : ""}`}
              onClick={() => setUsingCustom(true)}
            >
              Other
            </button>
          </div>
          {usingCustom && (
            <input
              type="text"
              className="new-brand-territory-input"
              value={customTerritory}
              onChange={(e) => setCustomTerritory(e.target.value)}
              placeholder="Type the territory (e.g. Australia)"
              autoFocus
            />
          )}

          <div className="new-brand-actions">
            <button type="button" className="kit-update-close" onClick={() => setStep("upload")}>Back</button>
            <button
              type="button"
              className="new-brand-next"
              disabled={!effectiveTerritory || submitting}
              onClick={finish}
            >
              {submitting ? "Setting up…" : "Finish setup"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
