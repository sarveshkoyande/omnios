"""
Industry benchmark baselines for pharma omnichannel engagement, and the two agent-facing
recommendation builders that consume them.

`config/omnichannel_benchmarks.json` holds the researched dataset: channel-tactic
engagement rates (email open/CTR, webinar attendance, display CTR, paid search), HCP rep
access, digital-affinity posture, the US HCP universe by specialty, a therapy-area ->
specialty map, persona x channel affinity indices, and lifecycle-stage KPI target bands.

Two agents read it:

  * Maya (Market & Competitive Intelligence) -> `maya_audience_profile()`
    Sizes the addressable HCP audience for a therapy area, reads its rep-access
    constraint and digital posture. Fills the Target-Customer-Group rows that ask for
    demographics, representative attributes and attitude-to-industry.

  * Arjun (Activation Planning) -> `arjun_engagement_baseline()`
    Turns the channel mix into per-channel engagement targets (baseline x lifecycle
    index) and the KPI priorities for the stage. Fills the channel-selection affinity
    column and the "what good looks like" column of Test-Measure-Learn.

Everything returned carries `agent` and `confidence` so the plan can render it as an
*agent recommendation* (a distinct highlight) rather than a captured fact or an open
question. Nothing here is a brand forecast -- a brand's own history always supersedes it.
"""
from __future__ import annotations

import json
import pathlib

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
BENCH_JSON = BASE_DIR / "config" / "omnichannel_benchmarks.json"

_CACHE: dict | None = None

CAVEAT = ("Agent-recommended from researched industry baselines (see sources) — directional, "
          "not a brand forecast. Replace with the brand's own historical performance once one "
          "in-market period exists.")


def load() -> dict:
    global _CACHE
    if _CACHE is None:
        _CACHE = json.loads(BENCH_JSON.read_text(encoding="utf-8")) if BENCH_JSON.exists() else {}
    return _CACHE


def _fmt_int(n) -> str:
    return f"{int(n):,}" if isinstance(n, (int, float)) else "—"


def source_urls(source_ids: list[str]) -> list[dict]:
    src = load().get("sources", {})
    return [{"title": src[s]["title"], "url": src[s]["url"]} for s in source_ids if s in src]


# ------------------------------------------------------------------ Maya --------------

def specialties_for(therapy_area: str) -> list[str]:
    return load().get("therapy_area_to_specialty", {}).get(therapy_area, [])


def audience_size(therapy_area: str) -> dict:
    """Addressable US HCP universe for a therapy area: the sum across its mapped
    specialties, with a per-specialty breakdown and the weakest confidence tag."""
    b = load()
    uni = b.get("hcp_universe_us", {})
    specs = specialties_for(therapy_area)
    rows, total, conf = [], 0, "cited"
    for s in specs:
        e = uni.get(s)
        if not e:
            continue
        rows.append({"specialty": s, "count": e["count"], "confidence": e.get("confidence", "approximate")})
        total += e["count"]
        if e.get("confidence") == "approximate":
            conf = "approximate"
    return {"therapy_area": therapy_area, "specialties": rows, "total": total,
            "confidence": conf if rows else "unknown"}


def rep_access_for(therapy_area: str) -> dict:
    """The rep-access constraint for this therapy area's lead specialty, falling back to
    the global figure. Access -- not creative -- is the first constraint on Field spend."""
    acc = load().get("hcp_access", {})
    lead = (specialties_for(therapy_area) or [""])[0]
    spec = (acc.get("by_specialty") or {}).get(lead)
    return {
        "lead_specialty": lead,
        "specialty_fully_accessible_pct": (spec or {}).get("fully_accessible_pct"),
        "specialty_meet_3_or_fewer_pct": (spec or {}).get("meet_3_or_fewer_companies_pct"),
        "global_access_rate_pct": acc.get("global_access_rate_pct"),
        "us_rep_accessible_pct": acc.get("us_rep_accessible_pct"),
        "no_rep_contact_6mo_pct": acc.get("no_rep_contact_6mo_pct"),
        "restrict_to_3_or_fewer_companies_pct": acc.get("restrict_to_3_or_fewer_companies_pct"),
        "confidence": "cited",
    }


