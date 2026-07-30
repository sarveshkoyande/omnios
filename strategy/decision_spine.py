"""Decision Spine — the SME-grounded knowledge layer behind the Planning & Strategy stage.

Twelve decision stages (S0–S11) that a real pharma omnichannel campaign plan must walk,
reverse-engineered from (a) the SFMC Campaign Value Chain SME sessions, (b) the captured
SLA-baseline call, and (c) a real agency project brief (Klick/Vertex "Share Your Story CTA
Emails" — the terminal-artifact standard: rule-level eligibility tied to job-coded source
assets, pillar-linked objectives, CRC1→CRC2→CERT ladder assumptions, variant counts, RACI
with counted review rounds).

Three jobs, one module:

1. SPINE — each stage declares the DECISION it makes, the DATA POINTS it needs (with source
   class: internal | external | user, and derivation strategy: derive | ask | confirm), the
   named FRAMEWORK that turns inputs into the decision, and the Campaign Brief section the
   decision feeds. This registry is what makes the agent's questions exist FOR a reason.

2. spine_ask() — derive-first question builder for studio_run.SEQUENCE steps. A question is
   only posed when the ctx genuinely cannot answer it (same law planning_v2's gap analysis
   enforces: inferable gaps are logged as assumptions, never asked). Every ask carries the
   why, the framework, and what's blocked without it.

3. build_decision_record() — after a step lands, emits the full reasoning record: inputs
   with provenance, framework applied, the decision, why, alternatives rejected, and which
   downstream sections/brief parts consume it. This is what kills the blank/childish output:
   the plan explains itself at every step.

Compliance invariants carried throughout (from the vault): MLR/CRC originates, agents
orchestrate; patient-facing + branded ⇒ full CRC ladder; unbranded-first for patients;
any surface collecting patient drug-experience responses is an AE-capture surface with a
~24h PV routing obligation.
"""
from __future__ import annotations

# --------------------------------------------------------------------------- #
# The spine registry. Keyed S0..S11. `feeds` names Campaign Brief sections.
# --------------------------------------------------------------------------- #

