"""Test-Measure-Learn framework (Sheets 11 & 13 of the Customer Engagement Planning
Toolkit workbook, "Sheet4" and the hidden "Sheet7" TEST/MEASURE/LEARN diagram --
same framework transcribed twice in the source). Turns the KPI engine's leading
indicators (kpi.py) into the toolkit's own 9-column test table rather than
inventing a parallel measurement model.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from rules import CHANNEL_TOUCHPOINTS, STAGE_BY_KEY  # noqa: E402

_COLUMNS = ["test", "objective", "channels", "measure", "definition", "frequency",
           "data_source", "what_good_looks_like", "what_we_will_learn"]


def _infer_channels(indicator: str) -> str:
    low = indicator.lower()
    for bucket, touchpoints in CHANNEL_TOUCHPOINTS.items():
        if any(kw.split()[0].lower() in low for kw in touchpoints):
            return bucket
    if "email" in low or "website" in low or "portal" in low:
        return "Owned digital"
    if "webinar" in low or "congress" in low:
        return "Events"
    if "rep" in low or "detail" in low or "sample" in low:
        return "Field"
    return "Owned digital"


def build_test_measure_learn(stage_key: str, leading_indicators: list[str]) -> dict:
    stage = STAGE_BY_KEY.get(stage_key, STAGE_BY_KEY["aware"])
    rows = []
    for indicator in leading_indicators[:3]:
        channel = _infer_channels(indicator)
        rows.append({
            "test": f"Does {indicator.lower()} move in response to the current channel mix?",
            "objective": f"Ties back to the stage's engagement goal: {stage['engagement_goal']}.",
            "channels": channel,
            "measure": indicator,
            "definition": f"{indicator} as tracked in the martech/CDP engagement logs for this segment.",
            "frequency": "Bi-weekly for always-on digital channels, monthly for field/event channels.",
            "data_source": "SFMC / CDP engagement logs, reconciled against claims/Rx data where relevant.",
            "what_good_looks_like": "Directional improvement vs. this segment's prior-wave baseline (no absolute benchmark exists yet).",
            "what_we_will_learn": f"Whether {indicator.lower()} is a leading predictor of progression to the next journey stage for this persona.",
        })
    return {
        "toolkit_reference": "Test-Measure-Learn framework (Sheets 11 & 13)",
        "columns": _COLUMNS,
        "rows": rows,
        "caveat": "Test rows are drafted from the KPI engine's leading indicators, not a run experiment -- confirm data availability in SFMC/CDP before committing to a test design.",
    }
