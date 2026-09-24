import { useState } from "react";
import type { BrandKit, JourneyStepId } from "../types";
import { Icon } from "./Icon";

function formatWhen(iso?: string): string {
  if (!iso) return "unknown";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "unknown";
  return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

/** The alert-triangle "when was this last updated, based on what, and can I update it"
 *  affordance shared by every section on the page. Honest about a real limitation: there is
 *  no per-section change history anywhere in this data model yet (the kit is still
 *  committed config, not a versioned record -- see idea 3/6 in the brand-workspace
 *  ideation doc), so every section shows the SAME file-level timestamp rather than a
 *  fabricated per-section one, and says so explicitly. "Update" is a real, honest stub --
 *  it does not silently no-op, it tells you editing isn't wired up yet.
 *
 *  When a panel maps to a brand journey step (`step` + `onUpdate` both supplied), Update is
 *  real: it opens the journey on that step instead of showing the stub message. Panels no
 *  journey step fills keep the honest stub. */
export function SectionMeta({ kit, step, onUpdate }: {
  kit: BrandKit;
  step?: JourneyStepId;
  onUpdate?: (step: JourneyStepId) => void;
}) {
  const [open, setOpen] = useState(false);
  const [updateClicked, setUpdateClicked] = useState(false);

  return (
    <div className="section-meta">
      <button
        type="button"
        className="section-meta-trigger"
        aria-label="When this was last updated"
        title="When this was last updated"
        onClick={(e) => { e.stopPropagation(); setOpen((o) => !o); }}
      >
        <Icon name="alertTriangle" size={15} />
      </button>
      {open && (
        <div className="section-meta-popover" onClick={(e) => e.stopPropagation()}>
          <div className="section-meta-row">
            <span className="section-meta-label">Last updated</span>
            <span>{formatWhen(kit.updated_at)}</span>
          </div>
          <div className="section-meta-row">
            <span className="section-meta-label">Based on</span>
            <span>{kit.source_label}</span>
          </div>
          <p className="section-meta-caveat">
            This is the brand kit file's own timestamp -- every section shares it. There is no
            per-section change history yet.
          </p>
          {step && onUpdate ? (
            <button type="button" className="section-meta-update" onClick={() => onUpdate(step)}>
              Update
            </button>
          ) : !updateClicked ? (
            <button type="button" className="section-meta-update" onClick={() => setUpdateClicked(true)}>
              Update
            </button>
          ) : (
            <p className="section-meta-caveat section-meta-stub">
              Editing isn't wired up yet -- this kit is still read-only committed config.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

const STEP_LABEL: Record<JourneyStepId, string> = {
  brief: "Brief",
  audience: "Audience",
  message: "Message",
  kit: "Kit",
  flow: "Flow",
};

/** Empty state for a workspace area a journey step fills: says it isn't planned yet and,
 *  when the workspace can open the journey, links straight to that step. Areas no journey
 *  step fills keep their own "Not available in this kit" text instead. */
export function NotPlanned({ step, onOpen, className = "overview-fact-missing" }: {
  step: JourneyStepId;
  onOpen?: (step: JourneyStepId) => void;
  className?: string;
}) {
  return (
    <span className={className}>
      Not planned yet
      {onOpen && (
        <>
          {" "}&middot;{" "}
          <button
            type="button"
            className="not-planned-link"
            onClick={(e) => { e.stopPropagation(); onOpen(step); }}
          >
            Plan in {STEP_LABEL[step]}
          </button>
        </>
      )}
    </span>
  );
}
