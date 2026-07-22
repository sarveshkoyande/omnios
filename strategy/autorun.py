"""Orchestrates the full 9-stage campaign planning process end to end from just
three inputs (brand, therapy area, lifecycle phase) -- no manual persona/journey-stage
picking or competitor typing required. Each stage's real output feeds the next:
lifecycle -> persona/journey stage -> market landscape -> discovered competitors ->
strategy (messaging + channel mix) -> SWOT/positioning -> budget -> KPIs -> risk/governance.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from lifecycle import infer_persona_and_stage  # noqa: E402
from engine import generate_strategy, market_landscape  # noqa: E402
from positioning import build_positioning_statement  # noqa: E402
from kpi import build_kpi_framework  # noqa: E402
from competitive.discovery import discover_competitors  # noqa: E402
from competitive.swot import build_swot  # noqa: E402
import process_knowledge  # noqa: E402

STANDARD_RISKS = [
    "Regulatory/MLR delay pushes campaign launch past planned window",
    "Competitor launches a new indication or evidence readout that shifts the positioning",
    "Data fragmentation (CRM/CDP/claims not reconciled) degrades NBA/targeting quality",
    "Budget cut mid-cycle forces channel-mix re-prioritization",
    "HCP consent/opt-in expiry reduces addressable target list",
    "Field force turnover disrupts rep-dependent segment coverage",
    "Payer/formulary access restriction narrows the addressable patient population",
]

GOVERNANCE_CADENCE = {
    "Quarterly": "QBR -- cross-functional review of full-funnel performance vs. the annual/semi-annual brand plan.",
    "Monthly": "Monthly franchise/brand review -- lagging KPI trends (TRx/NRx, share), budget pacing, competitive moves.",
    "Bi-weekly": "Bi-weekly brand review -- leading-indicator check-in, content pipeline/MLR status, campaign tagging/UTM governance.",
    "Continuous": "Operational meetings -- NBA/CDP trigger tuning, channel-ops issues, data-feed health (CRM/CDP/claims match rates).",
    "Orchestrator role": "A named Omnichannel Orchestrator (per the Ipsen NA playbook) owns journey setup, campaign tagging, and this whole cadence.",
}


def run_full_analysis(brand: str, therapy_area: str, lifecycle_key: str, budget: float = 0) -> dict:
    inferred = infer_persona_and_stage(lifecycle_key)
    persona, stage_key = inferred["persona"], inferred["stage_key"]

    market = market_landscape(brand, therapy_area)

    discovered_competitors = discover_competitors(therapy_area, brand, limit=5)

    brief_grounding = process_knowledge.brief_grounding(brand, therapy_area)
    strategy = generate_strategy(brand, therapy_area, persona, stage_key, brief_grounding)

    swot_result = build_swot(brand, discovered_competitors, therapy_area, refresh=True) if discovered_competitors else None

    positioning = build_positioning_statement(brand, therapy_area, persona, stage_key, discovered_competitors)

    channel_mix = strategy["channel_mix_pct"]
    budget_allocation = {
        ch: {"pct": pct, "amount": round(budget * pct / 100, 2) if budget else None}
        for ch, pct in channel_mix.items()
    }

    kpi_framework = build_kpi_framework(stage_key, channel_mix)

    return {
        "inferred_inputs": {
            "persona": persona,
            "stage_key": stage_key,
            "stage_label": strategy["inputs"]["stage"],
            "lifecycle_label": inferred["lifecycle_label"],
            "lifecycle_rationale": inferred["rationale"],
            "discovered_competitors": discovered_competitors,
        },
        "stage_1_market_landscape": market,
        "stage_2_4_strategy": strategy,
        "stage_1b_3_competitive": swot_result,
        "stage_3_positioning": positioning,
        "stage_5_budget": {
            "total_budget": budget or None,
            "allocation": budget_allocation,
            "caveat": strategy["caveat"],
        },
        "stage_7_kpi": kpi_framework,
        "stage_8_risk_governance": {
            "standard_risks": STANDARD_RISKS,
            "governance_cadence": GOVERNANCE_CADENCE,
        },
        "caveat": (
            "Persona, journey stage, and competitors were all auto-inferred from the lifecycle phase and "
            "therapy area -- review the 'inferred_inputs' block and override any of them manually if this "
            "doesn't match your real segmentation or competitive set."
        ),
    }
