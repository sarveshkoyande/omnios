"""Reporting & Insights payload for the Reporting tab (and the Reporting agent's grounding).

Everything in this payload is counted out of the real HCP 360 panel for the exact filter
combination the user picked, then scaled by the researched benchmarks:

  * `hcp_panel_metrics`  -- counts the cohort (sizes, affinities, send windows, content
                            demand, per-state and per-segment breakdowns) straight from
                            hcp_360.db. Nothing there is generated.
  * `reporting_metrics`  -- turns those counts into rates with one rule:
                            benchmark x lifecycle index x (cohort affinity / panel affinity),
                            so an unfiltered view sits on the benchmark and every filter moves
                            the numbers by exactly what that population measures.
  * this module          -- assembles the dashboard: metric registry (which drives both the
                            KPI cards and the single-metric trend chart), funnel, journey,
                            channel/geo/asset breakdowns, the derived insight feed, and the
                            plan deliverables (UTM matrix, test design).

Caveat that travels with the payload: the panel is synthetic reference data and no live ESP
feed is connected, so these are grounded targets, not observed sends.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import hcp_panel_metrics as panel  # noqa: E402
import projects as pstore  # noqa: E402
import reporting_metrics as rmx  # noqa: E402

_LIFECYCLE_KEY = {
    "launch": "launch", "growth": "growth", "mature": "mature",
    "loe": "loe", "defend": "loe", "decline": "loe", "exclusivity": "loe",
}
# The six metrics the KPI rail shows by default; the drop-down offers the full registry.
HEADLINE_KEYS = ["delivery", "open", "ctr", "conversion", "engagement_score", "unsubscribe"]


def _lifecycle_key(label: str, fallback: str = "growth") -> str:
    low = (label or "").strip().lower()
    for frag, key in _LIFECYCLE_KEY.items():
        if frag in low:
            return key
    return fallback


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


def _test_design(brand: str, cohort_size: int) -> dict:
    """A/B design sized against the real cohort — variant cells are that cohort split."""
    cell = max(1, cohort_size // 2)
    return {
        "approach": "2–3 subject-line / preheader variants per email; modular, reuse-first "
                    "(shared content blocks recombined per segment rather than net-new builds).",
        "active": 4,
        "rows": [
            {"test": "Subject line", "variants": "2–3 per send", "measure": "Open rate",
             "cell_size": cell, "primary": True},
            {"test": "Preheader", "variants": "2–3 per send", "measure": "Open rate",
             "cell_size": cell, "primary": False},
            {"test": "CTA / hero module", "variants": "2 per send", "measure": "Click-through rate",
             "cell_size": cell, "primary": False},
            {"test": "Send time", "variants": "day/session cohorts from the panel's own preferences",
             "measure": "Open rate", "cell_size": max(1, cohort_size // 4), "primary": False},
        ],
        "note": f"Cell sizes are the live cohort ({cohort_size:,} HCPs) split evenly. Win variants "
                "get promoted into the shared block library so learnings compound across sends.",
    }


def _top_window(windows: dict) -> dict | None:
    """The panel's single most-preferred (day, session) email window in this cohort."""
    best = None
    for row in windows.get("rows", []):
        for i, share in enumerate(row["cells"]):
            if best is None or share > best["share_pct"]:
                best = {"day": row["day"], "session": windows["sessions"][i],
                        "share_pct": share, "hcps": row["counts"][i]}
    return best


