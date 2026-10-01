"""Company-level compliance profiles (config/compliance_profiles.json).

Campaign SOPs, the approval workflow, suppression stacks and channel rules belong to the client
company, not to a brand: every brand of that company inherits the same profile. Brand-level
content (claims, safety information, do/don'ts) stays in the brand kit. A brand whose company
hasn't supplied SOPs can point at another profile as a clearly labelled template.
"""
from __future__ import annotations

import json
import pathlib

PROFILES_JSON = pathlib.Path(__file__).resolve().parent.parent / "config" / "compliance_profiles.json"


def _load() -> dict:
    if not PROFILES_JSON.exists():
        return {}
    return json.loads(PROFILES_JSON.read_text(encoding="utf-8"))


def for_brand(brand: str) -> dict | None:
    """The compliance profile a brand uses, plus the public regulatory baseline, or None when
    the brand has no profile assigned."""
    data = _load()
    link = next((v for k, v in data.get("brands", {}).items() if k.lower() == brand.strip().lower()), None)
    if not link:
        return None
    profile = data.get("profiles", {}).get(link.get("profile"))
    if not profile:
        return None
    return {**profile, "status": link.get("status", "active"), "status_note": link.get("status_note", ""),
            "regulatory_baseline": data.get("regulatory_baseline", [])}
