"""Therapy-relative labels for the HCP 360 target-list segments.

The panel stores brand-relative segment names in `segment__c`: "Loyalists", "Switchers",
"High Potentials". Those read wrong on a new-brand launch. A brand with no scripts yet has
no loyalists to defend and nothing for anyone to switch away from, so a launch plan that
offers those segments is describing a market position the brand does not hold.

The fix is vocabulary, not data. The same panel rows describe *therapy-area* prescribing
behaviour, which is exactly what syndicated scripts data (IQVIA-class) can tell you before
a brand has any performance of its own. This module renames the segments to what the
underlying behaviour actually is, and carries the sourcing statement that has to appear
wherever segments are shown.

The rename is applied at the read boundary (hcp_360.py) rather than in the seed, so the
stored `segment__c` values stay canonical: SQL filters, already-saved plans, and any future
real panel keep working unchanged. `to_raw()` accepts either vocabulary, so a caller that
only ever saw the display name -- including the LLM ask() tool loop -- can still filter.
"""
from __future__ import annotations

# Raw `segment__c` value -> the therapy-relative name shown to users.
THERAPY_LABEL: dict[str, str] = {
    "High Potentials": "High prescribers of therapy",
    "Loyalists": "Loyalists to therapy area",
    "Switchers": "Existing therapy writers",
    "Emergers": "Emerging therapy writers",
    "Other NSCLC Writers": "Other therapy-class writers",
    "Non Writers": "Non-writers in therapy area",
}

# Selection criteria per segment, keyed by the raw value. Every line describes behaviour in
# the therapy area or drug class -- none of them assert anything about this brand's own
# share, which is the thing a launch cannot know.
CRITERIA: dict[str, str] = {
    "High Potentials": "Highest script volume in the therapy area -- the largest addressable pool, ranked on class volume rather than on any one brand.",
    "Loyalists": "Concentrate their class prescribing in a single therapy -- an established habit at therapy level, not brand level.",
    "Switchers": "Already write in the therapy area and move between options within it -- reachable with comparative evidence.",
    "Emergers": "Newer or lower-volume writers still building class experience -- nurture toward routine use.",
    "Other NSCLC Writers": "Write elsewhere in the drug class but are not active in this therapy -- a broad awareness play.",
    "Non Writers": "No class prescribing on record -- long-horizon disease-state education.",
}

_GENERIC_CRITERIA = "Therapy-area target-list segment from the HCP 360 panel."

# Shown next to any segment list. The point Sneha raised is that a reader cannot tell where
# a launch segmentation came from, and assumes brand performance because the old names
# implied it. State the source explicitly instead.
PROVENANCE = (
    "Segmentation is built on therapy-area prescribing behaviour from syndicated scripts "
    "data (IQVIA-class panel), not on this brand's own performance."
)

# Both vocabularies resolve back to the canonical value, so a filter written against either
# name hits the same rows.
_RAW_BY_LOWER: dict[str, str] = {raw.lower(): raw for raw in THERAPY_LABEL}
_RAW_BY_LOWER.update({shown.lower(): raw for raw, shown in THERAPY_LABEL.items()})


def to_display(raw: str | None) -> str:
    """Therapy-relative name for a stored segment value. Unknown values pass through, so a
    panel that grows a new segment degrades to showing its raw name rather than dropping it."""
    if not raw:
        return ""
    return THERAPY_LABEL.get(str(raw), str(raw))


def to_raw(value: str | None) -> str:
    """Canonical `segment__c` value for either vocabulary, for anything heading into SQL.
    Unrecognised values pass through unchanged and simply match nothing."""
    if not value:
        return ""
    return _RAW_BY_LOWER.get(str(value).strip().lower(), str(value))


def criteria_for(raw: str | None) -> str:
    """Therapy-relative selection criteria for a stored segment value."""
    return CRITERIA.get(str(raw or ""), _GENERIC_CRITERIA)


# --------------------------------------------------------------------------- #
# Panel shape.
# --------------------------------------------------------------------------- #
# Share of the panel each segment holds. A real target list is a pyramid: a small tier of
# high-volume writers over a broad base of low-engagement ones. The seed generators used to
# round-robin the segment field, which produced six segments within 0.3 points of each other
# -- so "the largest addressable segment" was decided by rounding noise, every segment looked
# equally worth leading with, and the sizing carried no information at all.
SEGMENT_MIX: dict[str, int] = {
    "High Potentials": 9,
    "Loyalists": 14,
    "Switchers": 19,
    "Emergers": 23,
    "Other NSCLC Writers": 30,
    "Non Writers": 5,
}

_MIX_SEED = 20260731


def pick_segment(rng) -> str:
    """One weighted segment draw. For row-at-a-time generators, where the total row count
    is not known up front."""
    return rng.choices(list(SEGMENT_MIX), weights=list(SEGMENT_MIX.values()), k=1)[0]


def assign_segments(count: int, seed: int = _MIX_SEED) -> list[str]:
    """Exactly `count` segment values matching SEGMENT_MIX, deterministically shuffled.

    Exact rather than sampled: re-labelling a fixed panel should land on the intended shape
    every time, not near it."""
    import random

    if count <= 0:
        return []
    counts = {name: count * share // 100 for name, share in SEGMENT_MIX.items()}
    # Integer division loses a few rows; give the remainder to the broadest segment so the
    # total is exact and the pyramid keeps its base.
    broadest = max(SEGMENT_MIX, key=lambda name: SEGMENT_MIX[name])
    counts[broadest] += count - sum(counts.values())
    out = [name for name, n in counts.items() for _ in range(n)]
    random.Random(seed).shuffle(out)
    return out
