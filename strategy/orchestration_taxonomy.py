"""Engagement Orchestration -- governed activity taxonomy + activity-type registry.

The single source of truth for *how an orchestration activity is classified*. Two things live
here:

1. TAG_DIMENSIONS -- the controlled, multi-dimensional tag vocabulary every activity is tagged
   against (team / function / channel / asset type / campaign phase / compliance tier /
   automation class / risk). Governed, not free-text: the known failure mode in pharma
   marketing ops is inconsistent, siloed tagging, so the allowed values are enumerated here and
   the frontend + downstream field-maps read from the same list.

2. ACTIVITY_TYPES -- the registry that maps each derivation *category* produced by
   orchestration_tasks.generate_tasks() onto a richer activity-type record: its campaign phase,
   its scheduling order, its default automation class, its compliance tier / hard-gate kind, a
   default asset type, and default risk. orchestration_sla.py keys its day-count SLAs off the
   same activity-type ids.

Grounding: the compliance tiers and the AE/MIR / MLR / consent / ISI / AFU gate kinds, and the
"heavily-assisted vs fully-agentified vs human-gated" automation axis, come from the vault's
SFMC Campaign Value Chain & Agentification Blueprint ("agents orchestrate; MLR originates").
See PRD-Orchestration-Phase.md sections 6.2 and 6.9.
"""
from __future__ import annotations

# --- Tag dimensions (governed vocabulary) -----------------------------------------------------

# Campaign phase -- also the scheduler's precedence order (planning -> ... -> wrap).
PHASE_PLANNING = "planning"
PHASE_PRODUCTION = "production"
PHASE_REVIEW = "review"
PHASE_EXECUTION = "execution"
PHASE_WRAP = "wrap"
PHASE_ORDER = [PHASE_PLANNING, PHASE_PRODUCTION, PHASE_REVIEW, PHASE_EXECUTION, PHASE_WRAP]

# Automation class -- Sanket's "heavily assisted vs fully agentified" axis, plus the human-gated
# case for anything a person/compliance function must decide.
AUTO_FULL = "fully-agentified"       # can leave human hands entirely (SQL gen, dedup, tagging)
AUTO_ASSISTED = "heavily-assisted"   # automated but needs human judgement/sign-off
AUTO_HUMAN = "human-gated"           # a person/compliance function must decide; never agent-closed

# Compliance tier -- rigor matched to material risk.
TIER_NONE = "none"
TIER_LIGHT = "light"
TIER_FULL_MLR = "full-MLR"

# Hard-gate kinds -- routable + trackable, NEVER agent-closable (PRD F9). None = no hard gate.
GATE_MLR = "MLR"          # medical/legal/regulatory review (a.k.a. PRC/CRC)
GATE_CONSENT = "CONSENT"  # consent basis present + in-date
GATE_ISI = "ISI"          # ISI / fair-balance present in rendered asset
GATE_AFU = "AFU"          # approved-for-use asset + job-code binding
GATE_AE_MIR = "AE_MIR"    # adverse-event / medical-information / off-label routing (~24h SLA)

TAG_DIMENSIONS: dict[str, list[str]] = {
    "team": [
        "Web team",
        "Content & derivative assets team",
        "Campaign operations team",
        "Data & data cloud team",
        "Reporting & insights team",
        "MLR / Regulatory / Medical",
    ],
    "channel": ["email", "web", "paid-social", "display", "search", "field/rep", "event", "portal", "ehr"],
    "asset_type": ["email", "banner", "landing-page", "video", "pdf/iva", "social-post", "journey", "report", "audience", "config", "none"],
    "phase": PHASE_ORDER,
    "compliance_tier": [TIER_NONE, TIER_LIGHT, TIER_FULL_MLR],
    "automation_class": [AUTO_FULL, AUTO_ASSISTED, AUTO_HUMAN],
    "risk": ["low", "medium", "high"],
}


