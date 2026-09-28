"""The fixed parts of the Flow Planner SOP, loaded from a versioned seed file.

Ported from the reference project's `app/flow/sop.py`. The document is data,
this module is the reader. What lives here is everything the SOP states
outright and that no campaign can change - the suppression lists, the fixed
block wording, the legend. What does *not* live here is anything derived from
a campaign's own field values; that is `inputs.py`.

VERSION is stamped onto every generated flow. A reviewer looking at a six-week
-old journey needs to know which revision of the SOP produced it, and "the
file as it stands today" is not an answer.
"""
from __future__ import annotations

import json
import pathlib

_PATH = pathlib.Path(__file__).resolve().parent.parent.parent / "assets" / "seed" / "flow_sop_rules.json"
_DATA = json.loads(_PATH.read_text(encoding="utf-8"))

VERSION: str = _DATA.get("version", "0.0.0")
SOURCE: str = _DATA.get("source", "")

LEGEND: list[dict] = _DATA.get("legend", [])
TASK_RESPONSIBILITIES: list[str] = _DATA.get("task_responsibilities", [])
_CADENCE: dict[str, str] = _DATA.get("campaign_type_cadence", {})
_TEXT: dict[str, str] = _DATA.get("text", {})
_SUPPRESSIONS: dict[str, list[dict]] = _DATA.get("suppressions", {})

DTC, HCP = "DTC", "HCP"

# The SOP's own word for "nobody has told us yet". Used as a value, and mirrored
# into node["tbd"] so the renderer and the SA can both see what is outstanding.
TBD: str = _TEXT.get("tbd", "TBD")


def text(key: str, **fmt) -> str:
    """Fixed SOP wording by key, with {placeholders} filled in.

    Unknown keys raise rather than returning "", because a silently empty block
    in a generated journey is far harder to notice than a failing test.
    """
    if key not in _TEXT:
        raise KeyError(f"no SOP text for {key!r}; known keys: {sorted(_TEXT)}")
    return _TEXT[key].format(**fmt) if fmt else _TEXT[key]


def suppressions(audience: str) -> list[dict]:
    """The MDS suppression blocks for an audience, in SOP order.

    SOP row 5: seven separate blocks for DTC, eight for HCP. The count and the
    order are both part of the specification, so this returns the list as
    authored rather than anything derived.
    """
    return list(_SUPPRESSIONS.get(normalise_audience(audience) or DTC, []))


def cadence(campaign_type: str | None) -> str | None:
    """'Adhoc' or 'Cadenced' for the HCP target list (SOP row 3).

    None where the campaign type does not map - Model based and Real-time say
    nothing about cadence - which the caller turns into a TBD rather than
    guessing one of the two.
    """
    if not campaign_type:
        return None
    return _CADENCE.get(campaign_type.strip())


def normalise_audience(value: str | None) -> str | None:
    """DTC / HCP from a field value, or None if it is neither.

    The whole SOP forks on this one answer, so an unrecognised value must not
    quietly fall through to the DTC branch.
    """
    if not value:
        return None
    v = value.strip().upper()
    if v in (DTC, HCP):
        return v
    return None
