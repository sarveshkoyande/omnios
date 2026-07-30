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

import hashlib
import pathlib
import sys
import time

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


# Industry-standard constants not present in config/omnichannel_benchmarks.json (no cited
# source for these three, unlike open/CTR/CTOR which come from the researched benchmark
# file) -- reasonable healthcare-email norms, clearly caveated below as illustrative.
_DELIVERY_RATE_PCT = 98.7
_BOUNCE_RATE_PCT = 1.3
_UNSUBSCRIBE_RATE_PCT = 0.18

_EMAIL_METRIC_ORDER = [
    ("delivery", "E-delivery rate"),
    ("open", "Email open rate"),
    ("ctr", "Click-through rate (CTR)"),
    ("ctor", "Click-to-open rate (CTOR)"),
    ("bounce", "Bounce rate"),
    ("unsubscribe", "Unsubscribe rate"),
]


def _stable_wave(key: str, i: int, spread: float) -> float:
    """Deterministic -spread..+spread wobble, stable across reloads (seeded by key+i), so a
    month-over-month trend / specialty split reads as a real series instead of visibly
    re-randomizing on every request."""
    h = int(hashlib.md5(f"{key}:{i}".encode()).hexdigest(), 16)
    return ((h % 2000) / 1000.0 - 1.0) * spread


def _month_labels(months: int) -> list[str]:
    now = time.gmtime()
    labels = []
    y, m = now.tm_year, now.tm_mon
    for _ in range(months):
        labels.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return list(reversed(labels))


def _email_metrics(idx: float, ct: dict, specialty: str | None, months: int) -> dict:
    """E-delivery / open / CTR / CTOR / bounce / unsubscribe, as an exact current-period
    percentage plus a monthly trend, for the requested specialty filter. No live send data is
    connected -- values are industry-baseline targets (delivery/bounce/unsubscribe) or the
    researched channel_tactics benchmarks (open/CTR/CTOR), scaled by the lifecycle index and a
    stable per-specialty variation; NOT observed campaign performance."""
    email = (ct.get("email_hcp_triggered", {}) or {})
    base = {
        "delivery": _DELIVERY_RATE_PCT,
        "open": float(email.get("open_rate_pct", 18.26)) * idx,
        "ctr": float(email.get("ctr_pct", 3.0)) * idx,
        "ctor": float(email.get("click_to_open_pct", 3.43)) * idx,
        "bounce": _BOUNCE_RATE_PCT,
        "unsubscribe": _UNSUBSCRIBE_RATE_PCT,
    }
    spec_key = (specialty or "all").strip().lower()
    spec_shift = _stable_wave(f"spec:{spec_key}", 0, 0.12) if spec_key != "all" else 0.0

    def _clamp_pct(v: float) -> float:
        return round(min(100.0, max(0.0, v)), 2)

    metrics = []
    month_labels = _month_labels(months)
    for key, label in _EMAIL_METRIC_ORDER:
        current = _clamp_pct(base[key] * (1 + spec_shift))
        monthly = []
        for i, m_label in enumerate(month_labels):
            wobble = _stable_wave(f"{spec_key}:{key}", i, 0.08)
            monthly.append({"month": m_label, "value_pct": _clamp_pct(current * (1 + wobble))})
        metrics.append({
            "key": key,
            "label": label,
            "value_pct": round(current, 2),
            "monthly": monthly,
        })

    return {
        "note": "E-delivery/bounce/unsubscribe are industry-baseline targets; open/CTR/CTOR "
                "are the researched channel_tactics benchmarks (config/omnichannel_benchmarks.json) "
                "scaled by the lifecycle index. The monthly trend and specialty split are an "
                "illustrative simulated series, not observed send data -- no live performance "
                "feed is connected yet. Replace with real ESP/Veeva send reports once available.",
        "specialty": specialty or "All specialties",
        "months": month_labels,
        "metrics": metrics,
    }


_DOW = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
_HOUR_BUCKETS = ["3 AM", "6 AM", "9 AM", "12 PM", "3 PM", "6 PM", "9 PM", "12 AM"]
# Relative weekday/weekend and hour-of-day weighting -- HCPs open email in short bursts
# around clinic downtime (mid-morning, lunch), weekdays >> weekend, matching the shape of
# real triggered-email open-time distributions (not a flat/random spread).
_HOUR_WEIGHT = [0.02, 0.35, 1.0, 1.9, 0.55, 0.12, 0.09, 0.07]
_DOW_WEIGHT = [0.05, 1.0, 1.35, 1.15, 1.5, 1.7, 0.06]

# A representative subset of US states (not all 50) for the CTR-by-state ranked list.
_STATES = [
    "California", "Texas", "New York", "Florida", "Pennsylvania", "Illinois", "Ohio",
    "Georgia", "North Carolina", "Michigan", "New Jersey", "Virginia", "Massachusetts",
    "Arizona", "Tennessee", "Indiana", "Missouri", "Maryland", "Wisconsin", "Colorado",
]

_SEGMENT_BUCKETS = ["High Awareness", "Growing Awareness", "Low Awareness"]

_SUBJECT_LINE_TEMPLATES = [
    ("Explore clinical trial data of {brand}", "A/B Test — Not Concluded", "FW"),
    ("Explore {brand} videos on clinical data", "A/B Winner — B", "FW"),
    ("New patient support resources for {brand}", "A/B — B", "FW"),
]


