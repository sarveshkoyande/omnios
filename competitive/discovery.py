"""Auto-discovers likely competitor brand/drug names for a therapy area by querying
ClinicalTrials.gov for studies matching that condition and counting how often each
intervention (drug) name appears, excluding the target brand itself. Real public
data, not a guessed/invented competitor list -- if nothing comes back, the caller
gets an empty list rather than a fabricated one.
"""
from __future__ import annotations

import requests

CT_BASE_URL = "https://clinicaltrials.gov/api/v2/studies"


def discover_competitors(therapy_area: str, exclude_brand: str, limit: int = 5, page_size: int = 50) -> list[str]:
    if not therapy_area:
        return []

    try:
        resp = requests.get(
            CT_BASE_URL,
            params={"query.cond": therapy_area, "pageSize": page_size},
            timeout=8,  # best-effort (falls back to []) -- fail fast, this runs before Align shows
        )
        resp.raise_for_status()
        studies = resp.json().get("studies", [])
    except Exception as e:
        print(f"[discovery] ClinicalTrials.gov query failed for '{therapy_area}': {e}")
        return []

    exclude_lower = exclude_brand.strip().lower()
    drug_counts: dict[str, int] = {}
    for study in studies:
        arms_module = study.get("protocolSection", {}).get("armsInterventionsModule", {})
        for interv in arms_module.get("interventions", []):
            name = (interv.get("name") or "").strip()
            if not name or exclude_lower in name.lower():
                continue
            # Skip generic non-drug interventions (behavioral/procedure arms, placebo, standard-of-care labels).
            interv_type = (interv.get("type") or "").upper()
            if interv_type and interv_type not in {"DRUG", "BIOLOGICAL"}:
                continue
            if name.lower() in {"placebo", "standard of care", "usual care"}:
                continue
            drug_counts[name] = drug_counts.get(name, 0) + 1

    ranked = sorted(drug_counts.items(), key=lambda kv: -kv[1])
    return [name for name, _ in ranked[:limit]]
