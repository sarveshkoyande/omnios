import { useState } from "react";
import type { BrandKit, KitUpdateSection } from "../types";

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
 *  When a panel maps to one of the five brand-plan update sections (`section` + `onUpdate`
 *  both supplied), Update is real: it navigates to that section's tab on the update screen
 *  instead of showing the stub message. Panels with no mapped section (Proof points,
 *  Clinical data, Claims library, Identity, Voice check -- none of them own a slice of
 *  the update flow's field set) keep the honest stub. */
export function SectionMeta({ kit, section, onUpdate }: {
  kit: BrandKit;
  section?: KitUpdateSection;
  onUpdate?: (section: KitUpdateSection) => void;
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
        &#9888;
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
          {section && onUpdate ? (
            <button type="button" className="section-meta-update" onClick={() => onUpdate(section)}>
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