SPINE: dict[str, dict] = {
    "S0": {
        "name": "Campaign frame",
        "decision": "Campaign archetype + program placement (net-new journey vs extension of an existing program)",
        "framework": {"name": "Campaign archetype classifier",
                      "how": "Lifecycle stage + trigger event + existing-journey inventory classify the campaign as launch / growth / defense / retention / reactivation, and as net-new vs extension. Extensions inherit the parent program's templates, consent basis, and source-asset trigger logic."},
        "data_points": [
            {"label": "brand + lifecycle stage", "source": "internal", "derivation": "derive"},
            {"label": "existing program / journey inventory", "source": "internal", "derivation": "derive"},
            {"label": "campaign trigger ('why now')", "source": "user", "derivation": "ask"},
            {"label": "net-new vs extension", "source": "user", "derivation": "confirm"},
        ],
        "feeds": ["Purpose (program context + trigger logic)"],
    },
    "S1": {
        "name": "Objective & value",
        "decision": "Pillar-linked measurable objective + leading indicators",
        "framework": {"name": "Objective cascade",
                      "how": "Brand strategic pillar → behavioral objective (the belief/action shift) → measurable KPI with a benchmark-anchored target. Every asset downstream must trace to the pillar (Vertex brief pattern: 'Patient Activation Pillar: Building Belief')."},
        "data_points": [
            {"label": "brand strategy pillars", "source": "internal", "derivation": "derive"},
            {"label": "belief-shift anchor (BAM A→B)", "source": "internal", "derivation": "derive"},
            {"label": "objective confirmation", "source": "user", "derivation": "confirm"},
            {"label": "category engagement benchmarks", "source": "external", "derivation": "derive"},
        ],
        "feeds": ["Objective (pillar-linked)"],
    },
    "S2": {
        "name": "Audience & eligibility",
        "decision": "Primary segment + rule-level eligibility (triggers, inclusions/exclusions, consent basis)",
        "framework": {"name": "Behavioral segmentation + eligibility-rule composer",
                      "how": "Segment library (HCP: stoppers/trial-list/adopters/advocates axis; patient: program-stage) picks the group; eligibility is then written as executable rules — trigger events, source assets, inclusion/exclusion criteria, consent basis — not persona prose. Waterfall history sanity-checks reachable volume."},
        "data_points": [
            {"label": "segment library + affinity profiles", "source": "internal", "derivation": "derive"},
            {"label": "audience sizing benchmark", "source": "external", "derivation": "derive"},
            {"label": "primary segment choice", "source": "user", "derivation": "confirm"},
            {"label": "eligibility triggers / consent basis", "source": "internal", "derivation": "derive"},
        ],
        "feeds": ["Target Audience & Eligibility"],
    },
    "S3": {
        "name": "Insight & belief shift",
        "decision": "Current belief A → desired belief B, with barriers and drivers",
        "framework": {"name": "BAM chart (A→B shift) + barrier/driver analysis",
                      "how": "The Belief-Attitude-Motivation chart states the single belief the campaign must move and what blocks it; every message rung and channel moment exists to move that belief."},
        "data_points": [
            {"label": "BAM chart / A→B shift", "source": "internal", "derivation": "derive"},
            {"label": "market research & competitive evidence", "source": "external", "derivation": "derive"},
        ],
        "feeds": ["Communication Strategy (the 'why believe')"],
    },
    "S4": {
        "name": "Compliance envelope",
        # The brief states the requirement ("MLR-approved content required") and nothing
        # more. The ladder, round counts and PV routing are process detail the compliance
        # team owns; putting the workflow in a brand manager's brief buries the campaign
        # under someone else's process. It stays derived and recorded -- it still sets the
        # timeline's MLR buffer -- but it feeds the technical appendix, not the brief body.
        "decision": "MLR-approved content required (review ladder + PV obligations recorded as technical assumptions)",
        "framework": {"name": "MLR risk-tier classifier + AE/MIR surface scan",
                      "how": "Audience type × content type sets the review rigor: patient-facing branded ⇒ full CRC1 (assume revise-resubmit) → CRC2 (approved-with-changes) → CERT; unbranded-first rule for patients. Any surface collecting patient drug-experience responses (surveys, replies) is flagged as an AE-capture surface with a ~24h PV routing obligation. MLR originates; agents only route."},
        "data_points": [
            {"label": "audience type + content type", "source": "internal", "derivation": "derive"},
            {"label": "review-ladder assumption", "source": "user", "derivation": "confirm"},
            {"label": "AE/MIR capture surfaces", "source": "internal", "derivation": "derive"},
        ],
        "feeds": ["Technical Appendix (review + PV assumptions)"],
    },
    "S5": {
        "name": "Message architecture",
        "decision": "Message ladder — lead rung + sequence, grounded in approved claims (job codes where they exist)",
        "framework": {"name": "Message ladder + AFU claims grounding",
                      "how": "Only claims from the approved library ladder up; the first rung is the one the evidence base supports most strongly for this audience. No net-new claims — MLR originates."},
        "data_points": [
            {"label": "claims / content library", "source": "internal", "derivation": "derive"},
            {"label": "brand kit core claim", "source": "internal", "derivation": "derive"},
            {"label": "lead message confirmation", "source": "user", "derivation": "confirm"},
        ],
        "feeds": ["Communication Strategy (message outline + tone guardrails)"],
    },
    "S6": {
        "name": "Channel & journey",
        "decision": "PP/NPP split, anchor channel, journey logic (triggers, cadence, frequency caps)",
        "framework": {"name": "Channel-affinity scoring + TML targets + journey archetypes",
                      "how": "Segment channel-affinity benchmarks rank channels; the anchor takes the largest share and sets cadence guardrails; journey archetype (trigger-based vs scheduled wave) comes from the campaign frame. A rep touch + digital touch in the same week counts once for frequency."},
        "data_points": [
            {"label": "channel-affinity benchmarks", "source": "external", "derivation": "derive"},
            {"label": "brand channel availability", "source": "internal", "derivation": "derive"},
            {"label": "anchor channel confirmation", "source": "user", "derivation": "confirm"},
        ],
        "feeds": ["Project Overview (sequencing + journey logic)"],
    },
    "S7": {
        "name": "Deliverables spec",
        "decision": "Asset list with variant counts, template + modular reuse plan",
        "framework": {"name": "Modular decomposition + reuse-first rule",
                      "how": "Each tactic decomposes into modular assets (hero/body/ISI blocks); existing AFU assets are reused before net-new is briefed; variants are specified for testing (e.g. 2–3 subject lines + preheaders per email for A/B) — the Vertex-brief level of concreteness."},
        "data_points": [
            {"label": "content inventory / DAM", "source": "internal", "derivation": "derive"},
            {"label": "variant counts for testing", "source": "user", "derivation": "confirm"},
        ],
        "feeds": ["Activities / Deliverables"],
    },
    "S8": {
        "name": "Measurement & tagging",
        "decision": "KPI tree, link/tagging matrix approach, UTM taxonomy, test design",
        "framework": {"name": "KPI tree + measurement-plan template",
                      "how": "Leading indicators trace to the objective's pillar; every link carries campaign + job-code tagging (link matrix as a deliverable); A/B design is declared here, not improvised at build."},
        "data_points": [
            {"label": "leading/lagging indicators", "source": "internal", "derivation": "derive"},
            {"label": "benchmark targets", "source": "external", "derivation": "derive"},
        ],
        "feeds": ["Measurement Plan"],
    },
    "S9": {
        "name": "Operational plan",
        "decision": "RACI, counted review rounds, SLA timeline backward from launch",
        "framework": {"name": "RACI template + backward SLA scheduler",
                      "how": "Owner teams from the activity playbook; review rounds counted up front (extra rounds ⇒ change request); the timeline is backward-scheduled from go-live with the MLR buffer honoured — same engine Engagement Orchestration executes against (~18-day manual baseline, 5-day agentic target)."},
        "data_points": [
            {"label": "team roster / RACI defaults", "source": "internal", "derivation": "derive"},
            {"label": "launch window / hard date", "source": "user", "derivation": "ask"},
            {"label": "SLA library", "source": "internal", "derivation": "derive"},
        ],
        "feeds": ["Timeline", "Approvals"],
    },
    "S10": {
        "name": "Risks & assumptions",
        "decision": "Assumption register + risk flags (AE/MIR, deliverability, consent gaps, patient gating)",
        "framework": {"name": "Pre-mortem checklist (vault gap analysis)",
                      "how": "Every derived assumption is logged; the known failure modes — AE/MIR routing absent, consent provenance untracked, asset expiry unmonitored, silent query failures — are checked against this plan's surfaces and flagged."},
        "data_points": [
            {"label": "derived-assumption log", "source": "internal", "derivation": "derive"},
            {"label": "patient gating status", "source": "internal", "derivation": "derive"},
        ],
        "feeds": ["Risk Register", "Assumptions & Mandatories"],
    },
    "S11": {
        "name": "Synthesis & emission",
        "decision": "Campaign Strategy + Campaign Brief, every line traceable to a decision record",
        "framework": {"name": "Traceability matrix",
                      "how": "The brief is a projection of the decision records into the operational-brief anatomy; nothing appears in the brief that no stage decided."},
        "data_points": [{"label": "all decision records", "source": "internal", "derivation": "derive"}],
        "feeds": ["Whole brief"],
    },
}

