"""Phase 1 runnable proof: construct one valid instance of each of the four
core objects, round-trip through JSON, and confirm the validators that
enforce the brief's hard rules actually reject bad input.

Run: python -m strategy.planning_v2.selftest_phase1
"""
from __future__ import annotations

from pydantic import ValidationError

from strategy.planning_v2.models import (
    AudienceProfile,
    Brand,
    BusinessRequirementsBrief,
    ComplianceCheckpoint,
    CriticalSuccessFactor,
    Gap,
    MarketLandscape,
    OmnichannelChannel,
    ProvenanceRef,
    StrategicContext,
    StrategicImperative,
    TacticalPlan,
    Workstream,
)


def build_strategic_context() -> StrategicContext:
    return StrategicContext(
        brand=Brand(name="Oncomyra", molecule="talrenimab", indication="2L NSCLC", modality="mAb"),
        strategic_focus=[StrategicImperative(imperative="Establish 2L standard", definition="Shift SoC before 3L erosion")],
        market_landscape=MarketLandscape(
            disease="NSCLC", prevalence="~236,000 new US cases/yr", standard_of_care="platinum doublet",
            prognosis="poor beyond 2L", competitive_class="checkpoint inhibitors",
        ),
        critical_success_factors=[
            CriticalSuccessFactor(id="csf1", key_insight="Oncologists under-refer at progression",
                                    strategies=["Peer-to-peer progression signal education"],
                                    tactical_focus=["peer_to_peer", "congress_scientific_exchange"],
                                    guardrail="No unapproved combination claims"),
        ],
        audiences=[
            AudienceProfile(role="hcp", description="Community oncologists", needs=["progression signals"]),
            AudienceProfile(role="patient", description="Newly progressed patients", gating_status="gated",
                             gating_reason="Patient materials not yet MLR-approved"),
        ],
        provenance={
            "brand.name": [ProvenanceRef(source_type="document", source_id="p.1", detail="title page")],
        },
    )


def build_gap() -> Gap:
    return Gap(
        field="media_flighting.budget",
        tactical_section_blocked="media_flighting",
        why_needed="Flight sequencing cannot be costed without a budget ceiling",
        inferable=False,
        sources_attempted=["document", "knowledge_graph", "market_signals"],
        question="What is the confirmed FY media budget ceiling for this brand?",
        suggested_default="Use prior-year budget as placeholder",
        impact_rank=1,
    )


def build_tactical_plan() -> TacticalPlan:
    return TacticalPlan(
        strategic_recap="2L NSCLC access play built on peer-to-peer progression education.",
        omnichannel_strategy=[
            OmnichannelChannel(channel="Peer-to-peer webinar", role="Drive progression-signal awareness",
                                branded_or_unbranded="branded", csf_mapping=["csf1"]),
        ],
    )


def build_brb() -> BusinessRequirementsBrief:
    return BusinessRequirementsBrief(
        initiative_summary="Stand up 2L progression-signal peer education program.",
        workstreams=[
            Workstream(name="Peer-to-peer program build", tactical_sections=["peer_to_peer"],
                       deliverables=["Speaker deck", "MSL briefing doc"], proposed_owning_team="Field Medical",
                       dependencies=["MLR pre-clearance of speaker deck"], parallelizable=True,
                       suggested_sla="4 weeks"),
        ],
        compliance_checkpoints=[
            ComplianceCheckpoint(checkpoint_type="mlr_gate", location="peer_to_peer.speaker_deck",
                                  description="Speaker deck requires MLR sign-off before first program"),
        ],
    )


def main() -> None:
    sco = build_strategic_context()
    gap = build_gap()
    plan = build_tactical_plan()
    brb = build_brb()

    for label, obj in [("StrategicContext", sco), ("Gap", gap), ("TacticalPlan", plan), ("BusinessRequirementsBrief", brb)]:
        payload = obj.model_dump_json()
        obj.model_validate_json(payload)
        print(f"OK  {label:28s} round-tripped, {len(payload)} bytes")

    # Hard-rule checks: these MUST fail.
    failures = 0

    try:
        Gap(field="x", tactical_section_blocked="y", why_needed="z", inferable=False,
            impact_rank=1)  # no question -> must raise
        failures += 1
        print("FAIL Gap accepted a non-inferable gap with no question")
    except ValidationError:
        print("OK   Gap rejects non-inferable gap missing a question")

    try:
        Gap(field="x", tactical_section_blocked="y", why_needed="z", inferable=True,
            question="should not be here", impact_rank=1)  # inferable + question -> must raise
        failures += 1
        print("FAIL Gap accepted an inferable gap that still carries a question")
    except ValidationError:
        print("OK   Gap rejects inferable gap that still carries a question")

    try:
        AudienceProfile(role="patient", gating_status="gated", gating_reason="")  # gated w/o reason -> must raise
        failures += 1
        print("FAIL AudienceProfile accepted a gated patient audience with no gating_reason")
    except ValidationError:
        print("OK   AudienceProfile rejects gated patient audience missing gating_reason")

    try:
        BusinessRequirementsBrief(workstreams=[Workstream(name="orphan", tactical_sections=[])])
        failures += 1
        print("FAIL BusinessRequirementsBrief accepted a workstream mapped to no tactical_sections")
    except ValidationError:
        print("OK   BusinessRequirementsBrief rejects workstream mapped to no tactical_sections")

    if failures:
        raise SystemExit(f"{failures} validator(s) failed to enforce the brief's hard rules")
    print("\nPhase 1: all four core objects construct, validate, and round-trip clean.")


if __name__ == "__main__":
    main()
