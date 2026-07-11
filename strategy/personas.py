"""Synthetic persona layer -- loads config/synthetic_personas.json and matches personas to a
generated plan.

A persona is a named, fictional HCP embodying one behaviour-based audience segment
(config/audience_segments.json) for a specific specialty / therapy area, deliberately
diverse across age, gender, ethnicity/background and specialty. The point is to let a Brand
Engagement Plan be pressure-tested "in character" by the range of people it is trying to
reach: persona_review.py scores the plan against each persona's channel preferences and
decision drivers and returns honest, voiced feedback.

This module is just the catalogue + matching:
  * load() / get(id)          -- the persona records (get() returns the FULL record, used
                                  both by the review engine and by the info-card endpoint)
  * match_to_plan(...)        -- rank personas by relevance to a plan's therapy area + specialty
  * card(persona)             -- the trimmed record the picker UI shows
"""
from __future__ import annotations

import json
import pathlib
import sys

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import benchmarks  # noqa: E402

PERSONAS_JSON = BASE_DIR / "config" / "synthetic_personas.json"
_CACHE: list[dict] | None = None


def load() -> list[dict]:
    global _CACHE
    if _CACHE is None:
        data = json.loads(PERSONAS_JSON.read_text(encoding="utf-8"))
        _CACHE = data.get("personas", [])
    return _CACHE


def get(persona_id: str) -> dict | None:
    return next((p for p in load() if p.get("id") == persona_id), None)


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _ta_overlap(plan_ta: str, persona_tas: list[str]) -> bool:
    t = _norm(plan_ta)
    if not t:
        return False
    return any(t == _norm(x) or t in _norm(x) or _norm(x) in t for x in persona_tas)


def match_to_plan(therapy_area: str = "", indication: str = "", audience_types: list[str] | None = None) -> dict:
    """Rank personas by relevance to a plan. A persona is 'matched' when it shares the plan's
    therapy area, or its specialty is one that treats that therapy area (via the benchmark
    therapy_area -> specialty map). Returns {matched, others} with a per-persona reason so the
    picker can explain why each is (or isn't) a natural reviewer for this plan."""
    specialties = {_norm(s) for s in (benchmarks.specialties_for(therapy_area) or [])}
    matched, others = [], []
    for p in load():
        if audience_types and p.get("audience_type") not in audience_types:
            continue
        score, reasons = 0, []
        if _ta_overlap(therapy_area, p.get("therapy_areas", [])):
            score += 3
            reasons.append("treats this therapy area")
        spec = _norm(p.get("specialty", ""))
        if spec and spec in specialties:
            score += 2
            reasons.append(f"{p['specialty']} manages these patients")
        rec = card(p)
        rec["match_score"] = score
        rec["match_reason"] = ", ".join(reasons) or "adjacent audience"
        (matched if score > 0 else others).append(rec)
    matched.sort(key=lambda r: (-r["match_score"], r["name"]))
    others.sort(key=lambda r: r["name"])
    return {"therapy_area": therapy_area, "matched": matched, "others": others}


def card(persona: dict) -> dict:
    """Trimmed record for the persona picker (no heavy prose)."""
    who = persona.get("specialty") or persona.get("condition") or ""
    return {
        "id": persona.get("id"),
        "name": persona.get("name"),
        "audience_type": persona.get("audience_type"),
        "segment_key": persona.get("segment_key"),
        "segment_name": persona.get("segment_name"),
        "specialty": persona.get("specialty", ""),
        "condition": persona.get("condition", ""),
        "who": who,
        "location": persona.get("location", ""),
        "age": persona.get("age"),
        "tagline": persona.get("tagline", ""),
        "digital_affinity": (persona.get("digital") or {}).get("affinity", ""),
        "digital_score": (persona.get("digital") or {}).get("affinity_score"),
    }
