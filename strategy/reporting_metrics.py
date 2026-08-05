"""The rate model that turns HCP 360 panel facts into campaign metrics.

`hcp_panel_metrics` counts the real panel; this module converts those counts into the
percentages the Reporting dashboard shows, and it does so with one rule applied everywhere:

    cohort rate = industry benchmark x lifecycle index x (cohort affinity / panel affinity)

The benchmark and lifecycle index come from `config/omnichannel_benchmarks.json`; the lift
term is the filtered cohort's own measured affinity relative to the whole panel's. An
unfiltered view therefore lands exactly on the benchmark, and every filter moves the numbers
by exactly as much as the population it selected actually differs -- nothing is randomised,
and nothing is a static literal.

Volumes (audience, sends, delivered, opened, clicked) are the cohort's real HCP counts run
through those rates, so the funnel adds up against a population you can list by NPI.
"""
from __future__ import annotations

import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import benchmarks  # noqa: E402
import hcp_panel_metrics as panel  # noqa: E402

# Industry norms with no entry in the benchmark file (documented as such in the payload's
# caveat): healthcare-email delivery/unsubscribe baselines.
DELIVERY_BASE_PCT = 98.7
UNSUB_BASE_PCT = 0.18

# US state code -> name, so the choropleth can match the topology's `properties.name`.
STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan",
    "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota",
    "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee",
    "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "PR": "Puerto Rico",
}

# Campaign channel -> the panel affinity column that grounds it, and how it is presented.
# Labels stay short deliberately: they sit in a fixed column beside the bar, and a wrapped
# or ellipsed channel name is worse than a terse one.
CHANNEL_PRESENTATION = {
    "Email": {"label": "Email", "icon": "mail"},
    "Digital": {"label": "Web", "icon": "language"},
    "EHR": {"label": "EHR", "icon": "clinical_notes"},
    "Prog": {"label": "Peer progs", "icon": "diversity_3"},
    "Tele": {"label": "Rep tele", "icon": "call"},
}

# Preferred-content tag -> the asset shape a brand would actually ship for it.
_TAG_ASSET_TYPE = {
    "Clinical Trial Updates": "Email", "Efficacy Data": "Email", "Safety Profile": "Email",
    "MOA": "Interactive visual aid", "Biomarker Testing": "Landing page",
    "Treatment Guidelines": "Landing page", "Dosing & Administration": "Reference card",
    "Adverse Event Management": "Reference card", "Peer Perspectives": "Webinar",
    "Real World Evidence": "Webinar", "Access & Reimbursement": "Ebook",
    "Patient Support Programs": "Ebook",
}


def month_labels(months: int) -> list[str]:
    """`months` YYYY-MM labels ending with the current month, oldest first."""
    now = time.gmtime()
    labels, y, m = [], now.tm_year, now.tm_mon
    for _ in range(max(1, months)):
        labels.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return list(reversed(labels))


def anchors(lifecycle_key: str) -> dict:
    """Benchmark rates for this lifecycle stage -- the anchor every cohort rate scales from."""
    b = benchmarks.load()
    ct = b.get("channel_tactics", {}) or {}
    email = ct.get("email_hcp_triggered", {}) or {}
    idx = float(((b.get("lifecycle_kpi_targets", {}) or {}).get(lifecycle_key, {}) or {}).get("index", 1.0))
    return {
        "index": idx,
        "open_pct": float(email.get("open_rate_pct", 18.26)) * idx,
        "ctr_pct": float(email.get("ctr_pct", 3.0)) * idx,
        "ctor_pct": float(email.get("click_to_open_pct", 3.43)) * idx,
        "delivery_pct": DELIVERY_BASE_PCT,
        "unsubscribe_pct": UNSUB_BASE_PCT,
        "rep_access_pct": float((ct.get("field_rep_detail", {}) or {}).get("hcp_access_rate_pct", 45.0)),
    }


def _lift(cohort_affinity: dict, base_affinity: dict, channel: str) -> float:
    """The cohort's measured affinity for `channel` relative to the whole panel's."""
    base = base_affinity.get(channel) or 0.0
    if base <= 0:
        return 1.0
    return (cohort_affinity.get(channel) or 0.0) / base


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return round(min(high, max(low, value)), 2)


def rates_for(profile: dict, base: dict, anc: dict) -> dict:
    """Every percentage on the dashboard for one population, derived from its own affinity."""
    aff, base_aff = profile["affinity"], base["affinity"]
    email_lift = _lift(aff, base_aff, "Email")
    digital_lift = _lift(aff, base_aff, "Digital")
    # Deep engagement rides on the channels a brand converts through in the clinic.
    deep = ((aff.get("EHR") or 0) + (aff.get("Prog") or 0)) / 2

    delivery = _clamp(anc["delivery_pct"] * (profile["deliverable_pct"] / 100.0))
    open_pct = _clamp(anc["open_pct"] * email_lift)
    ctr = _clamp(anc["ctr_pct"] * digital_lift)
    return {
        "delivery": delivery,
        "bounce": _clamp(100.0 - delivery),
        "open": open_pct,
        "ctr": ctr,
        "ctor": _clamp((ctr / open_pct * 100.0) if open_pct else 0.0),
        # Disengaged cohorts unsubscribe more: the inverse of the same measured lift.
        "unsubscribe": _clamp(anc["unsubscribe_pct"] / email_lift if email_lift else anc["unsubscribe_pct"], 0, 5),
        "conversion": _clamp(ctr * deep),
        # A 0-100 composite of the cohort's five measured channel affinities.
        "engagement_score": round(100 * sum(aff.values()) / max(1, len(aff)), 1),
    }


