"""Client data for the planning engines -- SYNTHETIC until real sources are connected.

Brand teams plan with data Omni can't fetch publicly: HCP targeting (deciles), key accounts,
formulary access by state, field force capacity, channel consent reach, market share and Rx
baselines. Until those feeds exist, this module generates a realistic, deterministic stand-in per
brand (seeded by the brand name) so the Engagement Planner's diagnosis and feasibility checks can
run end to end. Everything it produces carries "synthetic": true and is labelled as such in the UI;
replace it by writing real data with the same shape to DATA_DIR/client_data/<brand>.json with
"synthetic": false.

Shapes are scaled from public inputs where available (state adult population from CDC PLACES, the
brand's audience segments from Brand IQ) so the synthetic numbers are proportionate, not arbitrary.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import brand_kit  # noqa: E402
import us_geography as geo  # noqa: E402
from paths import data_path  # noqa: E402

CALLS_PER_REP_PER_MONTH = 140      # typical in-person + remote calls
_CHANNELS = ["Rep visit (F2F)", "Remote rep / e-detail", "Email", "Webinar", "EHR point-of-care", "Programmatic display", "Paid social"]


def _path(brand: str) -> Path:
    d = data_path("client_data")
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{brand.lower()}.json"


def load(brand: str) -> dict | None:
    p = _path(brand)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def generate(brand: str, *, force: bool = False) -> dict:
    """Create (or return) the brand's synthetic client data."""
    if not force and (existing := load(brand)):
        return existing
    kit = brand_kit.kit_for(brand) or {}
    rng = random.Random(f"omni-client-data:{brand.lower()}")
    pop = {}
    try:
        pop = geo._population([])  # state adult population from CDC PLACES (public)
    except Exception:  # noqa: BLE001
        pass
    if not pop:
        pop = {st: 1_000_000 for st in geo.US_STATES}

    segments = kit.get("audience_segments") or [
        {"name": p.get("name"), "who": p.get("specialties") or p.get("who"), "tier": p.get("tier")}
        for p in ((kit.get("personas") or {}).get("hcp") or [])]
    named = [s for s in segments if s.get("name")][:8]
    sizes = _size_segments(brand, named)
    hcp_segments = [s for s in named if (sizes.get(s["name"]) or {}).get("is_hcp", True)] or [{"name": "Target HCPs", "tier": "Primary"}]
    total_pop = sum(pop.values()) or 1

    # HCP universe by state x segment, with deciles (10 = highest potential).
    universe = []
    for s in hcp_segments:
        us_total = (sizes.get(s["name"]) or {}).get("us_count") or 3 * total_pop / 100_000
        for st, p in pop.items():
            n = max(1, int(us_total * p / total_pop * rng.uniform(0.8, 1.2)))
            deciles = {str(d): max(0, int(n * w)) for d, w in zip(range(10, 0, -1), _decile_weights(rng))}
            universe.append({"segment": s["name"], "state": st, "hcps": n, "deciles": deciles})
    by_segment = {}
    for u in universe:
        b = by_segment.setdefault(u["segment"], {"hcps": 0, "top3_deciles": 0})
        b["hcps"] += u["hcps"]
        b["top3_deciles"] += sum(u["deciles"][d] for d in ("10", "9", "8"))

    # Key accounts: synthetic health systems in the most populous states.
    top_states = sorted(pop, key=lambda s: -pop[s])[:12]
    accounts = [{"name": f"{geo.US_STATES[st]} Health System {i + 1}", "state": st, "type": rng.choice(["IDN", "Academic medical centre", "Community hospital network", "Oncology network"]),
                 "hcps": rng.randint(80, 900), "formulary": rng.choice(["Preferred", "Covered", "Covered with PA", "Not covered"])}
                for st in top_states for i in range(rng.randint(1, 3))]

    # Formulary access by state (% of commercial + Medicare lives with unrestricted access).
    access_type = (kit.get("brand_situation") or {}).get("access")
    base = {"open": 0.85, "restricted": 0.55, "hospital": 0.7, "price_negotiated": 0.65}.get(access_type or "", 0.65)
    formulary = {st: {"unrestricted_pct": round(min(0.98, max(0.15, rng.gauss(base, 0.12))) * 100),
                      "pa_required_pct": round(rng.uniform(0.05, 0.4) * 100)} for st in pop}

    # Field force sized to the opportunity, with a realistic gap.
    total_top = sum(b["top3_deciles"] for b in by_segment.values())
    reps = max(20, int(total_top / rng.uniform(140, 260)))
    regions = {}
    for st, p in pop.items():
        r = geo.CENSUS_REGION.get(st, "Other")
        regions[r] = regions.get(r, 0) + p
    tot = sum(regions.values()) or 1
    field = {"reps": reps, "calls_per_rep_per_month": CALLS_PER_REP_PER_MONTH,
             "capacity_calls_per_month": reps * CALLS_PER_REP_PER_MONTH,
             "by_region": {r: max(1, round(reps * v / tot)) for r, v in regions.items()}}

    # Channel consent / reach per segment (share of the segment reachable on each channel).
    reach = {s["name"]: {ch: round(rng.uniform(0.15, 0.85) * 100) for ch in _CHANNELS} for s in hcp_segments}
    for s in hcp_segments:
        reach[s["name"]]["Email"] = round(rng.uniform(0.25, 0.6) * 100)          # opted-in email is the usual bottleneck

    # Market share and Rx baselines by region.
    share = {r: round(rng.uniform(0.08, 0.35) * 100, 1) for r in regions}
    trx = {r: int(regions[r] / 1000 * rng.uniform(0.5, 3.0)) for r in regions}

    out = {"brand": brand, "synthetic": True,
           "note": "SYNTHETIC client data generated by strategy/client_data.py (seeded by brand) -- a stand-in until real HCP, account, access, field and consent data are connected.",
           "hcp_universe": {"by_segment": by_segment, "by_state_segment": universe},
           "accounts": accounts, "formulary_by_state": formulary, "field_force": field,
           "channel_reach_pct": reach, "market_share_pct_by_region": share, "monthly_trx_by_region": trx}
    _path(brand).write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def _size_segments(brand: str, segments: list[dict]) -> dict:
    """Realistic US headcounts per segment for the synthetic universe. The model estimates them
    (they're synthetic anyway); without a model every segment gets a modest default."""
    try:
        from llm_json import complete_json
        out = complete_json(
            "Estimate, for SYNTHETIC test data, the realistic number of people in the United States in each "
            "segment (e.g. ~30,000 practising cardiologists, ~8,000 endocrinologists, ~15,000 oncologists). Say "
            "whether the segment is healthcare professionals (is_hcp) or patients/caregivers. Reply with JSON "
            'only: {"segments":[{"name":"","is_hcp":true,"us_count":0}]}',
            {"brand": brand, "segments": [{k: s.get(k) for k in ("name", "who")} for s in segments]}, max_tokens=1200)
        return {x["name"]: x for x in out.get("segments") or [] if isinstance(x, dict) and x.get("name")}
    except Exception:  # noqa: BLE001 -- synthetic sizing is optional; fall back to defaults
        return {}