# Stages whose decisions are process/plumbing rather than campaign strategy. Their records
# still exist and still feed the timeline and risk logic -- they just render in the
# technical appendix instead of the brief body.
TECHNICAL_STAGES = {"S4", "S10"}

# SEQUENCE section id -> spine stage anchoring it (records are emitted for these).
SEQ_TO_SPINE: dict[str, str] = {
    "tcg": "S2", "cxq": "S1", "feas": "S0", "msgflow": "S5", "channels": "S6",
    "content": "S4", "dmf": "S7", "metrics": "S8", "workplan": "S9",
    "tacpatient": "S10", "tacbrief": "S11",
}


def stage_for(section_id: str) -> dict | None:
    sid = SEQ_TO_SPINE.get(section_id)
    return {"id": sid, **SPINE[sid]} if sid else None


def _clip(value: str, limit: int = 140) -> str:
    value = " ".join(str(value or "").split())
    return value[: limit - 1].rstrip() + "..." if len(value) > limit else value


def _brief(ctx: dict) -> dict:
    return ctx.get("brief") or ctx.get("slots") or {}


def _brief_field(ctx: dict, key: str) -> str:
    return str((_brief(ctx).get(key) or "")).strip()


def _strategic_source(ctx: dict) -> dict:
    return ctx.get("strategic_source") or {}