def volumes_for(profile: dict, rates: dict) -> dict:
    """The funnel counts for one population: real HCPs run through its own rates."""
    audience = profile["size"]
    delivered = round(audience * rates["delivery"] / 100)
    opened = round(delivered * rates["open"] / 100)
    clicked = round(delivered * rates["ctr"] / 100)
    converted = round(delivered * rates["conversion"] / 100)
    return {"audience": audience, "sent": audience, "delivered": delivered,
            "opened": opened, "clicked": clicked, "converted": converted,
            "unsubscribed": round(delivered * rates["unsubscribe"] / 100)}


# key -> (label, unit, higher_is_better, chart series description)
METRIC_SPEC = [
    ("delivery", "Delivery rate", "%", True, "Share of the wave's audience with a deliverable panel record."),
    ("open", "Open rate", "%", True, "Benchmark open rate scaled by the wave's measured email affinity."),
    ("ctr", "Click rate (CTR)", "%", True, "Benchmark CTR scaled by the wave's measured digital affinity."),
    ("ctor", "Click-to-open (CTOR)", "%", True, "Clicks as a share of opens for the wave."),
    ("conversion", "Conversion rate", "%", True, "Clicks carried through to deep engagement, indexed on EHR/programme affinity."),
    ("unsubscribe", "Unsubscribe rate", "%", False, "Inverse of the wave's measured email affinity."),
    ("bounce", "Bounce rate", "%", False, "The non-deliverable remainder of the wave."),
    ("engagement_score", "Engagement score", "index", True, "Composite of the wave's five measured channel affinities (0-100)."),
    ("audience", "HCPs reached", "count", True, "Panel members in the wave with a deliverable record."),
    ("opened", "Unique opens", "count", True, "Wave delivered volume x its own open rate."),
    ("clicked", "Unique clicks", "count", True, "Wave delivered volume x its own click rate."),
]
_VOLUME_KEYS = {"audience", "opened", "clicked"}


def _status(key: str, value: float, benchmark: float | None, higher_is_better: bool) -> str:
    """good / watch / risk against the benchmark. Volume metrics have no band."""
    if benchmark is None or benchmark <= 0:
        return "neutral"
    ratio = value / benchmark
    if not higher_is_better:
        ratio = benchmark / value if value else 2.0
    if ratio >= 1.0:
        return "good"
    return "watch" if ratio >= 0.85 else "risk"


def build_metrics(cohort: dict, base: dict, anc: dict, waves: list[dict], labels: list[str]) -> list[dict]:
    """The metric registry: one entry per selectable metric, each carrying its current value,
    its benchmark, its month-over-month delta and its own monthly series.

    This one list drives the KPI cards, the metric drop-down and the trend chart -- the chart
    renders exactly the metric selected, never all of them at once.
    """
    cohort_rates = rates_for(cohort, base, anc)
    cohort_volumes = volumes_for(cohort, cohort_rates)
    base_rates = rates_for(base, base, anc)  # benchmark line: the unfiltered panel

    series: list[dict] = []
    for wave, label in zip(waves, labels):
        w_rates = rates_for(wave, base, anc)
        series.append({"month": label, **w_rates, **volumes_for(wave, w_rates)})

    metrics = []
    for key, label, unit, higher_is_better, description in METRIC_SPEC:
        monthly = [{"month": row["month"], "value": row[key]} for row in series]
        current = cohort_volumes[key] if key in _VOLUME_KEYS else cohort_rates[key]
        if key in _VOLUME_KEYS:
            benchmark = None
        elif key == "engagement_score":
            benchmark = base_rates["engagement_score"]
        else:
            benchmark = base_rates[key]
        last, prev = (monthly[-1]["value"], monthly[-2]["value"]) if len(monthly) > 1 else (current, current)
        delta = round(last - prev, 2)
        metrics.append({
            "key": key,
            "label": label,
            "unit": unit,
            "value": current,
            "benchmark": None if benchmark is None else round(benchmark, 2),
            "band": None if benchmark is None else [round(benchmark * 0.85, 2), round(benchmark * 1.15, 2)],
            "delta": delta,
            "delta_unit": "pp" if unit == "%" else ("pts" if unit == "index" else "count"),
            "direction": "up" if delta > 0 else ("down" if delta < 0 else "flat"),
            "higher_is_better": higher_is_better,
            "status": _status(key, current, benchmark, higher_is_better),
            "description": description,
            "monthly": monthly,
        })
    return metrics


