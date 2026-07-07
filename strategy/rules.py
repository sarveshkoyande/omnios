"""
Static rule tables encoding the frameworks from
'Omni OS -- Campaign Planning & Strategy Deep Dive.md' (SS3-SS6).
If that doc's tables change, mirror the change here.
"""

STAGES = [
    {
        "key": "unaware",
        "label": "1. Unaware",
        "mental_state": "Never encountered the brand/molecule",
        "core_barrier": "No awareness",
        "engagement_goal": "Get on the radar",
        "messaging_type": "Unbranded disease-state / epidemiology",
        "current_belief": "No awareness that this molecule/approach exists for their patient population",
        "desired_belief": "This condition and this molecule are relevant to my patients",
        "proof_points": ["Epidemiology / disease-burden data", "Unmet-need studies"],
        "tone_constraint": "Unbranded only -- pre-approval language rules apply",
        "primary_touchpoints": ["Congress presence", "Programmatic/paid social", "PubMed-adjacent placements", "Rep cold-call"],
        "promotion_signal": "Any first impression/click/booth visit",
        "base_channel_mix": {"Reach": 60, "Owned digital": 15, "Events": 15, "Field": 5, "Peer": 0, "Patient-adjacent": 5},
    },
    {
        "key": "aware",
        "label": "2. Aware",
        "mental_state": "Has heard of it, no real understanding",
        "core_barrier": "\"I don't understand it\"",
        "engagement_goal": "Build comprehension",
        "messaging_type": "Mechanism of action, how it differs from standard of care",
        "current_belief": "Has heard the name, doesn't understand mechanism or differentiation",
        "desired_belief": "Understands how this differs from current standard of care",
        "proof_points": ["Mechanism-of-action data", "Differentiation vs. standard of care"],
        "tone_constraint": "Branded intro permitted with approved claims only",
        "primary_touchpoints": ["Email introducing the brand", "Banner/display", "Rep intro detail", "Unbranded-to-branded website"],
        "promotion_signal": "Email open, site visit, first rep meeting accepted",
        "base_channel_mix": {"Reach": 30, "Owned digital": 35, "Events": 10, "Field": 20, "Peer": 0, "Patient-adjacent": 5},
    },
    {
        "key": "interested",
        "label": "3. Interested / Evaluating",
        "mental_state": "Understands it, isn't yet convinced",
        "core_barrier": "\"I don't believe it (for my patients)\"",
        "engagement_goal": "Build belief/credibility",
        "messaging_type": "Efficacy & safety data, head-to-head evidence, KOL commentary",
        "current_belief": "Understands the mechanism but doubts it applies to their patients",
        "desired_belief": "Convinced the evidence supports use in their patient population",
        "proof_points": ["Trial efficacy/safety data", "Head-to-head evidence", "KOL commentary"],
        "tone_constraint": "MLR-cleared claims only, fair-balance required",
        "primary_touchpoints": ["Webinars", "e-detailing", "Congress symposia", "MSL scientific exchange", "Self-detail on web"],
        "promotion_signal": "Webinar registration/attendance, 3+ min site visit, MSL request",
        "base_channel_mix": {"Reach": 10, "Owned digital": 20, "Events": 25, "Field": 30, "Peer": 5, "Patient-adjacent": 10},
    },
    {
        "key": "trial",
        "label": "4. Trial / First Rx",
        "mental_state": "Convinced, hasn't acted yet",
        "core_barrier": "How do I actually start",
        "engagement_goal": "Convert belief -> first prescription",
        "messaging_type": "Patient selection criteria, dosing & initiation, access/reimbursement support",
        "current_belief": "Believes in the evidence but unsure how to operationalize a first prescription",
        "desired_belief": "Knows exactly which patient to start, how to dose, and how access/reimbursement works",
        "proof_points": ["Patient-selection criteria", "Dosing/initiation guide", "Access & reimbursement support materials"],
        "tone_constraint": "MLR-cleared claims only, fair-balance required",
        "primary_touchpoints": ["Rep detail with starter/samples", "Patient support program enrollment", "Dosing app/CLM leave-behind"],
        "promotion_signal": "First sample request, first patient-support enrollment, first Rx flagged in claims/Rx data",
        "base_channel_mix": {"Reach": 5, "Owned digital": 10, "Events": 10, "Field": 35, "Peer": 5, "Patient-adjacent": 35},
    },
    {
        "key": "adoption",
        "label": "5. Adoption / Regular prescriber",
        "mental_state": "Prescribes routinely",
        "core_barrier": "Complacency or competitive-switch risk",
        "engagement_goal": "Reinforce, defend share of mind",
        "messaging_type": "Real-world evidence, broader patient-type expansion, practical troubleshooting (AE management)",
        "current_belief": "Confident in routine use but not actively expanding or defending it",
        "desired_belief": "Sees ongoing real-world value and expands to a broader patient set",
        "proof_points": ["Real-world evidence", "Patient-type expansion data", "AE-management guidance"],
        "tone_constraint": "MLR-cleared claims only, fair-balance required",
        "primary_touchpoints": ["Ongoing rep cadence", "Nurture email flows", "Peer case-study content", "Targeted congress follow-up"],
        "promotion_signal": "Repeat Rx / TRx trend, consistent digital engagement",
        "base_channel_mix": {"Reach": 5, "Owned digital": 20, "Events": 15, "Field": 30, "Peer": 15, "Patient-adjacent": 15},
    },
    {
        "key": "champion",
        "label": "6. Advocate / Champion",
        "mental_state": "Prescribes routinely and influences peers",
        "core_barrier": "Risk of under-utilising them",
        "engagement_goal": "Turn into a voice for the brand",
        "messaging_type": "Co-created content, real-world data they helped generate, peer-to-peer talking points",
        "current_belief": "A satisfied prescriber, not yet activated as an advocate",
        "desired_belief": "Sees themselves as a co-creator and peer voice for the brand",
        "proof_points": ["Co-created real-world data", "Peer-to-peer talking points"],
        "tone_constraint": "MLR-cleared claims + advisory/speaker compliance rules",
        "primary_touchpoints": ["Speaker programs", "Advisory boards", "Peer-to-peer/DOL programs", "Congress podium slots", "Co-authored abstracts"],
        "promotion_signal": "Speaking engagements accepted, peer-referral pattern, advisory board participation",
        "base_channel_mix": {"Reach": 0, "Owned digital": 10, "Events": 20, "Field": 15, "Peer": 50, "Patient-adjacent": 5},
    },
]

