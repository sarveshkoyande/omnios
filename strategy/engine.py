"""Combines the static rule tables (rules.py) with live knowledge-repo lookups
to generate a campaign strategy recommendation from a small set of inputs."""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from rules import CHANNEL_TOUCHPOINTS, PERSONA_MULTIPLIERS, STAGE_BY_KEY, STAGES  # noqa: E402
from paths import data_path  # noqa: E402

DB_PATH = data_path("omni_kb.db")


def _compute_channel_mix(stage_key: str, persona: str) -> dict[str, float]:
    stage = STAGE_BY_KEY[stage_key]
    base = stage["base_channel_mix"]
    mult = PERSONA_MULTIPLIERS.get(persona, {c: 1.0 for c in base})

    weighted = {ch: base.get(ch, 0) * mult.get(ch, 1.0) for ch in base}
    total = sum(weighted.values()) or 1.0
    normalized = {ch: round(v / total * 100, 1) for ch, v in weighted.items()}

    # Fix rounding drift so percentages sum to exactly 100.
    drift = round(100 - sum(normalized.values()), 1)
    if drift and normalized:
        top_channel = max(normalized, key=normalized.get)
        normalized[top_channel] = round(normalized[top_channel] + drift, 1)
    return normalized


def _kb_grounding(search_term: str, limit: int = 5) -> dict[str, list[dict]]:
    result = {"clinicaltrials": [], "pubmed": [], "openfda": [], "dailymed": [], "google_trends": []}
    if not search_term or not DB_PATH.exists():
        return result

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    for source in result:
        rows = conn.execute(
            """
            SELECT title, url, metadata_json FROM documents
            WHERE source = ? AND search_term LIKE ?
            ORDER BY fetched_at DESC LIMIT ?
            """,
            (source, f"%{search_term}%", limit),
        ).fetchall()
        for r in rows:
            meta = {}
            try:
                meta = json.loads(r["metadata_json"] or "{}")
            except json.JSONDecodeError:
                pass
            result[source].append({"title": r["title"], "url": r["url"], "metadata": meta})
    conn.close()
    return result


def generate_strategy(brand: str, therapy_area: str, persona: str, stage_key: str,
                      brief_grounding: dict[str, dict] | None = None) -> dict:
    stage = STAGE_BY_KEY.get(stage_key)
    if stage is None:
        raise ValueError(f"Unknown stage key: {stage_key}")

    channel_mix = _compute_channel_mix(stage_key, persona)
    recommended_touchpoints = {
        ch: CHANNEL_TOUCHPOINTS[ch] for ch, pct in channel_mix.items() if pct > 0
    }

    kb_brand = _kb_grounding(brand)
    kb_therapy = _kb_grounding(therapy_area) if therapy_area else {}

    return {
        "inputs": {"brand": brand, "therapy_area": therapy_area, "persona": persona, "stage": stage["label"]},
        "stage_profile": {
            "mental_state": stage["mental_state"],
            "core_barrier": stage["core_barrier"],
            "engagement_goal": stage["engagement_goal"],
            "promotion_signal": stage["promotion_signal"],
        },
        "messaging_architecture": {
            "current_belief": stage["current_belief"],
            "desired_belief": stage["desired_belief"],
            "proof_points": stage["proof_points"],
            "tone_constraint": stage["tone_constraint"],
            "messaging_type": stage["messaging_type"],
        },
        "channel_mix_pct": channel_mix,
        "recommended_touchpoints": recommended_touchpoints,
        "primary_touchpoints_for_stage": stage["primary_touchpoints"],
        "kb_grounding": {
            "brand": kb_brand,
            "therapy_area": kb_therapy,
        },
        "brief_grounding": brief_grounding or {},
        "caveat": "Channel-mix percentages are an illustrative starting allocation synthesized from the stage/persona framework, not measured MMx output -- replace with real spend/response data as it becomes available.",
    }


def market_landscape(brand: str, therapy_area: str) -> dict:
    """Stage-1 (Market & Landscape) view: real KB documents for the brand and therapy
    area, with no persona/journey-stage inputs required -- just the raw grounding."""
    return {
        "brand": _kb_grounding(brand, limit=10),
        "therapy_area": _kb_grounding(therapy_area, limit=10) if therapy_area else {},
    }


def list_stage_options() -> list[dict]:
    return [{"key": s["key"], "label": s["label"]} for s in STAGES]


def list_persona_options() -> list[str]:
    return list(PERSONA_MULTIPLIERS.keys())