def build_funnel(cohort: dict, rates: dict) -> dict:
    """Delivered -> opened -> clicked -> converted, as real HCP counts with step conversion."""
    v = volumes_for(cohort, rates)
    steps = [("Audience", v["audience"]), ("Delivered", v["delivered"]),
             ("Opened", v["opened"]), ("Clicked", v["clicked"]), ("Converted", v["converted"])]
    top = max(1, v["audience"])
    out = []
    for i, (label, count) in enumerate(steps):
        prior = steps[i - 1][1] if i else count
        out.append({"stage": label, "count": count,
                    "pct_of_audience": round(100 * count / top, 2),
                    "pct_of_prior": round(100 * count / prior, 2) if prior else 0.0})
    return {"steps": out, "volumes": v}


def build_journey(volumes: dict) -> list[dict]:
    """The engagement-flow view of the same counts: each decision point and both branches."""
    delivered, opened, clicked = volumes["delivered"], volumes["opened"], volumes["clicked"]
    converted = volumes["converted"]
    def pct(part: int, whole: int) -> float:
        return round(100 * part / whole, 1) if whole else 0.0
    return [
        {"id": "send", "label": "Wave 1 email", "count": volumes["sent"], "pct": 100.0, "kind": "send"},
        {"id": "delivered", "label": "Delivered", "count": delivered, "pct": pct(delivered, volumes["sent"]), "kind": "step"},
        {"id": "opened", "label": "Opened", "count": opened, "pct": pct(opened, delivered), "kind": "decision",
         "branch": {"label": "No open", "count": delivered - opened, "pct": pct(delivered - opened, delivered)}},
        {"id": "clicked", "label": "Clicked", "count": clicked, "pct": pct(clicked, opened), "kind": "decision",
         "branch": {"label": "No click", "count": opened - clicked, "pct": pct(opened - clicked, opened)}},
        {"id": "converted", "label": "Deep engagement", "count": converted, "pct": pct(converted, clicked), "kind": "outcome",
         "branch": {"label": "Re-engage", "count": max(0, clicked - converted), "pct": pct(max(0, clicked - converted), clicked)}},
    ]


def build_channels(filters: dict, base: dict, anc: dict) -> list[dict]:
    """One row per channel: how many of the cohort prefer it (real counts) and the engagement
    rate its measured affinity implies."""
    cohort = panel.cohort_profile(filters)
    preferred = {r["value"]: r["count"] for r in panel.dimension_counts("channel", filters)}
    total = max(1, cohort["size"])
    email_base = base["affinity"].get("Email") or 1.0
    rows = []
    for key, meta in CHANNEL_PRESENTATION.items():
        affinity = cohort["affinity"].get(key) or 0.0
        rows.append({
            "channel": key,
            "label": meta["label"],
            "icon": meta["icon"],
            "hcps": preferred.get(key, 0),
            "preferred_pct": round(100 * preferred.get(key, 0) / total, 1),
            "affinity": round(affinity, 4),
            "engagement_pct": _clamp(anc["open_pct"] * (affinity / email_base if email_base else 1.0)),
        })
    return sorted(rows, key=lambda r: -r["engagement_pct"])


def build_geo(filters: dict, base: dict, anc: dict, limit: int = 60) -> list[dict]:
    """Per-state HCP counts with that state's own open/click rates."""
    base_aff = base["affinity"]
    rows = []
    for r in panel.dimension_counts("state", filters, limit=limit):
        code = (r["value"] or "").strip().upper()
        email_lift = (r["email_affinity"] / base_aff["Email"]) if base_aff.get("Email") else 1.0
        digital_lift = (r["digital_affinity"] / base_aff["Digital"]) if base_aff.get("Digital") else 1.0
        rows.append({
            "state_code": code,
            "state": STATE_NAMES.get(code, code),
            "hcps": r["count"],
            "open_pct": _clamp(anc["open_pct"] * email_lift),
            "ctr_pct": _clamp(anc["ctr_pct"] * digital_lift),
            "index": round(100 * email_lift, 1),
        })
    return rows


def build_assets(filters: dict, base: dict, anc: dict, brand: str, limit: int = 6) -> list[dict]:
    """Top-performing assets, ranked by the cohort's own preferred-content tags."""
    base_aff = base["affinity"]
    rows = []
    for tag_row in panel.content_demand(filters, limit=limit):
        tag = tag_row["tag"]
        email_lift = (tag_row["email_affinity"] / base_aff["Email"]) if base_aff.get("Email") else 1.0
        digital_lift = (tag_row["digital_affinity"] / base_aff["Digital"]) if base_aff.get("Digital") else 1.0
        open_pct = _clamp(anc["open_pct"] * email_lift)
        ctr = _clamp(anc["ctr_pct"] * digital_lift)
        rows.append({
            "name": f"{brand or 'Brand'} — {tag}",
            "tag": tag,
            "type": _TAG_ASSET_TYPE.get(tag, "Email"),
            "audience": tag_row["count"],
            "open_pct": open_pct,
            "ctr_pct": ctr,
            "conversion_pct": _clamp(ctr * ((base_aff.get("EHR") or 0) + (base_aff.get("Prog") or 0)) / 2),
        })
    return sorted(rows, key=lambda r: -r["open_pct"])