def _source_name(ctx: dict) -> str:
    src = _strategic_source(ctx)
    return src.get("source_name") or "provided strategic brief"


def _strategic_items(ctx: dict, *keys: str, limit: int = 2) -> list[str]:
    src = _strategic_source(ctx)
    out: list[str] = []
    for key in keys:
        value = src.get(key)
        if isinstance(value, list):
            out.extend(str(v).strip() for v in value if str(v or "").strip())
        elif value:
            out.append(str(value).strip())
    return [_clip(v, 120) for v in out[:limit]]


def _basis(ctx: dict, fallback: str, direct_key: str | None = None,
           strategic_keys: tuple[str, ...] = ()) -> str:
    direct = _brief_field(ctx, direct_key) if direct_key else ""
    if direct:
        return f"Brief-provided: {direct_key} = {_clip(direct, 110)}."
    strategic = _strategic_items(ctx, *strategic_keys, limit=2) if strategic_keys else []
    if strategic:
        return f"Strategic-source supported from {_source_name(ctx)}: {' | '.join(strategic)}."
    return fallback


# --------------------------------------------------------------------------- #
# Derive-first ask builders for the three NEW asks the spine adds.
# (The five existing asks — audience/objective/message/channel/timeline —
# stay in studio_run.build_ask; spine_ask_extras only adds what the old flow
# never asked. Each is conditional: derivable ⇒ None, recorded as assumption.)
# --------------------------------------------------------------------------- #

def spine_ask_extras(ctx: dict, step: dict) -> dict | None:
    """Extra spine asks with explicit basis labels.

    The ask text itself stays minimal so the LLM can write the actual question
    from context instead of reusing a static template sentence.
    """
    if step["id"] == "feas":  # S0 - program placement
        src = ctx.get("strategic_source")
        if src and src.get("has_content") and any("program" in (c or "").lower() for c in (src.get("csfs") or [])):
            return None
        return {"ask_id": f"ask-{step['num']}", "section": step["num"],
                "text": "",
                "question_focus": "Confirm whether this should be treated as a net-new journey or an extension of an existing program.",
                "evidence_basis": _basis(ctx,
                    "No existing program was detected in the provided context; this is a placement assumption to confirm.",
                    "campaign_name", ("csfs", "positioning")),
                "why": "Program placement (S0) drives eligibility rules, template reuse, review scope and timeline.",
                "framework": "Campaign archetype classifier",
                "blocked": "Purpose (program context + trigger logic)",
                "recommendation": {"label": "Net-new journey", "source": "default when no parent program is captured"},
                "options": [{"label": "Extension of an existing program", "source": "inherits templates + consent basis + source-asset triggers"}],
                "free_text": True}

    if step["id"] == "content":  # S4 - compliance envelope
        # No ask. The review ladder is a process fact the compliance team owns, not a
        # campaign decision a brand manager makes in a planning session -- asking them to
        # confirm CRC rounds put an internal workflow in front of the wrong person. The
        # envelope is still derived (it sets the timeline's MLR buffer) and still recorded,
        # but it lands as a technical assumption rather than a gate or a brief section.
        return None

    if step["id"] == "dmf":  # S7 - deliverables variants
        # No ask. "Two or three subject lines per email?" is a production convention, not a
        # campaign decision -- it belongs in the brief as a stated assumption, and stopping
        # a planning session to confirm it is the kind of low-value gate that made the flow
        # feel like an interrogation. It still lands in Deliverables and the test design.
        return None

    return None