def maya_audience_profile(brand: str, therapy_area: str, persona: str) -> dict:
    """Maya's benchmark-grounded read of the target audience. Returns both the structured
    numbers and the prose answers that fill the Target Customer Group template rows
    (t2 demographics, t7 representative attributes, t10 attitude to industry)."""
    b = load()
    size = audience_size(therapy_area)
    access = rep_access_for(therapy_area)
    aff = b.get("digital_affinity", {})

    spec_list = ", ".join(f"{r['specialty']} (~{_fmt_int(r['count'])})" for r in size["specialties"]) or "—"
    total_str = _fmt_int(size["total"]) if size["total"] else "not sized"

    # t2 -- demographics: specialties, geography, patient pool
    t2 = (f"US addressable universe ≈ **{total_str}** practising physicians across {spec_list}. "
          f"Geography: US national (the roster's primary market). Patient pool is indication-specific — "
          f"the brand team should overlay treated-patient volume per HCP decile.")

    # t7 -- which demographic attributes best represent the group
    t7 = (f"Specialty ({(specialties_for(therapy_area) or ['—'])[0]}) plus three behavioural attributes that predict "
          f"engagement better than demography: (1) rep-access tier, (2) digital-affinity tier, "
          f"(3) prescribing decile. Persona read: **{persona}**.")

    # t10 -- attitude toward industry (the access/receptivity posture)
    parts = []
    if access.get("specialty_fully_accessible_pct"):
        parts.append(f"only **{access['specialty_fully_accessible_pct']:.0f}%** of {access['lead_specialty']} providers "
                     f"are fully rep-accessible")
    parts.append(f"~{access['us_rep_accessible_pct']:.0f}% of US physicians are rep-accessible overall")
    parts.append(f"~{access['no_rep_contact_6mo_pct']:.0f}% had no rep contact in the last six months")
    parts.append(f"~{access['restrict_to_3_or_fewer_companies_pct']:.0f}% restrict engagement to three or fewer companies")
    t10 = ("Attitude to industry is **access-constrained, not hostile**: " + "; ".join(parts) + ". "
           f"But digital receptivity is high — **{aff.get('want_same_or_more_digital_pct')}%** of physicians want the same or more "
           f"digital interaction, and **{aff.get('more_likely_to_engage_if_tailored_pct')}%** engage more when content is tailored "
           f"to their patients. Earn the interaction with relevance; do not assume field access.")

    return {
        "agent": "intel", "agent_name": "Market & Competitive Intelligence", "confidence": size["confidence"],
        "audience_size": size, "rep_access": access, "digital_affinity": aff,
        "answers": {"t2": t2, "t7": t7, "t10": t10},
        "headline": (f"≈{total_str} addressable US HCPs · "
                     f"{access['us_rep_accessible_pct']:.0f}% rep-accessible · "
                     f"{aff.get('want_same_or_more_digital_pct')}% want same/more digital"),
        "caveat": CAVEAT,
        "sources": source_urls(["asco_workforce", "aamc_dashboard", "pharmaphorum_access",
                                 "prescriberpoint", "indegene_digital_affinity"]),
    }


# ------------------------------------------------------------------ Arjun -------------

def channel_affinity(persona: str, channel: str) -> int | None:
    return (load().get("persona_channel_affinity", {}).get(persona) or {}).get(channel)


def channel_targets(channel: str, lifecycle_key: str) -> dict | None:
    """Engagement target band for a channel bucket at a lifecycle stage:
    baseline x lifecycle index, expressed as a +/-15% working band."""
    b = load()
    base = (b.get("channel_bucket_baselines", {}) or {}).get(channel)
    life = (b.get("lifecycle_kpi_targets", {}) or {}).get(lifecycle_key, {})
    if not base:
        return None
    idx = life.get("index", 1.0)
    out = {"channel": channel, "kpi": base["primary_kpi"], "tactic": base["primary_tactic"],
           "baseline_pct": base.get("baseline_pct"), "index": idx, "confidence": "derived"}
    if base.get("baseline_pct") is None:
        out.update({"target_pct": None, "target_low_pct": None, "target_high_pct": None,
                    "what_good_looks_like": "Brand-measured — no defensible cross-industry baseline."})
        return out
    target = base["baseline_pct"] * idx
    lo, hi = target * 0.85, target * 1.15
    out.update({"target_pct": round(target, 2), "target_low_pct": round(lo, 2), "target_high_pct": round(hi, 2),
                "what_good_looks_like": f"{base['primary_kpi']} {round(lo,2)}–{round(hi,2)}% "
                                        f"(industry baseline {base['baseline_pct']}%, {lifecycle_key} index {idx}×)"})
    return out


# Which benchmark a Test-Measure-Learn row should be scored against is decided by WHAT IT
# MEASURES, not by the channel bucket it happens to be tagged with -- a webinar-attendance
# test tagged "Field" must still be scored against the webinar attendance baseline, and a
# volume metric (impressions) must not be given a percentage band at all.
_MEASURE_KINDS = [
    (("click-through", "click through", "ctr", "click rate"), "ctr"),
    (("open rate", "opens", "email open"), "open"),
    (("webinar", "attendance", "registration", "webcast"), "attendance"),
    (("rep access", "detail", "call rate", "field access"), "access"),
    (("impression", "reach delivered", "volume", "downloads", "visits", "sessions"), None),
]


