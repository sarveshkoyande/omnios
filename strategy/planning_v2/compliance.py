"""Phase 6 — Compliance validator.

Runs as a SEPARATE pass over an already-synthesized `TacticalPlan`, per the
brief's explicit instruction not to trust the generation step to self-police.
Deliberately mechanical/deterministic (regex + structural checks over the
pydantic objects), not a second LLM call asking the same model to grade its
own output — a fixed rule either matches or it doesn't, which is exactly the
property a compliance gate needs: no risk of the same blind spot that
produced a bad section also excusing it on review.

Enforces, per the brief:
  1. Commercial/medical firewall across every section.
  2. First-line, combination, and investigational content routed to Medical only.
  3. Fair balance + full ISI on every branded efficacy claim.
  4. Patient-facing tactics held gated until required inputs exist.
  5. Dosing / drug-interaction statements suppressed until resolved against the PI.
  6. Every budget/volume/share/KPI figure marked as a placeholder, never invented as fact.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from strategy.planning_v2.models import StrategicContext, TacticalPlan, TacticalSection

Severity = Literal["blocker", "warning"]


class ComplianceFinding(BaseModel):
    rule: str
    severity: Severity
    location: str
    message: str


class ComplianceReport(BaseModel):
    findings: list[ComplianceFinding] = Field(default_factory=list)

    @property
    def blockers(self) -> list[ComplianceFinding]:
        return [f for f in self.findings if f.severity == "blocker"]

    @property
    def passed(self) -> bool:
        return not self.blockers


# --------------------------------------------------------------------------- #
# Regulated-language patterns
# --------------------------------------------------------------------------- #

_MEDICAL_ONLY_TERMS = re.compile(
    r"\b(first[- ]line|1L\b|combination therapy|combo(?:\s|-)?(?:therapy|regimen)|"
    r"investigational|unapproved|off-label|off label)\b", re.IGNORECASE,
)
_DOSING_TERMS = re.compile(
    r"\b(dosing|dose|dosage|\d+\s?mg\b|drug[- ]interaction|contraindicat\w*)\b", re.IGNORECASE,
)
_EFFICACY_CLAIM_TERMS = re.compile(
    r"\b(efficacy|response rate|overall survival|progression[- ]free survival|\bORR\b|\bPFS\b|\bOS\b|"
    r"superior(?:ity)?|reduces?|improves?|(?:\d+%\s?(?:reduction|improvement|response)))\b", re.IGNORECASE,
)
_FIGURE_LOOKING = re.compile(r"[$€£]\s?\d[\d,]*|\b\d{1,3}%\b|\b\d[\d,]*\s?(?:reps?|HCPs?|patients?)\b", re.IGNORECASE)

# Sections whose content is field/commercial-facing by construction — a medical-only term
# found here is a firewall breach, not just a routing reminder.
_COMMERCIAL_SECTIONS = {
    "field_approach", "account_strategy", "account_focus", "targeting_matrix",
    "content_inventory", "trigger_based_engagement", "media_flighting",
}
# Sections that are Medical/MSL-owned by construction — regulated terms here still need a
# checkpoint, but are expected content rather than a firewall breach.
_MEDICAL_SECTIONS = {"congress_scientific_exchange", "peer_to_peer"}


def _section_text(name: str, section: TacticalSection) -> str:
    import json

    return f"{section.summary}\n{json.dumps(section.items)}"


def _iter_sections(plan: TacticalPlan) -> list[tuple[str, TacticalSection]]:
    out: list[tuple[str, TacticalSection]] = []
    for name, field_info in TacticalPlan.model_fields.items():
        if name in {"omnichannel_strategy", "measurement", "patient_strategy", "appendices", "provenance",
                     "strategic_recap", "investment_thesis"}:
            continue
        value = getattr(plan, name)
        if isinstance(value, TacticalSection):
            out.append((name, value))
    return out


def _check_firewall_and_routing(plan: TacticalPlan) -> list[ComplianceFinding]:
    findings: list[ComplianceFinding] = []
    for name, section in _iter_sections(plan):
        text = _section_text(name, section)
        hits = sorted(set(m.group(0).lower() for m in _MEDICAL_ONLY_TERMS.finditer(text)))
        if not hits:
            continue
        if name in _COMMERCIAL_SECTIONS:
            findings.append(ComplianceFinding(
                rule="commercial_medical_firewall", severity="blocker", location=name,
                message=f"Commercial-facing section contains medical-only language {hits} — "
                        "first-line/combination/investigational content must route to Medical, not Commercial.",
            ))
        elif name in _MEDICAL_SECTIONS:
            findings.append(ComplianceFinding(
                rule="medical_only_routing", severity="warning", location=name,
                message=f"Contains medical-only language {hits} — confirm this section stays "
                        "MSL/Medical-owned and is not repurposed for field/commercial use.",
            ))
        else:
            findings.append(ComplianceFinding(
                rule="medical_only_routing", severity="blocker", location=name,
                message=f"Section contains medical-only language {hits} but is not a recognized "
                        "Medical-owned section — route to Medical before use.",
            ))
    return findings


def _check_dosing(plan: TacticalPlan) -> list[ComplianceFinding]:
    findings: list[ComplianceFinding] = []
    for name, section in _iter_sections(plan):
        text = _section_text(name, section)
        hits = sorted(set(m.group(0).lower() for m in _DOSING_TERMS.finditer(text)))
        if hits:
            findings.append(ComplianceFinding(
                rule="dosing_drug_interaction_suppression", severity="blocker", location=name,
                message=f"Contains dosing/drug-interaction language {hits} — suppress until resolved "
                        "against the approved Prescribing Information (PI) with Medical/Regulatory sign-off.",
            ))
    return findings


def _check_fair_balance(plan: TacticalPlan, sco: StrategicContext) -> list[ComplianceFinding]:
    findings: list[ComplianceFinding] = []
    has_fair_balance_reqs = any(ev.fair_balance_requirements for ev in sco.evidence)
    for name, section in _iter_sections(plan):
        text = _section_text(name, section)
        if _EFFICACY_CLAIM_TERMS.search(text):
            if not has_fair_balance_reqs:
                findings.append(ComplianceFinding(
                    rule="fair_balance_isi", severity="blocker", location=name,
                    message="Section makes an efficacy-shaped claim but the strategic context has no "
                            "fair_balance_requirements on file for any evidence item — every branded "
                            "efficacy claim needs fair balance + full ISI paired with it.",
                ))
            elif not section.guardrails:
                findings.append(ComplianceFinding(
                    rule="fair_balance_isi", severity="warning", location=name,
                    message="Section makes an efficacy-shaped claim; confirm fair balance + full ISI "
                            "is attached at render time — no guardrail is recorded on this section.",
                ))
    return findings


def _check_patient_gating(plan: TacticalPlan, sco: StrategicContext) -> list[ComplianceFinding]:
    findings: list[ComplianceFinding] = []
    patient_audiences = [a for a in sco.audiences if a.role == "patient"]
    sco_gated = any(a.gating_status == "gated" for a in patient_audiences) if patient_audiences else True
    if sco_gated and not plan.patient_strategy.gated:
        findings.append(ComplianceFinding(
            rule="patient_gating", severity="blocker", location="patient_strategy",
            message="Strategic context marks the patient audience as gated, but the tactical plan's "
                    "patient_strategy.gated is False — patient-facing tactics must stay held until the "
                    "required inputs exist.",
        ))
    if plan.patient_strategy.gated and plan.patient_strategy.items:
        findings.append(ComplianceFinding(
            rule="patient_gating", severity="blocker", location="patient_strategy",
            message="patient_strategy is gated but still lists active tactical items — a gated section "
                    "must not populate executable patient-facing tactics.",
        ))
    if plan.patient_strategy.gated and not plan.patient_strategy.gating_logic:
        findings.append(ComplianceFinding(
            rule="patient_gating", severity="warning", location="patient_strategy",
            message="patient_strategy is gated but gating_logic is empty — state what must clear "
                    "before patient tactics activate.",
        ))
    return findings


def _check_placeholders(plan: TacticalPlan) -> list[ComplianceFinding]:
    findings: list[ComplianceFinding] = []
    for m in plan.measurement:
        for kpi_name, pv in m.targets.items():
            loc = f"measurement.{m.csf_id}.{kpi_name}"
            if pv.value is None:
                continue
            if not pv.is_placeholder:
                if not pv.note:
                    findings.append(ComplianceFinding(
                        rule="figures_must_be_placeholders", severity="blocker", location=loc,
                        message=f"Target {kpi_name}={pv.value!r} is marked non-placeholder with no "
                                "note justifying the source — every KPI/budget/volume/share figure must "
                                "either be a flagged placeholder or cite where the real number came from.",
                    ))
            elif not pv.note:
                findings.append(ComplianceFinding(
                    rule="figures_must_be_placeholders", severity="warning", location=loc,
                    message=f"Target {kpi_name} is a placeholder with no note — add a short reason "
                            "(e.g. 'requires brand-team data').",
                ))
    # Freeform sections can still smuggle a raw figure into prose ("$2M budget", "15% lift") that
    # never passed through the modeled PlaceholderValue type at all — those are worse than an
    # unlabeled placeholder, they look like asserted fact. Flag every one found.
    for name, section in _iter_sections(plan):
        text = _section_text(name, section)
        hits = sorted(set(_FIGURE_LOOKING.findall(text)))
        if hits:
            findings.append(ComplianceFinding(
                rule="figures_must_be_placeholders", severity="blocker", location=name,
                message=f"Section states figure(s) {hits} as plain text outside the modeled "
                        "PlaceholderValue type — every budget/volume/share/KPI figure must render as "
                        "a placeholder requiring brand-team data, never as asserted fact in free text.",
            ))
    return findings


def validate(plan: TacticalPlan, sco: StrategicContext) -> ComplianceReport:
    findings: list[ComplianceFinding] = []
    findings += _check_firewall_and_routing(plan)
    findings += _check_dosing(plan)
    findings += _check_fair_balance(plan, sco)
    findings += _check_patient_gating(plan, sco)
    findings += _check_placeholders(plan)
    return ComplianceReport(findings=findings)
