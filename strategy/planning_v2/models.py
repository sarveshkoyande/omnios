"""Phase 1 — the four core data objects that form the contract between every
pipeline stage: StrategicContext, TacticalPlan, Gap, BusinessRequirementsBrief.

Design notes
------------
* Every fact-bearing object carries a `provenance` dict keyed by dotted field
  path (e.g. "market_landscape.prevalence", "critical_success_factors[1]")
  mapping to a list of `ProvenanceRef`. This is how stage 2/3 record *where*
  a value came from (document page/section, knowledge-graph note, market
  signal, or an expert prior asserted by the LLM) and is what lets the gap
  analyzer in stage 4 tell "present" apart from "inferable" apart from "true
  gap" without re-deriving it.
* `PlaceholderValue` is the type every budget/volume/share/KPI figure in the
  TacticalPlan must use. It exists so the compliance validator (Phase 6) can
  mechanically find every number that must never be presented as fact and
  confirm it is flagged, rather than trusting the generation step to
  self-police (per the brief's explicit requirement).
* All models are pydantic v2 `BaseModel`s so validation is structural, not
  advisory: a StrategicContext or TacticalPlan that fails to construct is a
  bug in the stage that produced it, caught immediately rather than surfacing
  as a downstream KeyError three stages later.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

# --------------------------------------------------------------------------- #
# Shared primitives
# --------------------------------------------------------------------------- #

SourceType = Literal["document", "knowledge_graph", "market_signals", "expert_prior"]


class ProvenanceRef(BaseModel):
    """Where one fact came from. `source_id` is a page/section ref for a
    document, a note title/path for the knowledge graph, a dataset/series id
    for market signals, or a short rationale for an expert prior (expert
    priors are not "sources found" — they must be labeled as such so a human
    reviewer can tell inference from citation)."""

    source_type: SourceType
    source_id: str = ""
    detail: str = ""
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class PlaceholderValue(BaseModel):
    """A budget/volume/share/KPI figure. `is_placeholder=True` means the
    number is illustrative/estimated and must render as a placeholder
    requiring brand-team data, never as fact — this is what Phase 6's
    compliance validator scans for."""

    value: float | int | str | None = None
    is_placeholder: bool = True
    note: str = ""

    @model_validator(mode="after")
    def _placeholder_needs_note(self) -> "PlaceholderValue":
        if self.is_placeholder and not self.note:
            self.note = "Requires brand-team data; not yet supplied."
        return self


def _provenance_field() -> dict[str, list[ProvenanceRef]]:
    return {}


# --------------------------------------------------------------------------- #
# Strategic Context Object
# --------------------------------------------------------------------------- #


class Brand(BaseModel):
    name: str
    molecule: str = ""
    indication: str = ""
    modality: str = ""


class StrategicImperative(BaseModel):
    imperative: str
    definition: str = ""


class MarketLandscape(BaseModel):
    disease: str = ""
    prevalence: str = ""
    standard_of_care: str = ""
    prognosis: str = ""
    competitive_class: str = ""


class CompetitiveDynamics(BaseModel):
    class_context: str = ""
    differentiation: str = ""
    comparison_guardrails: list[str] = Field(default_factory=list)


class CriticalSuccessFactor(BaseModel):
    id: str
    key_insight: str
    strategies: list[str] = Field(default_factory=list)
    tactical_focus: list[str] = Field(default_factory=list)
    guardrail: str = ""


GatingStatus = Literal["open", "gated", "not_applicable"]


class AudienceProfile(BaseModel):
    role: Literal["hcp", "pathology", "nurse_and_app", "medical", "patient"]
    description: str = ""
    needs: list[str] = Field(default_factory=list)
    gating_status: GatingStatus = "open"
    gating_reason: str = ""

    @model_validator(mode="after")
    def _patient_must_state_gating(self) -> "AudienceProfile":
        if self.role == "patient" and self.gating_status == "gated" and not self.gating_reason:
            raise ValueError("gated patient audience must state gating_reason")
        return self


class AccountArchetype(BaseModel):
    type: str
    role: str = ""
    characteristics: list[str] = Field(default_factory=list)


class EvidenceItem(BaseModel):
    trial_design: str = ""
    endpoints: list[str] = Field(default_factory=list)
    values: dict[str, str] = Field(default_factory=dict)
    fair_balance_requirements: list[str] = Field(default_factory=list)


class StrategicContext(BaseModel):
    """Output of stage 2 (Extract) + stage 3 (Enrich)."""

    brand: Brand
    strategic_focus: list[StrategicImperative] = Field(default_factory=list)
    market_landscape: MarketLandscape = Field(default_factory=MarketLandscape)
    competitive_dynamics: CompetitiveDynamics = Field(default_factory=CompetitiveDynamics)
    challenges: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    critical_success_factors: list[CriticalSuccessFactor] = Field(default_factory=list)
    audiences: list[AudienceProfile] = Field(default_factory=list)
    account_archetypes: list[AccountArchetype] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)

    provenance: dict[str, list[ProvenanceRef]] = Field(default_factory=_provenance_field)

    @model_validator(mode="after")
    def _csf_ids_unique(self) -> "StrategicContext":
        ids = [c.id for c in self.critical_success_factors]
        if len(ids) != len(set(ids)):
            raise ValueError("critical_success_factors ids must be unique")
        return self


# --------------------------------------------------------------------------- #
# Tactical Plan Object
# --------------------------------------------------------------------------- #


class TacticalSection(BaseModel):
    """Uniform shape for the tactical-plan sections the brief names but does
    not itself sub-structure (flighting, field_approach, targeting_matrix,
    media_flighting, trigger_based_engagement, content_inventory,
    congress_scientific_exchange, peer_to_peer, nurse_app_education,
    account_strategy, account_focus, testing_enablement_digital). Keeping
    these uniform is what lets gap analysis, synthesis, and the compliance
    validator walk the whole TacticalPlan generically instead of needing a
    bespoke case per section."""

    summary: str = ""
    items: list[dict[str, Any]] = Field(default_factory=list)
    csf_mapping: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


class OmnichannelChannel(BaseModel):
    channel: str
    role: str = ""
    branded_or_unbranded: Literal["branded", "unbranded", "both"] = "branded"
    csf_mapping: list[str] = Field(default_factory=list)


class MeasurementIndicator(BaseModel):
    csf_id: str
    leading_indicators: list[str] = Field(default_factory=list)
    lagging_indicators: list[str] = Field(default_factory=list)
    targets: dict[str, PlaceholderValue] = Field(default_factory=dict)


class PatientStrategy(BaseModel):
    summary: str = ""
    items: list[dict[str, Any]] = Field(default_factory=list)
    gated: bool = True
    gating_logic: str = ""

    @model_validator(mode="after")
    def _gated_needs_logic(self) -> "PatientStrategy":
        if self.gated and not self.gating_logic:
            self.gating_logic = "Gated pending required patient-facing inputs (see open gaps)."
        return self


class PlanAppendices(BaseModel):
    competitive_context: str = ""
    measurement: str = ""
    guardrails_recap: list[str] = Field(default_factory=list)


class TacticalPlan(BaseModel):
    """Output of stage 6 (Synthesize)."""

    strategic_recap: str = ""
    investment_thesis: str = ""
    flighting: TacticalSection = Field(default_factory=TacticalSection)
    field_approach: TacticalSection = Field(default_factory=TacticalSection)
    targeting_matrix: TacticalSection = Field(default_factory=TacticalSection)
    omnichannel_strategy: list[OmnichannelChannel] = Field(default_factory=list)
    media_flighting: TacticalSection = Field(default_factory=TacticalSection)
    trigger_based_engagement: TacticalSection = Field(default_factory=TacticalSection)
    content_inventory: TacticalSection = Field(default_factory=TacticalSection)
    congress_scientific_exchange: TacticalSection = Field(default_factory=TacticalSection)
    peer_to_peer: TacticalSection = Field(default_factory=TacticalSection)
    nurse_app_education: TacticalSection = Field(default_factory=TacticalSection)
    account_strategy: TacticalSection = Field(default_factory=TacticalSection)
    account_focus: TacticalSection = Field(default_factory=TacticalSection)
    patient_strategy: PatientStrategy = Field(default_factory=PatientStrategy)
    testing_enablement_digital: TacticalSection = Field(default_factory=TacticalSection)
    measurement: list[MeasurementIndicator] = Field(default_factory=list)
    appendices: PlanAppendices = Field(default_factory=PlanAppendices)

    provenance: dict[str, list[ProvenanceRef]] = Field(default_factory=_provenance_field)


# --------------------------------------------------------------------------- #
# Gap Object
# --------------------------------------------------------------------------- #


class Gap(BaseModel):
    """Output of stage 4 (Gap analysis); non-inferable gaps feed stage 5
    (Pointed questions)."""

    field: str
    tactical_section_blocked: str
    why_needed: str
    inferable: bool
    sources_attempted: list[SourceType] = Field(default_factory=list)
    question: str | None = None
    suggested_default: str | None = None
    impact_rank: int = Field(ge=1)

    @model_validator(mode="after")
    def _question_only_if_not_inferable(self) -> "Gap":
        if not self.inferable and not self.question:
            raise ValueError(
                f"gap on '{self.field}' is not inferable but carries no question "
                "(stage 5 rule: every true gap must be turned into a question)"
            )
        if self.inferable and self.question:
            raise ValueError(
                f"gap on '{self.field}' is marked inferable but still carries a question "
                "(inferable gaps must be resolved by stage 3/4, not asked)"
            )
        return self


# --------------------------------------------------------------------------- #
# Business Requirements Brief Object
# --------------------------------------------------------------------------- #


class Workstream(BaseModel):
    name: str
    tactical_sections: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(default_factory=list)
    proposed_owning_team: str = ""
    dependencies: list[str] = Field(default_factory=list)
    parallelizable: bool = True
    suggested_sla: str = ""


class ComplianceCheckpoint(BaseModel):
    checkpoint_type: Literal["mlr_gate", "firewall_point"]
    location: str
    description: str = ""


class BusinessRequirementsBrief(BaseModel):
    """Output of stage 6 (Synthesize); emitted as-is at stage 7 (Handoff) to
    orchestration."""

    initiative_summary: str = ""
    workstreams: list[Workstream] = Field(default_factory=list)
    compliance_checkpoints: list[ComplianceCheckpoint] = Field(default_factory=list)

    @model_validator(mode="after")
    def _workstreams_have_sections(self) -> "BusinessRequirementsBrief":
        for ws in self.workstreams:
            if not ws.tactical_sections:
                raise ValueError(f"workstream '{ws.name}' maps to no tactical_sections")
        return self