def _insights(cohort, base, metrics, channels, geo, windows, assets, segments) -> list[dict]:
    """The Reporting agent's feed: recommendations, anomalies and wins, each derived from a
    specific panel fact so the number in the card can always be traced back to a query."""
    out: list[dict] = []
    by_key = {m["key"]: m for m in metrics}

    window = _top_window(windows)
    if window and window["share_pct"] > 0:
        avg = 100 / max(1, sum(len(r["cells"]) for r in windows["rows"]))
        out.append({
            "id": "send-window", "kind": "recommendation", "severity": "info",
            "title": f"Send into {window['day']} {window['session'].lower()}",
            "detail": f"{window['share_pct']}% of this cohort ({window['hcps']:,} HCPs) name it their "
                      f"most-preferred email window — {round(window['share_pct'] / avg, 1)}× the average slot.",
            "action": "Move wave 1 of the flight into this window and hold the rest as the control.",
            "evidence": "global_day_time_preference_data",
        })

    risk = [m for m in metrics if m["status"] == "risk" and m["benchmark"]]
    for m in risk[:2]:
        out.append({
            "id": f"below-benchmark-{m['key']}", "kind": "anomaly", "severity": "warning",
            "title": f"{m['label']} is under benchmark",
            "detail": f"{m['value']}{'%' if m['unit'] == '%' else ''} against a {m['benchmark']}% "
                      f"benchmark for this lifecycle stage.",
            "action": "Re-check targeting depth before adding volume — the audience mix is the driver.",
            "evidence": "omnichannel_benchmarks.json × cohort affinity",
            "metric_key": m["key"],
        })

    if channels:
        best, worst = channels[0], channels[-1]
        under_used = min(channels, key=lambda c: c["preferred_pct"] / max(c["affinity"], 0.01))
        out.append({
            "id": "channel-mix", "kind": "recommendation", "severity": "info",
            "title": f"{under_used['label']} is under-weighted for its affinity",
            "detail": f"Affinity {round(under_used['affinity'] * 100)}/100 but only "
                      f"{under_used['preferred_pct']}% of the cohort ({under_used['hcps']:,} HCPs) "
                      f"name it their preferred channel. {best['label']} leads on engagement at "
                      f"{best['engagement_pct']}%, {worst['label']} trails at {worst['engagement_pct']}%.",
            "action": f"Shift a test cell of the {worst['label'].lower()} budget into {under_used['label'].lower()}.",
            "evidence": "global_channel_affinity_and_preference",
        })

    sized = [g for g in geo if g["hcps"] >= 20]
    if len(sized) >= 2:
        low = min(sized, key=lambda g: g["index"])
        high = max(sized, key=lambda g: g["index"])
        out.append({
            "id": "geo-spread", "kind": "anomaly", "severity": "warning" if low["index"] < 92 else "info",
            "title": f"{low['state']} runs {round(high['index'] - low['index'])} points behind {high['state']}",
            "detail": f"{low['state']}: {low['hcps']:,} HCPs at {low['open_pct']}% open. "
                      f"{high['state']}: {high['hcps']:,} HCPs at {high['open_pct']}%.",
            "action": f"Route {low['state']} through the field/EHR mix instead of adding email frequency.",
            "evidence": "hcp_demographic_data__dlm × channel affinity",
        })

    if assets:
        top = assets[0]
        out.append({
            "id": "content-demand", "kind": "recommendation", "severity": "info",
            "title": f"{top['tag']} is the cohort's top content demand",
            "detail": f"{top['audience']:,} HCPs name it their most-preferred content tag; the matching "
                      f"{top['type'].lower()} models {top['open_pct']}% open / {top['ctr_pct']}% click.",
            "action": "Lead the flight with this module and reuse it across segments before building net-new.",
            "evidence": "global_content_affinity_score_data",
        })

    if segments:
        lead = segments[0]
        share = round(100 * lead["count"] / max(1, cohort["size"]), 1)
        out.append({
            "id": "segment-concentration", "kind": "win" if share < 55 else "anomaly",
            "severity": "positive" if share < 55 else "warning",
            "title": f"{lead['value']} carries {share}% of the cohort",
            "detail": f"{lead['count']:,} of {cohort['size']:,} HCPs, engagement affinity "
                      f"{round(lead['email_affinity'] * 100)}/100.",
            "action": "Keep a segment-level read on every KPI — a single segment moving will move the headline.",
            "evidence": "tbl_tl_data__dlm",
        })

    mover = max(metrics, key=lambda m: abs(m["delta"]) if m["unit"] == "%" else 0)
    if abs(mover["delta"]) > 0:
        good = (mover["delta"] > 0) == mover["higher_is_better"]
        out.append({
            "id": "trend-mover", "kind": "win" if good else "anomaly",
            "severity": "positive" if good else "warning",
            "title": f"{mover['label']} moved {abs(mover['delta'])}pp month-over-month",
            "detail": f"Latest wave {mover['monthly'][-1]['value']}% vs {mover['monthly'][-2]['value']}% "
                      f"the month before." if len(mover["monthly"]) > 1 else "Single period in view.",
            "action": "Open the trend chart on this metric to see which wave drove it.",
            "evidence": "wave rotation over the panel",
            "metric_key": mover["key"],
        })

    if cohort["deliverable_pct"] < 100:
        out.append({
            "id": "deliverability", "kind": "anomaly", "severity": "critical",
            "title": f"{round(100 - cohort['deliverable_pct'], 1)}% of the cohort has no deliverable record",
            "detail": f"{cohort['size'] - cohort['with_email']:,} HCPs cannot be reached by email at all.",
            "action": "Route them to field/EHR and open a data-quality ticket on the panel records.",
            "evidence": "hcp_demographic_data__dlm.email__c",
        })

    # Only worth a card when there is actual headroom: on an unfiltered view the cohort *is*
    # the panel, so the lift is 0 by construction and "0.0pp above benchmark" says nothing.
    open_m = by_key.get("open")
    headroom = round(open_m["value"] - (open_m["benchmark"] or 0), 2) if open_m else 0
    if open_m and open_m["status"] == "good" and headroom >= 0.3:
        out.append({
            "id": "open-strength", "kind": "win", "severity": "positive",
            "title": f"Open rate is running {headroom}pp above benchmark",
            "detail": f"{open_m['value']}% against {open_m['benchmark']}% — the cohort's measured email "
                      f"affinity is carrying it.",
            "action": "Bank the headroom in frequency, not in subject-line testing.",
            "evidence": "cohort affinity lift",
            "metric_key": "open",
        })
    return out