STAGE_BY_KEY = {s["key"]: s for s in STAGES}

CHANNEL_TOUCHPOINTS = {
    "Reach": ["Programmatic display", "Paid social", "Paid search", "Unbranded press/PR"],
    "Owned digital": ["Branded email/nurture flows", "CLM/e-detailing", "Brand website", "Portal/app"],
    "Events": ["Congress booths/symposia", "Webinars (ON24)", "Speaker programs"],
    "Field": ["Rep details", "Samples", "MSL scientific exchange"],
    "Peer": ["KOL/DOL content", "Peer-to-peer programs", "Advisory boards", "Congress podium slots"],
    "Patient-adjacent": ["Patient support program enrollment", "EHR point-of-care alerts"],
}

# Illustrative multipliers on top of a stage's base channel mix -- not measured MMx data,
# a directional starting point synthesized from SS2's persona/digital-behaviour descriptions.
PERSONA_MULTIPLIERS = {
    "Digital-first": {"Reach": 1.2, "Owned digital": 1.4, "Events": 1.0, "Field": 0.5, "Peer": 1.0, "Patient-adjacent": 1.0},
    "Hybrid": {"Reach": 1.0, "Owned digital": 1.0, "Events": 1.0, "Field": 1.0, "Peer": 1.0, "Patient-adjacent": 1.0},
    "Field-only / rep-dependent": {"Reach": 0.6, "Owned digital": 0.4, "Events": 1.1, "Field": 1.6, "Peer": 0.8, "Patient-adjacent": 1.0},
    "KOL / DOL": {"Reach": 0.8, "Owned digital": 1.1, "Events": 1.3, "Field": 0.9, "Peer": 1.8, "Patient-adjacent": 0.8},
    "Guideline-follower": {"Reach": 0.8, "Owned digital": 1.1, "Events": 1.3, "Field": 1.0, "Peer": 1.0, "Patient-adjacent": 1.0},
    "Patient-outcome-driven skeptic": {"Reach": 0.6, "Owned digital": 0.9, "Events": 1.2, "Field": 1.3, "Peer": 1.1, "Patient-adjacent": 1.1},
    "Fast-follower": {"Reach": 1.0, "Owned digital": 1.2, "Events": 1.0, "Field": 0.9, "Peer": 1.0, "Patient-adjacent": 1.0},
    "Unknown / not yet consented": {"Reach": 1.5, "Owned digital": 1.2, "Events": 0.8, "Field": 0.5, "Peer": 0.3, "Patient-adjacent": 0.5},
}

PERSONAS = list(PERSONA_MULTIPLIERS.keys())
