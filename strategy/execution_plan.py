"""Campaign Execution Work Plan + Execution Work Plan/RACI (Sheets 12 & 14 of the
Customer Engagement Planning Toolkit workbook) -- the toolkit's "Deploy" phase,
which had no equivalent anywhere in the tool before this. Task bands are the real
toolkit task categories (Sheet 12's "Detailed Plan"), laid out across a 13-week
timeline and shifted later when bam.build_micro_journeys flags a journey needing a
PRC/MLR cycle (same content-readiness gate the SFMC Value Chain blueprint doc names
as the recurring bottleneck). The RACI is the toolkit's real stakeholder list
(Sheet 14) x its real 7 workstream columns, seeded with illustrative R/A/C/I values.
"""
from __future__ import annotations

# (task_category, representative tasks, default (start_week, end_week) on a 13-week timeline)
_WORK_PLAN_BANDS = [
    {"category": "Milestone kickoff", "tasks": ["Set-up meeting/workshop/sprint cadence", "Develop project plan", "Project management lead & support"], "weeks": (1, 3)},
    {"category": "Campaign impact & material preparation", "tasks": ["Overview of campaign contents", "Draft & create email contents", "Draft & create email header/subject lines", "Draft/create additional journey materials", "Review campaign contents (legal/promotion code)", "Finalize campaign content based on MLR/Medical review"], "weeks": (2, 5)},
    {"category": "Design alignment", "tasks": ["Fine tune campaign impacts (\"Look & feel\")", "Review campaign impacts", "Finalize campaign impacts"], "weeks": (4, 6)},
    {"category": "Review & subject tagging", "tasks": ["Tagging categorization", "Validate tagging categorization", "Implement tagging categorization", "Links adaptation for each impact"], "weeks": (6, 7)},
    {"category": "MarTech preparation", "tasks": ["Build SFMC/Veeva specifications", "Create implementation plan (incl. A/B testing)", "Execute implementation", "Internal + look&feel + final test validation", "Launch SFMC/Veeva"], "weeks": (6, 9)},
    {"category": "Campaign Execution", "tasks": ["Campaign execution for Wave 1", "Validate campaign effectiveness", "Refresh campaign impacts (Wave 3)"], "weeks": (9, 11)},
    {"category": "Performance report", "tasks": ["Implement data capture process", "Integrate KPIs into measurement framework", "Performance report"], "weeks": (10, 13)},
]

_TOTAL_WEEKS = 13

_MLR_DELAY_WEEKS = 2  # shift applied to every band after material prep when a PRC/MLR cycle is flagged

_WORKSTREAMS = ["Project management & process preparation", "Content Creation", "Design", "Tagging",
               "Martech Preparation", "Launch", "Performance report"]

_STAKEHOLDERS = ["GCC CD&A", "Brand Commercial team", "Brand Medical team", "Brand Access team",
                 "GCC Campaign Ops Excellence", "MC/OC/Digital & Ops specialists",
                 "Dev. Agencies & Global Service Center"]

# Seeded R/A/C/I per stakeholder x workstream -- illustrative starting assignment,
# same caveat status as every other generated table in strategy/.
_RACI = {
    "GCC CD&A": ["A", "C", "C", "C", "C", "C", "C"],
    "Brand Commercial team": ["A", "A", "C", "C", "C", "A", "A"],
    "Brand Medical team": ["C", "C", "I", "I", "I", "I", "C"],
    "Brand Access team": ["I", "C", "I", "I", "I", "I", "I"],
    "GCC Campaign Ops Excellence": ["R", "C", "C", "R", "R", "R", "C"],
    "MC/OC/Digital & Ops specialists": ["C", "C", "R", "R", "R", "R", "R"],
    "Dev. Agencies & Global Service Center": ["I", "R", "R", "C", "C", "I", "I"],
}


def _needs_mlr_delay(micro_journeys: dict | None) -> bool:
    journeys = (micro_journeys or {}).get("journeys", [])
    return any("PRC/MLR cycle required" in j.get("content_readiness", "") for j in journeys)


def build_execution_work_plan(micro_journeys: dict | None = None) -> dict:
    delay = _MLR_DELAY_WEEKS if _needs_mlr_delay(micro_journeys) else 0
    bands = []
    for i, band in enumerate(_WORK_PLAN_BANDS):
        start, end = band["weeks"]
        # Milestone kickoff never shifts; everything after material prep shifts if MLR-gated.
        shift = delay if i > 1 else 0
        start, end = min(start + shift, _TOTAL_WEEKS), min(end + shift, _TOTAL_WEEKS)
        bands.append({"category": band["category"], "tasks": band["tasks"], "start_week": start, "end_week": end,
                     "duration_weeks": max(1, end - start)})
    return {
        "toolkit_reference": "Campaign Execution Work Plan (Sheet 12)",
        "total_weeks": _TOTAL_WEEKS,
        "mlr_delay_applied": bool(delay),
        "mlr_delay_note": ("A journey in this plan needs a new PRC/MLR cycle, so MarTech/launch/reporting bands "
                          f"were pushed back {delay} week(s) versus the existing-stock-content baseline."
                          if delay else "All journeys reuse existing stock content -- no PRC/MLR delay applied."),
        "bands": bands,
    }


def build_execution_raci() -> dict:
    return {
        "toolkit_reference": "Execution Work Plan / RACI (Sheet 14)",
        "workstreams": _WORKSTREAMS,
        "rows": [{"stakeholder": s, "assignments": dict(zip(_WORKSTREAMS, _RACI[s]))} for s in _STAKEHOLDERS],
        "legend": {"R": "Responsible", "A": "Accountable", "C": "Consulted", "I": "Informed"},
        "caveat": "RACI assignments are an illustrative starting point seeded from typical pharma engagement-team roles, not this brand's confirmed governance -- validate with the actual brand/agency team before use.",
    }