def _optimizations(windows, channels, geo, metrics, cohort) -> list[dict]:
    """Ranked optimisation opportunities with the panel fact that sizes each one."""
    out = []
    window = _top_window(windows)
    if window:
        out.append({"title": f"Concentrate wave 1 into {window['day']} {window['session'].lower()}",
                    "impact": "High", "metric": f"{window['hcps']:,} HCPs in window",
                    "detail": "The cohort's own most-preferred email window."})
    if channels:
        under = min(channels, key=lambda c: c["preferred_pct"] / max(c["affinity"], 0.01))
        out.append({"title": f"Add a {under['label'].lower()} cell to the flight",
                    "impact": "High", "metric": f"affinity {round(under['affinity'] * 100)}/100",
                    "detail": f"Only {under['preferred_pct']}% of the cohort is served there today."})
    weak = [g for g in geo if g["hcps"] >= 20 and g["index"] < 96][:2]
    for g in weak:
        out.append({"title": f"Re-mix {g['state']} away from email-only",
                    "impact": "Medium", "metric": f"index {g['index']}",
                    "detail": f"{g['hcps']:,} HCPs running below the cohort's engagement index."})
    for m in [m for m in metrics if m["status"] == "watch"][:2]:
        out.append({"title": f"Close the gap on {m['label'].lower()}",
                    "impact": "Medium", "metric": f"{m['value']}% vs {m['benchmark']}%",
                    "detail": m["description"]})
    if cohort["deliverable_pct"] < 100:
        out.append({"title": "Repair non-deliverable panel records", "impact": "High",
                    "metric": f"{cohort['size'] - cohort['with_email']:,} HCPs",
                    "detail": "Unreachable by email until the record is fixed."})
    return out


def _scorecard(metrics: list[dict]) -> dict:
    tracked = [m for m in metrics if m["benchmark"] is not None]
    on_track = [m for m in tracked if m["status"] == "good"]
    return {
        "on_track": len(on_track), "tracked": len(tracked),
        "rows": [{"label": m["label"], "value": m["value"], "unit": m["unit"],
                  "benchmark": m["benchmark"], "status": m["status"], "key": m["key"]}
                 for m in tracked],
    }


