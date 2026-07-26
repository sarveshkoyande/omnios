"""Reporting & Insights payload for the Reporting tab (and the Reporting agent's grounding).

Assembles, for one project:
  * funnel      -- the stage-promotion signal funnel for the priority journey stage
                   (email open -> site visit -> first rep meeting accepted), the last being
                   the primary promotion signal.
  * kpis        -- delivery & engagement KPI cards (impressions, CTR, unbranded content
                   completion, email open rate) with benchmark target bands.
  * demographics-- real aggregates from the HCP 360 panel (by specialty / channel / segment).
  * tagging     -- the link/tagging (UTM) matrix deliverable: every URL carries campaign +
                   job-code tagging.
  * test_design -- the A/B test design (2-3 subject-line/preheader variants per email,
                   modular reuse-first).

Rate targets are grounded in config/omnichannel_benchmarks.json (industry baselines) scaled by
the plan's lifecycle index; volumes are grounded in the HCP panel size. Everything is a
measurement TARGET/benchmark, not observed performance -- no live performance feed is wired.
Degrades gracefully: returns what it can even with a thin plan or an unloaded panel.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import benchmarks  # noqa: E402
import hcp_360  # noqa: E402
import projects as pstore  # noqa: E402

# lifecycle label/keyword -> benchmark lifecycle key (config/omnichannel_benchmarks.json)
_LIFECYCLE_KEY = {
    "launch": "launch", "growth": "growth", "mature": "mature",
    "loe": "loe", "defend": "loe", "decline": "loe", "exclusivity": "loe",
}
_AVG_FREQUENCY = 8  # impressions per targeted HCP over a flight -- for the volume target


def _lifecycle_key(label: str, fallback: str = "growth") -> str:
    low = (label or "").strip().lower()
    for frag, key in _LIFECYCLE_KEY.items():
        if frag in low:
            return key
    return fallback


def _band(base_pct: float, idx: float) -> dict:
    """A rate KPI's target band: baseline x lifecycle index, +/-15% working band."""
    target = base_pct * idx
    return {
        "value_pct": round(target, 1),
        "low_pct": round(target * 0.85, 1),
        "high_pct": round(target * 1.15, 1),
        "band": f"{round(target * 0.85, 1)}–{round(target * 1.15, 1)}%",
    }


def _demographics() -> dict:
    """Real HCP-panel aggregates. Empty (available False) if the panel isn't loaded."""
    try:
        hcp_360.load_hcp_360()  # idempotent: no-op once loaded
        stats = hcp_360.stats()
        total = next((v for k, v in stats.items() if k.endswith("demographic_data__dlm")), 0)
        if not total:
            return {"available": False}
        def top(dim: str, n: int = 6) -> list:
            try:
                return [r for r in hcp_360.segment_summary(dim) if r.get("value")][:n]
            except Exception:  # noqa: BLE001
                return []
        return {
            "available": True,
            "total_hcps": total,
            "by_specialty": top("specialty"),
            "by_preferred_channel": top("preferred_channel"),
            "by_segment": top("segment"),
            "by_state": top("state"),
        }
    except Exception:  # noqa: BLE001
        return {"available": False}


def _tagging_matrix(brand: str) -> dict:
    slug = (brand or "brand").strip().lower().replace(" ", "") or "brand"
    return {
        "note": "Link/tagging matrix deliverable — every URL carries campaign + job-code "
                "tagging, enforced at asset build so all traffic is attributable.",
        "columns": ["Parameter", "Convention", "Example"],
        "rows": [
            {"parameter": "utm_source", "convention": "sending platform / system", "example": "veeva"},
            {"parameter": "utm_medium", "convention": "channel bucket", "example": "email"},
            {"parameter": "utm_campaign", "convention": "brand_stage_YYYYQx", "example": f"{slug}_aware_2026q1"},
            {"parameter": "utm_content", "convention": "asset id + variant", "example": "moa_v2"},
            {"parameter": "utm_term", "convention": "audience / segment", "example": "med_onc_high_writer"},
            {"parameter": "job_code", "convention": "MLR/PP approval code (on every asset)", "example": "PP-XXX-US-0000"},
        ],
    }


def _test_design(brand: str) -> dict:
    return {
        "approach": "2–3 subject-line / preheader variants per email; modular, reuse-first "
                    "(shared content blocks recombined per segment rather than net-new builds).",
        "rows": [
            {"test": "Subject line", "variants": "2–3 per send", "measure": "Open rate", "primary": True},
            {"test": "Preheader", "variants": "2–3 per send", "measure": "Open rate", "primary": False},
            {"test": "CTA / hero module", "variants": "2 per send", "measure": "Click-through rate", "primary": False},
            {"test": "Send time", "variants": "day/time cohorts", "measure": "Open rate", "primary": False},
        ],
        "note": "Modular reuse-first: win variants get promoted into the shared block library so "
                "learnings compound across sends instead of being one-off.",
    }