def is_valid_tag(dimension: str, value: str) -> bool:
    """Governance check: reject any tag value not in the controlled vocabulary."""
    return dimension in TAG_DIMENSIONS and value in TAG_DIMENSIONS[dimension]


# --- Activity-type registry -------------------------------------------------------------------

# Keyed by the derivation *category* that orchestration_tasks.generate_tasks() already emits, so
# the enrichment pass is a pure lookup and Stage 1/Stage 2 never disagree. Each record:
#   activity_type   -- stable id the SLA library keys off
#   phase           -- campaign-phase tag + scheduler precedence bucket
#   automation      -- default automation class
#   tier            -- default compliance tier
#   gate            -- hard-gate kind or None
#   asset_type      -- default asset-type tag
#   risk            -- default risk tag
ACTIVITY_TYPES: dict[str, dict] = {
    "Touchpoint setup": {
        "activity_type": "touchpoint_build", "phase": PHASE_PRODUCTION,
        "automation": AUTO_ASSISTED, "tier": TIER_LIGHT, "gate": None,
        "asset_type": "email", "risk": "medium",
    },
    "Journey logic": {
        "activity_type": "journey_config", "phase": PHASE_EXECUTION,
        "automation": AUTO_FULL, "tier": TIER_NONE, "gate": None,
        "asset_type": "journey", "risk": "medium",
    },
    "Segmentation": {
        # vault correction: segmentation is an audience-BUILD activity, not a reporting one.
        "activity_type": "audience_build", "phase": PHASE_PRODUCTION,
        "automation": AUTO_ASSISTED, "tier": TIER_LIGHT, "gate": GATE_CONSENT,
        "asset_type": "audience", "risk": "high",
    },
    "Content & tactics": {
        "activity_type": "content_production", "phase": PHASE_PRODUCTION,
        "automation": AUTO_HUMAN, "tier": TIER_FULL_MLR, "gate": GATE_MLR,
        "asset_type": "email", "risk": "high",
    },
    "Tactical plan (CSFs)": {
        "activity_type": "tactical_activation", "phase": PHASE_PLANNING,
        "automation": AUTO_ASSISTED, "tier": TIER_NONE, "gate": None,
        "asset_type": "config", "risk": "medium",
    },
    "Scientific engagement": {
        "activity_type": "scientific_content", "phase": PHASE_REVIEW,
        "automation": AUTO_HUMAN, "tier": TIER_FULL_MLR, "gate": GATE_MLR,
        "asset_type": "pdf/iva", "risk": "high",
    },
    "Account & pathway": {
        "activity_type": "account_pathway", "phase": PHASE_PLANNING,
        "automation": AUTO_ASSISTED, "tier": TIER_LIGHT, "gate": None,
        "asset_type": "config", "risk": "medium",
    },
    "Patient & support": {
        # the recurring regulatory/legal patient gate -- human-gated by construction.
        "activity_type": "patient_gate", "phase": PHASE_REVIEW,
        "automation": AUTO_HUMAN, "tier": TIER_FULL_MLR, "gate": GATE_MLR,
        "asset_type": "none", "risk": "high",
    },
    "Measurement": {
        "activity_type": "measurement_setup", "phase": PHASE_WRAP,
        "automation": AUTO_ASSISTED, "tier": TIER_NONE, "gate": None,
        "asset_type": "report", "risk": "low",
    },
    "Custom": {
        "activity_type": "custom", "phase": PHASE_PRODUCTION,
        "automation": AUTO_ASSISTED, "tier": TIER_NONE, "gate": None,
        "asset_type": "none", "risk": "medium",
    },
}


def registry_for(category: str) -> dict:
    """Activity-type record for a derivation category, defaulting to Custom for anything new."""
    return ACTIVITY_TYPES.get(category, ACTIVITY_TYPES["Custom"])


def phase_rank(phase: str) -> int:
    """Scheduler precedence index for a campaign phase (lower runs earlier)."""
    return PHASE_ORDER.index(phase) if phase in PHASE_ORDER else len(PHASE_ORDER)
