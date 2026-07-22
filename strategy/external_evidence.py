"""Live external datapoints agents cite to back a plan's decisions.

The user's rule: agents may reach the web ONLY for external research/datapoints that back a
decision — not to author content. So this module deliberately talks to the same structured,
keyless PUBLIC sources the app already trusts (ClinicalTrials.gov, PubMed/NCBI, openFDA) and
returns small, factual, *citeable* numbers — a trial-activity count, a recent-publication
count, an approval fact — each with its source URL and the date it was pulled. It does not do
open-web search and it does not generate prose.

Distinct from `engine.market_landscape` (which lists KB documents already scraped into the
local DB): this is a fresh, on-demand pull of *quantitative* signal sized to a specific
therapy area / brand, so a section can say "backed by N active trials (ClinicalTrials.gov, as
of <date>)". Everything here is best-effort: any network/parse failure yields fewer (or no)
datapoints and never raises into the planning pipeline.
"""
from __future__ import annotations

import datetime as _dt
import os

import requests

CT_STUDIES = "https://clinicaltrials.gov/api/v2/studies"
PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
OPENFDA_LABEL = "https://api.fda.gov/drug/label.json"

_TIMEOUT = 6  # best-effort, never load-bearing (see module docstring) -- fail fast rather than
              # stalling the whole pipeline; up to 4 of these run sequentially before Align shows.
_CACHE: dict[str, list[dict]] = {}


def enabled() -> bool:
    """External evidence is on unless disabled (e.g. offline dev/tests)."""
    return os.environ.get("OMNI_EXTERNAL_EVIDENCE", "1").strip().lower() not in {"0", "false", "no", "off"}


def _today() -> str:
    return _dt.date.today().isoformat()


def _dp(label: str, value, detail: str, source: str, url: str) -> dict:
    return {"label": label, "value": value, "detail": detail, "source": source,
            "url": url, "as_of": _today()}


def _ct_active_trials(therapy_area: str) -> dict | None:
    """Count of trials on ClinicalTrials.gov for the condition, and how many are recruiting."""
    try:
        total = requests.get(CT_STUDIES, params={"query.cond": therapy_area, "countTotal": "true",
                                                  "pageSize": 1}, timeout=_TIMEOUT).json().get("totalCount")
        recruiting = requests.get(CT_STUDIES, params={"query.cond": therapy_area,
                                  "filter.overallStatus": "RECRUITING", "countTotal": "true",
                                  "pageSize": 1}, timeout=_TIMEOUT).json().get("totalCount")
    except Exception as exc:  # noqa: BLE001
        print(f"[external_evidence] ClinicalTrials.gov lookup failed: {exc}")
        return None
    if total is None:
        return None
    detail = f"{total:,} registered studies for “{therapy_area}”"
    if recruiting is not None:
        detail += f", {recruiting:,} currently recruiting"
    url = f"https://clinicaltrials.gov/search?cond={requests.utils.quote(therapy_area)}"
    return _dp("Trial activity", total, detail + " — a proxy for competitive/pipeline intensity.",
               "ClinicalTrials.gov", url)


def _pubmed_recent(therapy_area: str, years: int = 3) -> dict | None:
    """Count of PubMed articles for the therapy area in the last `years` — evidence velocity."""
    start = _dt.date.today().year - years
    term = f'{therapy_area}[Title/Abstract] AND ("{start}"[PDAT] : "3000"[PDAT])'
    try:
        count = requests.get(PUBMED_ESEARCH, params={"db": "pubmed", "term": term, "retmax": 0,
                             "retmode": "json"}, timeout=_TIMEOUT).json().get("esearchresult", {}).get("count")
    except Exception as exc:  # noqa: BLE001
        print(f"[external_evidence] PubMed lookup failed: {exc}")
        return None
    if count is None:
        return None
    url = f"https://pubmed.ncbi.nlm.nih.gov/?term={requests.utils.quote(term)}"
    return _dp("Evidence velocity", int(count),
               f"{int(count):,} PubMed articles on “{therapy_area}” since {start} — the pace of new "
               "clinical evidence the messaging must keep current with.", "PubMed", url)


def _openfda_brand(brand: str) -> dict | None:
    """Whether the brand has an FDA drug label on file (an approval/regulatory anchor)."""
    try:
        data = requests.get(OPENFDA_LABEL, params={"search": f'openfda.brand_name:"{brand}"',
                            "limit": 1}, timeout=_TIMEOUT).json()
    except Exception as exc:  # noqa: BLE001
        print(f"[external_evidence] openFDA lookup failed: {exc}")
        return None
    total = (data.get("meta") or {}).get("results", {}).get("total")
    if not total:
        return None
    url = f"https://api.fda.gov/drug/label.json?search=openfda.brand_name:%22{requests.utils.quote(brand)}%22"
    return _dp("Regulatory anchor", total, f"An FDA drug label is on file for {brand} — claims must "
               "stay within the approved label.", "openFDA", url)


def datapoints(therapy_area: str = "", brand: str = "") -> list[dict]:
    """The citeable external datapoints for this plan, cached per (therapy_area, brand). Returns
    [] if disabled or nothing resolved — callers render it only when non-empty."""
    if not enabled():
        return []
    key = f"{therapy_area.strip().lower()}|{brand.strip().lower()}"
    if key in _CACHE:
        return _CACHE[key]
    out: list[dict] = []
    if therapy_area:
        for fn in (_ct_active_trials, _pubmed_recent):
            dp = fn(therapy_area)
            if dp:
                out.append(dp)
    if brand:
        dp = _openfda_brand(brand)
        if dp:
            out.append(dp)
    _CACHE[key] = out
    return out