def build(project_id: str) -> dict:
    proj = pstore.get_project(project_id) or {}
    result = proj.get("result") or {}
    slots = ((proj.get("state") or {}).get("slots") or {})
    inferred = result.get("inferred_inputs") or {}

    brand = result.get("brand") or slots.get("brand") or ""
    therapy_area = result.get("therapy_area") or slots.get("therapy_area") or ""
    lifecycle_label = inferred.get("lifecycle_label") or slots.get("lifecycle_text") or ""
    lifecycle_key = slots.get("lifecycle_key") or _lifecycle_key(lifecycle_label)
    stage_label = inferred.get("stage_label") or "Aware"

    b = benchmarks.load()
    ct = b.get("channel_tactics", {})
    idx = float(((b.get("lifecycle_kpi_targets", {}) or {}).get(lifecycle_key, {}) or {}).get("index", 1.0))

    email_open = (ct.get("email_hcp_triggered", {}) or {}).get("open_rate_pct", 18.26)
    email_ctr = (ct.get("email_hcp_triggered", {}) or {}).get("ctr_pct", 3.0)
    rep_access = (ct.get("field_rep_detail", {}) or {}).get("hcp_access_rate_pct", 45.0)

    demo = _demographics()
    target_hcps = demo.get("total_hcps") or 1000
    impressions_target = target_hcps * _AVG_FREQUENCY

    # Funnel: stage-promotion signals for the priority journey stage.
    funnel = {
        "stage": stage_label,
        "note": f"Signals that promote a {stage_label.lower()} HCP to the next journey stage. "
                f"Bands = industry baseline × {lifecycle_key} lifecycle index ({idx}×).",
        "signals": [
            {"label": "Email open", "kind": "rate", **_band(email_open, idx),
             "note": "top-of-funnel engagement signal", "primary": False},
            {"label": "Site visit", "kind": "rate", **_band(email_ctr, idx),
             "note": "click-through to owned site (mid-funnel intent)", "primary": False},
            {"label": "First rep meeting accepted", "kind": "rate", **_band(rep_access, idx),
             "note": "primary stage-promotion signal", "primary": True},
        ],
    }

    # Delivery & engagement KPI cards.
    kpis = [
        {"label": "Impressions delivered", "kind": "volume",
         "value": impressions_target, "value_display": f"{impressions_target:,}",
         "sub": f"{target_hcps:,} target HCPs × ~{_AVG_FREQUENCY} avg frequency",
         "note": "reach/delivery target — volume, no rate band", "primary": False},
        {"label": "Click-through rate", "kind": "rate", **_band(email_ctr, idx),
         "sub": "email, triggered", "note": "engagement quality", "primary": False},
        {"label": "Unbranded content completion rate", "kind": "rate",
         "value_pct": 60.0, "low_pct": 55.0, "high_pct": 65.0, "band": "55–65%",
         "sub": "disease-state / MOA content", "note": "depth-of-engagement target (derived)", "primary": False},
        {"label": "Email open rate", "kind": "rate", **_band(email_open, idx),
         "sub": "triggered HCP email", "note": "reach into the inbox", "primary": True},
    ]

    return {
        "available": True,
        "brand": brand,
        "therapy_area": therapy_area,
        "lifecycle_label": lifecycle_label,
        "lifecycle_key": lifecycle_key,
        "stage_label": stage_label,
        "caveat": "Targets/benchmarks, not observed results — no live performance feed is "
                  "connected. Rate bands are industry baselines scaled by the lifecycle index; "
                  "replace with the brand's own numbers once one in-market period exists.",
        "funnel": funnel,
        "kpis": kpis,
        "demographics": demo,
        "tagging": _tagging_matrix(brand),
        "test_design": _test_design(brand),
    }


def summary_text(project_id: str) -> str:
    """Compact text digest of the insights payload, for grounding the Reporting agent."""
    d = build(project_id)
    lines = [f"Reporting insights for {d.get('brand') or 'the brand'} ({d.get('therapy_area') or 'n/a'}), "
             f"lifecycle {d.get('lifecycle_key')}, priority stage {d.get('stage_label')}."]
    lines.append("Stage-promotion funnel:")
    for s in d["funnel"]["signals"]:
        star = " [primary]" if s.get("primary") else ""
        lines.append(f"  - {s['label']}: target {s.get('band', s.get('value_pct'))}{star}")
    lines.append("Delivery & engagement KPIs:")
    for k in d["kpis"]:
        val = k.get("value_display") or k.get("band") or (f"{k.get('value_pct')}%" if k.get("value_pct") else "")
        lines.append(f"  - {k['label']}: {val} ({k.get('sub', '')})")
    demo = d["demographics"]
    if demo.get("available"):
        lines.append(f"HCP 360 panel: {demo['total_hcps']} HCPs.")
        if demo.get("by_specialty"):
            top = ", ".join(f"{r['value']} ({r['count']})" for r in demo["by_specialty"][:5])
            lines.append(f"  Top specialties: {top}")
        if demo.get("by_preferred_channel"):
            top = ", ".join(f"{r['value']} ({r['count']})" for r in demo["by_preferred_channel"][:5])
            lines.append(f"  Preferred channel: {top}")
    lines.append("Tagging: UTM matrix (utm_source/medium/campaign/content/term + job_code on every URL).")
    lines.append("Test design: 2-3 subject-line/preheader variants per email, modular reuse-first.")
    lines.append(d["caveat"])
    return "\n".join(lines)


if __name__ == "__main__":
    import json
    print(json.dumps(build("_demo_"), indent=2, default=str)[:2000])