def _framework(cohort: dict, metrics: list[dict], tagging: dict) -> dict:
    """Measurement-framework coverage: which reads have a grounded source wired today."""
    rows = [
        {"area": "Audience sizing", "source": "hcp_360 demographic panel", "status": "live",
         "detail": f"{cohort['size']:,} HCPs in the current cohort"},
        {"area": "Channel affinity", "source": "global_channel_affinity_and_preference", "status": "live",
         "detail": "Per-HCP 0–10 scores across five channels"},
        {"area": "Send-time optimisation", "source": "global_day_time_preference_data", "status": "live",
         "detail": "Day × session preference per HCP"},
        {"area": "Content demand", "source": "global_content_affinity_score_data", "status": "live",
         "detail": "Top-3 preferred content tags per HCP"},
        {"area": "Segment / writer status", "source": "tbl_tl_data__dlm", "status": "live",
         "detail": "Target-list segment, persona and TRx tier"},
        {"area": "Rate benchmarks", "source": "config/omnichannel_benchmarks.json", "status": "live",
         "detail": "Cited industry baselines scaled by the lifecycle index"},
        {"area": "Link tagging", "source": "UTM matrix (this tab)", "status": "live",
         "detail": f"{len(tagging['rows'])} parameters enforced at asset build"},
        {"area": "Observed sends", "source": "ESP / Veeva send reports", "status": "pending",
         "detail": "No live performance feed connected — rates are grounded targets"},
    ]
    live = sum(1 for r in rows if r["status"] == "live")
    return {"rows": rows, "coverage_pct": round(100 * live / len(rows)),
            "live": live, "total": len(rows),
            "note": f"{len(metrics)} metrics are derived from the live sources above."}


def _learnings(cohort, channels, windows, assets, segments) -> list[dict]:
    out = []
    if channels:
        out.append({"title": "Affinity, not creative, is moving the rates",
                    "detail": f"The cohort's measured channel affinity spread runs from "
                              f"{round(min(c['affinity'] for c in channels) * 100)} to "
                              f"{round(max(c['affinity'] for c in channels) * 100)} out of 100."})
    window = _top_window(windows)
    if window:
        out.append({"title": "Send windows are concentrated, not flat",
                    "detail": f"{window['day']} {window['session'].lower()} alone holds "
                              f"{window['share_pct']}% of the cohort's stated preference."})
    if assets:
        out.append({"title": "Content demand is broad",
                    "detail": f"The top tag ({assets[0]['tag']}) covers {assets[0]['audience']:,} HCPs — "
                              f"modular reuse beats a single hero asset."})
    if segments:
        out.append({"title": "Segments read differently on the same send",
                    "detail": ", ".join(f"{s['value']} {round(s['email_affinity'] * 100)}/100"
                                        for s in segments[:3]) + " on email affinity."})
    out.append({"title": "Targets, not results",
                "detail": "Every rate here is a benchmark scaled by a measured cohort — replace it "
                          "with the brand's own numbers after one in-market period."})
    return out


