"""Engagement Orchestration -- SLA engine, seeded from the real captured day-count baseline.

For every activity type (orchestration_taxonomy.ACTIVITY_TYPES) this holds:
  baseline_days   -- current-state MANUAL duration (business days). What the work takes today.
  target_days     -- the agentic/orchestrated target. What Engagement Orchestration aims for.
  definition_of_done -- the explicit "this task is complete when..." statement (marketing-ops
                     SLAs exist precisely to define done, so a missing upstream input can't be
                     silently treated as the owner's missed deadline).
  gating_input    -- short description of the prerequisite that must be delivered before the
                     clock is fair to run (input-gating, PRD F3.3); None if self-contained.

Baseline seed (vault):
  - Follow-up call SLA baseline for one SIMPLE campaign: strategy brief 7-8d; orchestration-equiv
    15-20d; build+configure+tag+validate ~16d; approval+migration +2d; total ~18d asset-ready ->
    deployed. Target stated as 5 days. Medium/complex add days on top (not yet quantified there --
    modelled via COMPLEXITY multipliers below).
  - The per-category "SLA to clear" strings already in orchestration_tasks._CATEGORY_META (10 /
    5 / 15 / 7 business days) are the same numbers, reused here as structured baselines.
  - patient_gate / MLR review get NO compression (target == baseline): you cannot agent away a
    human compliance decision -- "agents orchestrate; MLR originates".

See PRD-Orchestration-Phase.md sections 6.3 (SLA engine) and 6.4 (time-saved lens).
"""
from __future__ import annotations

import orchestration_taxonomy as tax

# --- SLA library, keyed by activity_type ------------------------------------------------------

_SLA: dict[str, dict] = {
    "touchpoint_build": {
        "baseline_days": 10, "target_days": 3,
        "definition_of_done": "Touchpoint built + configured in the channel tool and passing internal preview/QA.",
        "gating_input": "Approved content/HTML for this touchpoint is available (AFU).",
    },
    "journey_config": {
        "baseline_days": 5, "target_days": 1,
        "definition_of_done": "Entry criteria + decision splits configured and validated against the plan's business rules.",
        "gating_input": "Segments and touchpoints for this journey are defined.",
    },
    "audience_build": {
        "baseline_days": 5, "target_days": 1,
        "definition_of_done": "Target audience pulled, deduped, suppression + consent enforced, and count signed off.",
        "gating_input": "Target list / specialty definition delivered.",
    },
    "content_production": {
        "baseline_days": 15, "target_days": 5,
        "definition_of_done": "Content drafted, designed, and MLR-approved (AFU + job code) for the message.",
        "gating_input": "Approved messaging / claims from the plan.",
    },
    "tactical_activation": {
        "baseline_days": 10, "target_days": 3,
        "definition_of_done": "Critical success factor operationalised into a concrete configured activity.",
        "gating_input": None,
    },
    "scientific_content": {
        "baseline_days": 15, "target_days": 5,
        "definition_of_done": "Scientific-exchange anchor prepared and MLR/medical-approved.",
        "gating_input": "Approved proof points / evidence from the plan.",
    },
    "account_pathway": {
        "baseline_days": 7, "target_days": 2,
        "definition_of_done": "Account archetype pathway move defined and handed to field/ops.",
        "gating_input": None,
    },
    "patient_gate": {
        # pure human/compliance gate -- no compression.
        "baseline_days": 5, "target_days": 5,
        "definition_of_done": "Regulatory/legal has confirmed patient-facing gate status; documented in the ledger.",
        "gating_input": "Regulatory/legal reviewer availability.",
    },
    "measurement_setup": {
        "baseline_days": 7, "target_days": 2,
        "definition_of_done": "Tracking/KPIs stood up and validated to capture the leading indicators.",
        "gating_input": "Journey + touchpoints live enough to instrument.",
    },
    "custom": {
        "baseline_days": 5, "target_days": 3,
        "definition_of_done": "Manually-added activity completed per its description.",
        "gating_input": None,
    },
}

# Complexity multipliers -- simple is the captured baseline; medium/complex add days (call noted
# they add "more days on top", unquantified -- these are the tool's default, admin-overridable).
COMPLEXITY = {"simple": 1.0, "medium": 1.6, "complex": 2.4}
DEFAULT_COMPLEXITY = "simple"


def sla_for(activity_type: str) -> dict:
    """SLA record for an activity type, defaulting to the custom profile."""
    return _SLA.get(activity_type, _SLA["custom"])


def _round_days(x: float) -> int:
    """Never let a real activity round to zero days."""
    return max(1, round(x))


def resolve(activity_type: str, complexity: str = DEFAULT_COMPLEXITY) -> dict:
    """Full resolved SLA for an activity: baseline vs target days at a complexity tier, the days
    saved, and the definition-of-done / input-gate. This is what an Activity carries and what the
    time-saved lens (PRD 6.4/F4.7) and scheduler consume. Stored on an activity under `sla_meta`
    (the flat `sla` field stays a display string for frontend back-compat)."""
    rec = sla_for(activity_type)
    mult = COMPLEXITY.get(complexity, 1.0)
    baseline = _round_days(rec["baseline_days"] * mult)
    target = _round_days(rec["target_days"] * mult)
    target = min(target, baseline)  # target can never be slower than the manual baseline
    return {
        "activity_type": activity_type,
        "complexity": complexity,
        "baseline_days": baseline,
        "target_days": target,
        "days_saved": baseline - target,
        "definition_of_done": rec["definition_of_done"],
        "gating_input": rec["gating_input"],
        # kept for back-compat with the old free-text `sla` field the frontend already shows.
        "sla_label": f"{target} business days",
    }


def summarize_time_saved(activities: list[dict]) -> dict:
    """Roll a list of enriched activities up into the stakeholder ROI number: total manual baseline
    vs total orchestrated target, and the reduction. `activities` items are expected to carry an
    `sla` sub-dict as produced by resolve() (via orchestration_tasks enrichment)."""
    baseline = target = 0
    for a in activities:
        s = a.get("sla_meta") or {}
        baseline += int(s.get("baseline_days") or 0)
        target += int(s.get("target_days") or 0)
    pct = round(100 * (baseline - target) / baseline) if baseline else 0
    return {
        "baseline_days_total": baseline,
        "target_days_total": target,
        "days_saved_total": baseline - target,
        "reduction_pct": pct,
        # elapsed-time note: the vault baseline is ~18 elapsed days for a simple campaign against a
        # stated 5-day target; per-activity day-sums above are effort-days, not the critical path.
        # The scheduler (orchestration_schedule.py) computes the elapsed/critical-path figure.
        "note": "Effort-day totals across all activities; see the schedule for elapsed calendar/critical-path time.",
    }