def _measure_kind(measure: str) -> str | None | bool:
    """Returns the benchmark kind for a measure, None for a volume metric with no defensible
    rate baseline, or False when nothing matches (leave the row untouched)."""
    m = (measure or "").lower()
    for keys, kind in _MEASURE_KINDS:
        if any(k in m for k in keys):
            return kind
    return False


def measure_target(measure: str, channel: str, lifecycle_key: str) -> dict | None:
    """Benchmark target band for a specific MEASURE (e.g. 'Click-through rate'), scaled by
    the lifecycle index. Returns None when the measure has no defensible rate baseline
    (volume metrics) or doesn't map to a benchmark at all -- callers then leave the row as-is."""
    kind = _measure_kind(measure)
    if kind is False or kind is None:
        return None
    b = load()
    tac = b.get("channel_tactics", {})
    if kind == "open":
        base, kpi, src = tac["email_hcp_triggered"]["open_rate_pct"], "Open rate", "email_hcp_triggered"
    elif kind == "ctr":
        # CTR baseline depends on the channel the click happens in: display CTR is an order
        # of magnitude below email CTR, so scoring an email test against display is wrong.
        if channel == "Reach":
            base, kpi, src = tac["programmatic_display_hcp"]["ctr_pct"], "CTR", "programmatic_display_hcp"
        else:
            base, kpi, src = tac["email_hcp_triggered"]["ctr_pct"], "CTR", "email_hcp_triggered"
    elif kind == "attendance":
        base, kpi, src = tac["webinar_hcp"]["attendance_rate_pct"], "Attendance rate", "webinar_hcp"
    elif kind == "access":
        base, kpi, src = b["hcp_access"]["global_access_rate_pct"], "HCP access rate", "hcp_access"
    else:
        return None
    idx = (b.get("lifecycle_kpi_targets", {}).get(lifecycle_key) or {}).get("index", 1.0)
    target = base * idx
    lo, hi = round(target * 0.85, 2), round(target * 1.15, 2)
    return {"kpi": kpi, "baseline_pct": base, "index": idx, "target_low_pct": lo, "target_high_pct": hi,
            "benchmark": src, "confidence": "derived",
            "what_good_looks_like": f"{kpi} {lo}–{hi}% (industry baseline {base}%, {lifecycle_key} index {idx}×)"}


def arjun_engagement_baseline(lifecycle_key: str, persona: str, channel_mix_pct: dict) -> dict:
    """Arjun's per-channel engagement targets and stage KPI priorities, for the funded
    channels only. Fills the channel-selection affinity column and TML's 'good looks like'."""
    b = load()
    life = (b.get("lifecycle_kpi_targets", {}) or {}).get(lifecycle_key, {})
    rows = []
    for ch, pct in sorted((channel_mix_pct or {}).items(), key=lambda kv: -kv[1]):
        t = channel_targets(ch, lifecycle_key) or {}
        rows.append({
            "channel": ch, "share_pct": pct,
            "affinity": channel_affinity(persona, ch),
            "kpi": t.get("kpi"), "baseline_pct": t.get("baseline_pct"),
            "target_low_pct": t.get("target_low_pct"), "target_high_pct": t.get("target_high_pct"),
            "what_good_looks_like": t.get("what_good_looks_like", "—"),
        })
    return {
        "agent": "activation", "agent_name": "Activation Planning", "confidence": "derived",
        "lifecycle_key": lifecycle_key, "emphasis": life.get("emphasis", ""),
        "priority_kpis": life.get("priority_kpis", []),
        "channels": rows,
        "governance": b.get("governance", {}),
        "headline": (f"{life.get('emphasis','')} · targets set at {life.get('index',1.0)}× industry baseline"),
        "caveat": CAVEAT,
        "sources": source_urls(["pharma_mkting_email", "phamax_benchmarks", "focus_digital",
                                 "dice_comms", "pulsepoint"]),
    }


if __name__ == "__main__":
    m = maya_audience_profile("Kisqali", "breast cancer", "Digital-first")
    print("MAYA:", m["headline"], "| confidence:", m["confidence"])
    print("  t2:", m["answers"]["t2"][:110])
    a = arjun_engagement_baseline("growth", "Digital-first", {"Owned digital": 30, "Reach": 25, "Field": 20, "Events": 15, "Peer": 5, "Patient-adjacent": 5})
    print("ARJUN:", a["headline"])
    for r in a["channels"][:3]:
        print(f"  {r['channel']:<18} affinity={r['affinity']} {r['what_good_looks_like'][:70]}")