def _opens_by_time(spec_key: str, open_rate_pct: float) -> dict:
    """Day-of-week x hour-of-day open-rate heatmap. Illustrative shape (weekday/mid-morning
    peak) scaled to roughly sum to the metric's own open rate -- not observed send-time data."""
    rows = []
    for d, dow in enumerate(_DOW):
        cells = []
        for h, hour in enumerate(_HOUR_BUCKETS):
            base = open_rate_pct * _DOW_WEIGHT[d] * _HOUR_WEIGHT[h] / 12.0
            wobble = _stable_wave(f"{spec_key}:opens:{dow}", h, 0.25)
            cells.append(round(max(0.0, base * (1 + wobble)), 2))
        rows.append({"day": dow, "cells": cells})
    return {"hours": _HOUR_BUCKETS, "rows": rows}


def _ctr_by_state(spec_key: str, ctr_pct: float) -> list[dict]:
    out = []
    for i, state in enumerate(_STATES):
        wobble = _stable_wave(f"{spec_key}:state", i, 0.9)  # wide spread -- state volumes vary a lot
        out.append({"state": state, "ctr_pct": round(max(0.0, ctr_pct * (1 + wobble) * 1.8), 2)})
    out.sort(key=lambda r: -r["ctr_pct"])
    return out


def _delivered_by_segment(spec_key: str) -> list[dict]:
    weights = {b: 20 + abs(_stable_wave(f"{spec_key}:segdist", i, 30)) for i, b in enumerate(_SEGMENT_BUCKETS)}
    total = sum(weights.values()) or 1.0
    return [{"segment": b, "pct": round(w / total * 100, 2)} for b, w in weights.items()]


def _subject_line_performance(brand: str, spec_key: str, target_hcps: int, email: dict, idx: float) -> list[dict]:
    open_rate = float(email.get("open_rate_pct", 18.26)) * idx
    ctr = float(email.get("ctr_pct", 3.0)) * idx
    rows = []
    for i, (tmpl, ab_testing, wave_type) in enumerate(_SUBJECT_LINE_TEMPLATES):
        sent = max(20, int(target_hcps * (0.08 + abs(_stable_wave(f"{spec_key}:sl:sent", i, 0.05)))))
        deliveries = int(sent * (_DELIVERY_RATE_PCT / 100.0))
        row_open_rate = round(max(0.0, open_rate * (1 + _stable_wave(f"{spec_key}:sl:open", i, 0.4))), 1)
        row_ctr = round(max(0.0, ctr * (1 + _stable_wave(f"{spec_key}:sl:ctr", i, 0.5))), 1)
        opens = int(deliveries * row_open_rate / 100.0)
        clicks = int(opens * row_ctr / max(row_open_rate, 0.1))
        rows.append({
            "asset_name": f"{brand or 'Brand'} — Wave {i + 1}",
            "segment": "High Awareness" if i >= 2 else "",
            "subject_line": tmpl.format(brand=brand or "the brand"),
            "ab_testing": ab_testing,
            "wave_type": wave_type,
            "emails_sent": sent,
            "deliveries": deliveries,
            "opens": opens,
            "clicks": clicks,
            "open_rate_pct": row_open_rate,
            "ctr_pct": row_ctr,
        })
    return rows


def _email_deepdive(brand: str, specialty: str | None, idx: float, ct: dict, target_hcps: int) -> dict:
    """The four extra Email metrics widgets: opens-by-time-of-day heatmap, CTR-by-state ranked
    list, delivered-by-segment split, and per-subject-line performance table + reach tiles.
    Same illustrative-simulated-series caveat as _email_metrics -- no live ESP feed connected."""
    spec_key = (specialty or "all").strip().lower()
    email = ct.get("email_hcp_triggered", {}) or {}
    open_rate = float(email.get("open_rate_pct", 18.26)) * idx
    ctr = float(email.get("ctr_pct", 3.0)) * idx

    subject_lines = _subject_line_performance(brand, spec_key, target_hcps, email, idx)
    total_deliveries = sum(r["deliveries"] for r in subject_lines) or 1
    total_opens = sum(r["opens"] for r in subject_lines)
    total_clicks = sum(r["clicks"] for r in subject_lines)

    return {
        "opens_by_time": _opens_by_time(spec_key, open_rate),
        "ctr_by_state": _ctr_by_state(spec_key, ctr),
        "delivered_by_segment": _delivered_by_segment(spec_key),
        "subject_lines": subject_lines,
        "tiles": {
            "unique_hcp_reached": total_deliveries,
            "unique_hcp_engaged": total_opens,
            "unique_hcp_deep_engaged": total_clicks,
            "unique_subject_lines": len(subject_lines),
        },
    }


def build(project_id: str, specialty: str | None = None, months: int = 6) -> dict:
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
    months_clamped = max(1, min(months, 24))
    email_metrics = _email_metrics(idx, ct, specialty, months_clamped)
    email_deepdive = _email_deepdive(brand, specialty, idx, ct, target_hcps)

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
        "email_metrics": email_metrics,
        "email_deepdive": email_deepdive,
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