def build(project_id: str, specialty: str | None = None, months: int = 6,
          filters: dict | None = None) -> dict:
    """Assemble the Reporting tab payload for `project_id` under the given filters.

    `filters` accepts any of hcp_panel_metrics.DIMENSIONS (specialty / state / segment /
    channel / brand); the legacy `specialty` kwarg folds into it."""
    applied = panel.clean_filters({**(filters or {}), **({"specialty": specialty} if specialty else {})})

    proj = pstore.get_project(project_id) or {}
    result = proj.get("result") or {}
    slots = ((proj.get("state") or {}).get("slots") or {})
    inferred = result.get("inferred_inputs") or {}

    brand = result.get("brand") or slots.get("brand") or ""
    therapy_area = result.get("therapy_area") or slots.get("therapy_area") or ""
    lifecycle_label = inferred.get("lifecycle_label") or slots.get("lifecycle_text") or ""
    lifecycle_key = slots.get("lifecycle_key") or _lifecycle_key(lifecycle_label)
    stage_label = inferred.get("stage_label") or "Aware"

    months = max(1, min(int(months or 6), 24))
    anc = rmx.anchors(lifecycle_key)
    base = panel.panel_baseline()
    cohort = panel.cohort_profile(applied)

    if cohort["size"] == 0:  # a filter combination with nobody in it
        return {"available": False, "brand": brand, "therapy_area": therapy_area,
                "filters": {"applied": applied, "facets": panel.facets({}), "months": months,
                            "month_labels": rmx.month_labels(months)},
                "message": "No HCPs in the panel match this filter combination."}

    labels = rmx.month_labels(months)
    waves = panel.wave_profile(applied, months)
    metrics = rmx.build_metrics(cohort, base, anc, waves, labels)
    rates = rmx.rates_for(cohort, base, anc)
    funnel = rmx.build_funnel(cohort, rates)
    channels = rmx.build_channels(applied, base, anc)
    geo = rmx.build_geo(applied, base, anc)
    assets = rmx.build_assets(applied, base, anc, brand)
    windows = panel.send_windows(applied)
    segments = panel.dimension_counts("segment", applied)
    specialties = panel.dimension_counts("specialty", applied, limit=12)
    tagging = _tagging_matrix(brand)
    trx = panel.prescribing_volume(applied)

    return {
        "available": True,
        "brand": brand,
        "therapy_area": therapy_area,
        "lifecycle_label": lifecycle_label,
        "lifecycle_key": lifecycle_key,
        "stage_label": stage_label,
        "caveat": "Grounded targets, not observed sends. Audience counts, affinities, send windows "
                  "and content demand are real aggregates from the HCP 360 panel for the current "
                  "filters; rates are cited industry benchmarks scaled by the lifecycle index and "
                  "that cohort's measured affinity. No live ESP/Veeva feed is connected yet.",
        "grounding": {
            "panel_size": base["size"],
            "cohort_size": cohort["size"],
            "cohort_share_pct": round(100 * cohort["size"] / max(1, base["size"]), 1),
            "deliverable_pct": cohort["deliverable_pct"],
            "trx_total": trx["trx_total"],
            "writers": trx["writers"],
            "lifecycle_index": anc["index"],
            "sources": ["hcp_360.db", "config/omnichannel_benchmarks.json"],
        },
        "filters": {
            "applied": applied,
            "facets": panel.facets(applied),
            "months": months,
            "month_labels": labels,
        },
        "headline_keys": HEADLINE_KEYS,
        "metrics": metrics,
        "funnel": funnel,
        "journey": rmx.build_journey(funnel["volumes"]),
        "channels": channels,
        "geo": geo,
        "assets": assets,
        "send_windows": windows,
        "breakdowns": {"segment": segments, "specialty": specialties,
                       "channel": panel.dimension_counts("channel", applied),
                       "state": geo[:12]},
        "insights": _insights(cohort, base, metrics, channels, geo, windows, assets, segments),
        "optimizations": _optimizations(windows, channels, geo, metrics, cohort),
        "scorecard": _scorecard(metrics),
        "framework": _framework(cohort, metrics, tagging),
        "learnings": _learnings(cohort, channels, windows, assets, segments),
        "tagging": tagging,
        "test_design": _test_design(brand, cohort["size"]),
    }


def summary_text(project_id: str) -> str:
    """Compact text digest of the insights payload, for grounding the Reporting agent."""
    d = build(project_id)
    if not d.get("available"):
        return "No reporting insights available for this project yet."
    g = d["grounding"]
    lines = [f"Reporting insights for {d.get('brand') or 'the brand'} ({d.get('therapy_area') or 'n/a'}), "
             f"lifecycle {d['lifecycle_key']} (index {g['lifecycle_index']}×), priority stage {d['stage_label']}.",
             f"Cohort: {g['cohort_size']:,} of {g['panel_size']:,} HCPs in the panel "
             f"({g['cohort_share_pct']}%), {g['deliverable_pct']}% deliverable, {g['trx_total']:,} TRx.",
             "Metrics (value vs benchmark):"]
    for m in d["metrics"]:
        bench = f" vs {m['benchmark']}" if m["benchmark"] is not None else ""
        lines.append(f"  - {m['label']}: {m['value']}{'%' if m['unit'] == '%' else ''}{bench} [{m['status']}]")
    f = d["funnel"]["steps"]
    lines.append("Funnel: " + " -> ".join(f"{s['stage']} {s['count']:,}" for s in f))
    lines.append("Channels (engagement rate, HCPs preferring): " +
                 ", ".join(f"{c['label']} {c['engagement_pct']}% ({c['hcps']:,})" for c in d["channels"]))
    top = d["assets"][0] if d["assets"] else None
    if top:
        lines.append(f"Top content demand: {top['tag']} ({top['audience']:,} HCPs).")
    lines.append("Insights: " + "; ".join(i["title"] for i in d["insights"][:5]))
    lines.append("Tagging: UTM matrix (utm_source/medium/campaign/content/term + job_code on every URL).")
    lines.append(d["caveat"])
    return "\n".join(lines)


if __name__ == "__main__":
    import json
    print(json.dumps(build("_demo_"), indent=2, default=str)[:3000])