# --------------------------------------------------------------------------- #
# Decision records.
# --------------------------------------------------------------------------- #

def _inputs_for(ctx: dict, sid: str) -> list[dict]:
    """Concrete inputs the stage actually used, with source class. Defensive .gets —
    every ctx key is optional."""
    inferred = ctx.get("inferred") or {}
    out: list[dict] = []

    def add(label: str, value, source_class: str, source: str):
        if value:
            v = str(value)
            out.append({"label": label, "value": v[:160] + ("…" if len(v) > 160 else ""),
                        "source_class": source_class, "source": source})

    if sid == "S2":
        add("segment", inferred.get("persona"), "internal", "audience segment library")
        add("audience sizing", (ctx.get("audience_profile") or {}).get("headline"), "external", "industry benchmark")
        g = ctx.get("hcp_360_grounding") or {}
        add("measured segmentation", g.get("headline"), "internal", "HCP 360 panel")
    elif sid == "S1":
        add("belief shift", (ctx.get("bam") or {}).get("a_to_b_shift"), "internal", "BAM chart")
        add("lifecycle posture", inferred.get("lifecycle_label"), "internal", "brand lifecycle store")
    elif sid == "S0":
        add("brand", inferred.get("brand") or (ctx.get("slots") or {}).get("brand"), "user", "intake")
        add("lifecycle", inferred.get("lifecycle_label"), "internal", "brand lifecycle store")
    elif sid == "S5":
        kms = (ctx.get("message_flow") or {}).get("key_messages") or []
        add("message pool", " · ".join(k.get("topic", "") for k in kms[:3]), "internal", "message flow")
        add("core claim", (ctx.get("brand_kit") or {}).get("core_claim"), "internal", "brand kit (approved claims)")
    elif sid == "S6":
        mix = (ctx.get("strategy") or {}).get("channel_mix_pct") or {}
        if mix:
            ranked = sorted(mix.items(), key=lambda kv: -kv[1])[:3]
            add("channel affinity", " · ".join(f"{k} {v}%" for k, v in ranked), "external", "engagement benchmarks")
    elif sid == "S4":
        add("audience type", inferred.get("persona"), "internal", "derived from S2")
        add("patient gating", "unbranded-first rule applies" if "patient" in (inferred.get("persona") or "").lower() else None,
            "internal", "compliance rules")
    elif sid == "S7":
        add("brand kit", (ctx.get("brand_kit") or {}).get("source_label"), "internal", "content library")
    elif sid == "S8":
        kpi = ctx.get("kpi") or {}
        add("leading indicators", " · ".join((kpi.get("leading_indicators") or [])[:3]), "internal", "KPI model")
    elif sid == "S9":
        add("execution bands", "13-week wave with MLR buffer", "internal", "execution work plan (toolkit sheet 12)")
        add("SLA baseline", "~18-day manual simple-campaign baseline; 5-day agentic target", "internal", "SLA baseline call")
    elif sid == "S10":
        add("known failure modes", "AE/MIR routing · consent provenance · asset expiry · silent query fails",
            "internal", "value-chain gap analysis")
    src = _strategic_source(ctx)
    if sid == "S0":
        add("campaign name", _brief_field(ctx, "campaign_name"), "user", "provided brief")
        add("why now", _brief_field(ctx, "reason"), "user", "provided brief")
    elif sid == "S1":
        add("brief objective", _brief_field(ctx, "objective"), "user", "provided brief")
        add("strategic positioning", src.get("positioning"), "user", _source_name(ctx))
        if src.get("csfs"):
            add("strategic CSFs", " | ".join(src.get("csfs")[:3]), "user", _source_name(ctx))
    elif sid == "S2":
        add("brief audience", _brief_field(ctx, "audience"), "user", "provided brief")
    elif sid == "S4":
        add("brief constraints", _brief_field(ctx, "constraints"), "user", "provided brief")
        if src.get("guardrails"):
            add("strategic guardrails", " | ".join(src.get("guardrails")[:3]), "user", _source_name(ctx))
    elif sid == "S5":
        if src.get("evidence"):
            add("strategic evidence anchors", " | ".join(src.get("evidence")[:3]), "user", _source_name(ctx))
    elif sid == "S6":
        add("brief channel preference", _brief_field(ctx, "preferred_channels"), "user", "provided brief")
    elif sid == "S7":
        add("existing assets", _brief_field(ctx, "existing_assets"), "user", "provided brief")
    elif sid == "S9":
        add("brief timing", _brief_field(ctx, "duration"), "user", "provided brief")
    return out


