"""US geography layer (docs/redesign/engagement-plan-v2.md, "US geography & client data").

Omni plans for the US. This module gives the public half of the geography picture: adult disease
prevalence by state from CDC PLACES (county estimates rolled up to states, weighted by county
population), so plans can prioritise states and spot white space. The client half (HCP deciles,
accounts, formulary, field force, consent reach, share) comes from client_data.py.

Which PLACES measures fit a brand is decided by the model from the brand's indications (rule R1:
no keyword matching); the numbers themselves are CDC's, cited with the dataset and release.
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from llm_json import complete_json  # noqa: E402
from paths import data_path  # noqa: E402

PLACES_COUNTY = "https://data.cdc.gov/resource/swc5-untb.json"   # PLACES: Local Data for Better Health, County Data
PLACES_PAGE = "https://www.cdc.gov/places/"
_UA = {"User-Agent": "OmniOS/1.0 (US geography)"}

US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts",
    "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}
CENSUS_REGION = {
    **dict.fromkeys(["CT", "ME", "MA", "NH", "RI", "VT", "NJ", "NY", "PA"], "Northeast"),
    **dict.fromkeys(["IL", "IN", "MI", "OH", "WI", "IA", "KS", "MN", "MO", "NE", "ND", "SD"], "Midwest"),
    **dict.fromkeys(["DE", "DC", "FL", "GA", "MD", "NC", "SC", "VA", "WV", "AL", "KY", "MS", "TN", "AR", "LA", "OK", "TX"], "South"),
    **dict.fromkeys(["AZ", "CO", "ID", "MT", "NV", "NM", "UT", "WY", "AK", "CA", "HI", "OR", "WA"], "West"),
}


def _get(params: dict) -> list[dict]:
    url = f"{PLACES_COUNTY}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=_UA), timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def measures() -> list[dict]:
    rows = _get({"$select": "distinct measureid, measure", "$limit": 100})
    return [{"id": r["measureid"], "measure": r["measure"]} for r in rows]


def _cache_path(measure: str) -> Path:
    p = data_path("geo_cache")
    p.mkdir(parents=True, exist_ok=True)
    return p / f"places_{measure}.json"


def state_prevalence(measure: str) -> dict:
    """Crude adult prevalence by state for one PLACES measure, with an estimated adult count.
    Cached under DATA_DIR (CDC releases yearly)."""
    cache = _cache_path(measure)
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    rows = _get({"$select": "stateabbr, data_value, totalpopulation, year",
                 "$where": f"measureid='{measure}' AND data_value_type='Crude prevalence'", "$limit": 5000})
    agg: dict[str, dict] = {}
    year = None
    for r in rows:
        st = r.get("stateabbr")
        if st not in US_STATES:
            continue
        try:
            v, pop = float(r["data_value"]), float(r["totalpopulation"])
        except (KeyError, TypeError, ValueError):
            continue
        year = r.get("year") or year
        a = agg.setdefault(st, {"pop": 0.0, "cases": 0.0})
        a["pop"] += pop
        a["cases"] += pop * v / 100
    states = sorted(({"state": st, "name": US_STATES[st], "region": CENSUS_REGION.get(st),
                      "prevalence_pct": round(a["cases"] / a["pop"] * 100, 1) if a["pop"] else None,
                      "est_cases": int(a["cases"]), "population": int(a["pop"])} for st, a in agg.items()),
                    key=lambda x: -x["est_cases"])
    out = {"measure": measure, "year": year, "states": states,
           "source": f"CDC PLACES county data {year or ''}, crude prevalence rolled up to states (population-weighted)",
           "url": PLACES_PAGE}
    cache.write_text(json.dumps(out), encoding="utf-8")
    return out


def pick_measures(brand: str, indications: list[dict]) -> list[dict]:
    """The model chooses which PLACES measures approximate the brand's patient populations."""
    out = complete_json(
        "You map a pharmaceutical brand's indications to CDC PLACES adult prevalence measures. Choose only "
        "from `measures`, at most 3, and only where the measure is a reasonable population proxy for an "
        "indication (say how good a proxy it is). If none fits (e.g. a rare disease), return an empty list. "
        'Reply with JSON only: {"picks":[{"measure":"ID","for_indication":"","fit":"direct|proxy","why":""}]}',
        {"brand": brand, "conditions": sorted({(i.get("condition") or i.get("name") or "") for i in indications}),
         "measures": measures()}, max_tokens=2000)
    picks, seen = [], set()
    for p in out.get("picks") or []:
        if isinstance(p, dict) and p.get("measure") and p["measure"] not in seen:
            seen.add(p["measure"])
            picks.append(p)
    return picks


def build(brand: str, indications: list[dict]) -> dict:
    """The brand's public US geography layer: picked measures with state prevalence."""
    picks = pick_measures(brand, indications)
    layers = []
    for p in picks:
        try:
            layers.append({**p, **state_prevalence(p["measure"])})
        except Exception as e:  # noqa: BLE001 -- one measure failing leaves the others
            layers.append({**p, "error": str(e)})
    return {"country": "US", "layers": layers, "population_by_state": _population(layers)}


def _population(layers: list[dict]) -> dict:
    for layer in layers:
        if layer.get("states"):
            return {s["state"]: s["population"] for s in layer["states"]}
    try:
        return {s["state"]: s["population"] for s in state_prevalence("CHECKUP")["states"]}
    except Exception:  # noqa: BLE001
        return {}