def _decile_weights(rng: random.Random) -> list[float]:
    """Concentrated potential: the top deciles hold few HCPs but most volume -- here the HCP
    counts per decile (decile 10 = highest potential, smallest group)."""
    w = [0.04, 0.05, 0.06, 0.08, 0.09, 0.1, 0.12, 0.13, 0.15, 0.18]
    w = [x * rng.uniform(0.85, 1.15) for x in w]
    s = sum(w)
    return [x / s for x in w]


def summary(brand: str) -> dict:
    """A compact view for the planner's grounding and the UI."""
    d = generate(brand)
    states = {}
    for u in d["hcp_universe"]["by_state_segment"]:
        st = states.setdefault(u["state"], {"hcps": 0, "top3": 0})
        st["hcps"] += u["hcps"]
        st["top3"] += sum(u["deciles"][k] for k in ("10", "9", "8"))
    top_states = sorted(states.items(), key=lambda kv: -kv[1]["top3"])[:10]
    worst_access = sorted(d["formulary_by_state"].items(), key=lambda kv: kv[1]["unrestricted_pct"])[:8]
    return {"synthetic": d["synthetic"], "note": d["note"],
            "hcps_by_segment": d["hcp_universe"]["by_segment"],
            "top_states_by_high_decile_hcps": [{"state": s, **v} for s, v in top_states],
            "lowest_access_states": [{"state": s, **v} for s, v in worst_access],
            "field_force": d["field_force"], "channel_reach_pct": d["channel_reach_pct"],
            "market_share_pct_by_region": d["market_share_pct_by_region"],
            "accounts": d["accounts"][:15]}