def build_decision_record(ctx: dict, step: dict, answer: str | None,
                          answered_by_user: bool | None = None) -> dict | None:
    """The reasoning record for a landed step. None when the step anchors no spine stage.

    `answered_by_user=False` with a non-empty `answer` marks an auto-assumed decision: the
    value is the agent's own recommendation, taken without a human gate."""
    stage = stage_for(step["id"])
    if not stage:
        return None
    sid = stage["id"]

    decided = answer or "(derived — no ask needed)"
    alternatives: list[dict] = []
    rationale = stage["framework"]["how"]

    # Stage-specific decision text where ctx gives us something concrete.
    inferred = ctx.get("inferred") or {}
    if sid == "S2" and not answer:
        decided = inferred.get("persona") or decided
    if sid == "S1" and not answer:
        decided = (ctx.get("bam") or {}).get("a_to_b_shift") or decided
    if sid == "S6" and not answer:
        mix = (ctx.get("strategy") or {}).get("channel_mix_pct") or {}
        if mix:
            top = max(mix.items(), key=lambda kv: kv[1])
            decided = f"{top[0]}-led mix ({top[1]}%)"
    if sid == "S4":
        # S4 no longer asks, so it would otherwise render as "(derived - no ask needed)"
        # in a brief. State the one line a brand manager needs instead.
        decided = answer or "MLR-approved content required"
    by_user = bool(answer) if answered_by_user is None else bool(answered_by_user)
    if answer and by_user:
        alternatives.append({"label": "agent recommendation accepted or overridden by user",
                             "why_rejected": "user call recorded verbatim; recommendation retained in the ask log"})
    elif answer:
        alternatives.append({"label": "options offered but not put to the user",
                             "why_rejected": "auto-assume was on: the agent's recommendation was taken unreviewed"})

    return {
        "type": "decision_record",
        "stage_id": sid,
        "stage_name": stage["name"],
        "section_id": step["id"],
        "decision": decided,
        "framework": stage["framework"]["name"],
        "rationale": rationale,
        "inputs": _inputs_for(ctx, sid),
        "alternatives": alternatives,
        "feeds": stage["feeds"],
        "answered_by_user": by_user,
        # Renderers put technical records in the appendix rather than the brief body, so
        # process detail stops being the first thing a brand manager reads.
        "technical": sid in TECHNICAL_STAGES,
    }
