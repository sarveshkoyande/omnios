"""Phase 6 runnable proof: construct a deliberately non-compliant TacticalPlan and confirm
the validator catches every rule category, then confirm a clean plan passes.

Run: python -m strategy.planning_v2.selftest_phase6
"""
from __future__ import annotations

from strategy.planning_v2.compliance import validate
from strategy.planning_v2.models import (
    AudienceProfile,
    Brand,
    EvidenceItem,
    MeasurementIndicator,
    PatientStrategy,
    PlaceholderValue,
    StrategicContext,
    TacticalPlan,
    TacticalSection,
)


def _sco(patient_gated: bool = True, with_fair_balance: bool = True) -> StrategicContext:
    return StrategicContext(
        brand=Brand(name="Oncomyra", molecule="talrenimab", indication="2L NSCLC"),
        audiences=[
            AudienceProfile(role="patient", gating_status="gated" if patient_gated else "open",
                             gating_reason="Materials not yet MLR-approved" if patient_gated else ""),
        ],
        evidence=[EvidenceItem(fair_balance_requirements=["Pair every efficacy claim with the boxed warning"])]
        if with_fair_balance else [],
    )


def dirty_plan() -> TacticalPlan:
    return TacticalPlan(
        field_approach=TacticalSection(
            summary="Reps discuss first-line combination therapy use with oncologists.",
            csf_mapping=["csf1"],
        ),
        content_inventory=TacticalSection(
            summary="Leave-behind claims 40% reduction in progression and cites a $2M media budget.",
            csf_mapping=["csf1"],
        ),
        peer_to_peer=TacticalSection(
            summary="MSL discusses recommended dosing adjustments for renal impairment.",
            csf_mapping=["csf1"],
        ),
        congress_scientific_exchange=TacticalSection(
            summary="MSLs present emerging investigational combination data at oncology congresses.",
            csf_mapping=["csf1"],
        ),
        patient_strategy=PatientStrategy(gated=False, items=[{"tactic": "patient email nurture"}]),
        measurement=[MeasurementIndicator(
            csf_id="csf1", leading_indicators=["engagement rate"],
            targets={"nrx_lift": PlaceholderValue(value=15, is_placeholder=False, note="")},
        )],
    )


def clean_plan() -> TacticalPlan:
    return TacticalPlan(
        field_approach=TacticalSection(summary="Reps deliver approved-label peer education materials.",
                                        csf_mapping=["csf1"], guardrails=["Stay within approved label"]),
        congress_scientific_exchange=TacticalSection(
            summary="MSLs present pivotal trial efficacy data at oncology congresses.",
            csf_mapping=["csf1"], guardrails=["Fair balance + full ISI on every slide"],
        ),
        patient_strategy=PatientStrategy(gated=True, items=[], gating_logic="Held until MLR clears patient materials."),
        measurement=[MeasurementIndicator(
            csf_id="csf1", leading_indicators=["engagement rate"],
            targets={"nrx_lift": PlaceholderValue(value=15, is_placeholder=True, note="Requires brand-team data.")},
        )],
    )


def main() -> None:
    report = validate(dirty_plan(), _sco())
    rules_hit = {f.rule for f in report.findings}
    print(f"DIRTY plan: {len(report.findings)} findings, {len(report.blockers)} blockers")
    for f in report.findings:
        print(f"  [{f.severity}] {f.rule} @ {f.location}: {f.message[:100]}")

    expected_rules = {
        "commercial_medical_firewall", "medical_only_routing", "dosing_drug_interaction_suppression",
        "fair_balance_isi", "patient_gating", "figures_must_be_placeholders",
    }
    missing = expected_rules - rules_hit
    assert not missing, f"compliance validator failed to catch rule categories: {missing}"
    assert not report.passed, "dirty plan should not pass"
    print(f"\nOK  all {len(expected_rules)} rule categories fired on the dirty plan")

    clean_report = validate(clean_plan(), _sco())
    print(f"\nCLEAN plan: {len(clean_report.findings)} findings, {len(clean_report.blockers)} blockers")
    for f in clean_report.findings:
        print(f"  [{f.severity}] {f.rule} @ {f.location}: {f.message[:100]}")
    assert clean_report.passed, f"clean plan should pass with no blockers, got: {clean_report.blockers}"
    print("OK  clean plan passes with zero blockers")


if __name__ == "__main__":
    main()
