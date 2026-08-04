"""Campaign Strategy + Campaign Brief — the two linked artifacts the Planning stage emits.

Replaces the old pair (hardcoded SimplePlanSummary + the 30-section Brand Engagement Plan as
the default view). The Strategy document is the DECISION layer: the spine's decision records
rendered in order — inputs, framework, decision, rationale, downstream feeds. The Brief is
the OPERATIONAL projection: hybrid of a real agency project brief's anatomy (Klick/Vertex —
purpose w/ program context + trigger logic, pillar-linked objective, rule-level audience
eligibility, comms strategy + tone guardrails, deliverables with variant counts, scope with
counted CRC rounds, approvals) plus first-class Measurement Plan and Risk Register sections.

Traceability is the law (spine S11): every brief section names the decision record that
produced it — nothing appears in the brief that no stage decided.

Deterministic structure from ctx with an LLM synthesis pass on top: resilient by
construction, and decision records are re-derived on the fly when the persisted list is
missing (build_decision_record is pure), so this works for any project whose ctx exists —
including older runs.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import campaign_ops  # noqa: E402
import decision_spine  # noqa: E402
import journey_brief  # noqa: E402  (journey step list + Mermaid projection of the ops flow)
import llm_decisioning  # noqa: E402
import studio_run  # noqa: E402  (SEQUENCE — to re-derive records when not persisted)


def _records(ctx: dict) -> list[dict]:
    recs = ctx.get("decision_records") or []
    if recs:
        return recs
    answers = ctx.get("studio_answers") or {}
    out: list[dict] = []
    for step in studio_run.SEQUENCE:
        r = decision_spine.build_decision_record(ctx, step, answers.get(step["id"]))
        if r and not any(x["stage_id"] == r["stage_id"] for x in out):
            out.append(r)
    return out


def _rec(recs: list[dict], sid: str) -> dict:
    return next((r for r in recs if r.get("stage_id") == sid), {})


def _strategic_source_summary(ctx: dict) -> dict:
    src = ctx.get("strategic_source") or {}
    brief = ctx.get("brief") or ctx.get("slots") or {}
    captured_fields = [
        {"label": label, "value": str(brief.get(key) or "")}
        for key, label in (
            ("campaign_name", "Campaign"),
            ("audience", "Audience"),
            ("geography", "Geography"),
            ("duration", "Timing"),
            ("objective", "Objective"),
            ("kpi", "Target KPI"),
            ("preferred_channels", "Preferred channels"),
            ("existing_assets", "Existing assets"),
            ("constraints", "Constraints"),
            ("reason", "Why now"),
        )
        if brief.get(key)
    ]
    if src.get("has_content"):
        basis = f"Grounded in {src.get('source_name') or 'the provided strategic plan'}."
    elif captured_fields:
        basis = "Grounded in the captured brief fields; no structured strategic-plan excerpts were extracted."
    else:
        basis = "No strategic brief/source details were captured; generated from internal planning frameworks and public/brand signals."
    return {
        "basis": basis,
        "source_name": src.get("source_name") or "",
        "has_strategic_source": bool(src.get("has_content")),
        "captured_fields": captured_fields,
        "csfs": src.get("csfs") or [],
        "positioning": src.get("positioning") or "",
        "evidence": src.get("evidence") or [],
        "guardrails": src.get("guardrails") or [],
    }


# --------------------------------------------------------------------------- #
# Campaign Strategy — the decision layer, records in spine order.
# --------------------------------------------------------------------------- #

def compose_strategy(ctx: dict) -> dict:
    recs = _records(ctx)
    inferred = ctx.get("inferred") or {}
    order = list(decision_spine.SPINE.keys())
    recs_sorted = sorted(recs, key=lambda r: order.index(r["stage_id"]) if r.get("stage_id") in order else 99)
    return {
        "title": "Campaign Strategy",
        "brand": inferred.get("brand") or (ctx.get("brief") or ctx.get("slots") or {}).get("brand") or "",
        "generated_at": time.strftime("%Y-%m-%d"),
        "source_summary": _strategic_source_summary(ctx),
        "records": recs_sorted,
        "note": "Each section is a decision record: the inputs used (with source class), the framework applied, "
                "the decision, and which brief sections it feeds. This is the reasoning the brief projects from.",
    }


# --------------------------------------------------------------------------- #
# Campaign Brief — the operational projection (hybrid Vertex anatomy).
# --------------------------------------------------------------------------- #

def _journey(plan: dict) -> dict:
    """The journey the brief prints: every touchpoint, wait, split and branch the ops flow
    actually contains. See journey_brief for why this is no longer a hand-collapsed summary."""
    return journey_brief.project(plan)


def compose_brief(ctx: dict, enrich: bool = False) -> dict:
    recs = _records(ctx)
    inferred = ctx.get("inferred") or {}
    slots = ctx.get("brief") or ctx.get("slots") or {}
    answers = ctx.get("studio_answers") or {}
    bam = ctx.get("bam") or {}
    persona = inferred.get("persona") or ""
    patient_facing = "patient" in persona.lower() or "caregiver" in persona.lower()

    try:
        plan = campaign_ops.build_campaign_plan(ctx)
    except Exception as exc:  # noqa: BLE001 — brief must compose even if the ops skeleton can't
        # Loud on the way down. This degradation is not cosmetic: without a plan the brief
        # loses the audience segments, the journey map and the deliverables table at once,
        # and a silent `plan = {}` made that look like a composition choice rather than a bug.
        print(f"[campaign_artifacts] campaign plan failed, brief degrades to no journey/segments: {exc!r}")
        plan = {}
    # The diagram is now a URL derived from the flow, not a file this process renders: no
    # subprocess, no Chromium, nothing cached on disk. The previous local render wrote every
    # project's journey to ONE shared PNG path, so whichever project rendered first became
    # the picture every other project showed.
    diagram = journey_brief.diagram(plan) if plan else {}
    if diagram:
        ctx["campaign_brief_diagram"] = diagram

    kms = (ctx.get("message_flow") or {}).get("key_messages") or []
    mix = (ctx.get("strategy") or {}).get("channel_mix_pct") or {}
    ranked_mix = sorted(mix.items(), key=lambda kv: -kv[1])
    kpi = ctx.get("kpi") or {}
    kit = ctx.get("brand_kit") or {}
    source_summary = _strategic_source_summary(ctx)

    # Deliverables: one row per send/followup touchpoint in the ops flow, with the S7 variant plan.
    variant_plan = answers.get("dmf") or "2–3 subject-line + preheader variants per email (A/B), modular reuse-first"
    deliverables = []
    for node in (plan.get("flow") or {}).get("nodes", []):
        if node.get("type") in ("send", "followup"):
            d = node.get("data", {})
            deliverables.append({
                "asset": f"{d.get('channel', 'Asset')}" + (f" — {d['label']}" if d.get("label") else ""),
                "variants": variant_plan if "mail" in (d.get("channel") or "").lower() else "1 primary layout",
                "notes": "Reuse approved modular blocks (hero/body/ISI) before net-new; link matrix required.",
            })
    if not deliverables:
        deliverables.append({"asset": "Asset list pending journey design", "variants": variant_plan,
                             "notes": "Derived once the campaign-ops flow exists."})

    ladder = answers.get("content") or (
        "CRC1 (assume revise & resubmit) → CRC2 (approved with changes) → CERT" if patient_facing
        else "Full MLR review for claims content; light review for unbranded/disease-state")

    risks = [
        {"risk": "AE/MIR capture on inbound surfaces (surveys, replies)", "severity": "critical" if patient_facing else "monitor",
         "mitigation": "Route any drug-experience response to PV/Medical Info within ~24h — detection and routing only, never auto-response."},
        {"risk": "Asset expiry (AFU 30/60/90-day window)", "severity": "monitor",
         "mitigation": "Expiring approved assets flagged via the asset-lifecycle nudge path."},
        {"risk": "Consent provenance", "severity": "monitor",
         "mitigation": "Consent basis recorded per recipient; suppression enforced pre-push."},
    ]
    if patient_facing:
        risks.append({"risk": "Patient gating (unbranded-first rule)", "severity": "critical",
                      "mitigation": "Patient tactics stay gated until regulatory/legal confirms branded exposure."})

    assumptions = [
        "Review-round counts as stated in Scope — additional rounds trigger a change request.",
        "All imagery/claims leveraged from the approved branded campaign (no net-new claims — MLR originates).",
        f"Variant plan: {variant_plan}.",
        "Timeline honours the MLR buffer; backward-scheduled from the launch window.",
    ]

    def _decided(sid: str) -> str | None:
        d = _rec(recs, sid).get("decision") or ""
        return None if (not d or d.startswith("(derived")) else d

    s1 = _rec(recs, "S1")

    draft = {
        "title": "Campaign Brief",
        "version": "1.0",
        "generated_at": time.strftime("%Y-%m-%d"),
        # The five lines a brand manager needs before anything else. Everything about how
        # the plan was produced -- sources, extraction basis, traceability -- moved to the
        # technical appendix: it was opening the brief with the machinery instead of the
        # campaign, which is the first thing the review flagged.
        "snapshot": {
            "objective": answers.get("cxq") or s1.get("decision") or bam.get("a_to_b_shift") or "",
            "brand": inferred.get("brand") or slots.get("brand") or "",
            "therapy_area": inferred.get("therapy_area") or slots.get("therapy_area") or "",
            "target_audience": answers.get("tcg") or persona,
            "reason": slots.get("reason") or "",
        },
        "header": {
            "brand": inferred.get("brand") or slots.get("brand") or "",
            "therapy_area": inferred.get("therapy_area") or slots.get("therapy_area") or "",
            "lifecycle": inferred.get("lifecycle_label") or "",
            "owner": "Planning & Strategy agent (draft — assign a human owner)",
        },
        "source_summary": source_summary,
        "journey_diagram": diagram,
        "purpose": {
            "program_context": answers.get("feas") or _decided("S0") or "Net-new journey (no existing program named)",
            "trigger_logic": (plan.get("entry_criteria") or [])[:4],
            "summary": f"Move {persona or 'the target audience'} through: {bam.get('a_to_b_shift', 'the planned belief shift')}.",
        },
        "objective": {
            "pillar": s1.get("decision") or bam.get("a_to_b_shift") or "",
            "statement": answers.get("cxq") or bam.get("a_to_b_shift") or "",
            "leading_indicators": (kpi.get("leading_indicators") or [])[:4],
        },
        "audience": {
            "segment": answers.get("tcg") or persona,
            # Every segment the user locked is listed -- no truncation, or the brief would
            # silently drop picks (the ask is multi-select and takes free text too).
            "eligibility_rules": [f"Entry: {c}" for c in (plan.get("entry_criteria") or [])[:3]] +
                                 [f"Segment: {s.get('name', '')}" +
                                  (f" ({s['volume']:,})" if s.get("volume") and s.get("volume_exact")
                                   else f" (~{s['volume']:,})" if s.get("volume") else "")
                                  for s in (plan.get("segments") or [])],
            "segments": [{"name": s.get("name", ""), "profile": s.get("profile", ""),
                          "volume": s.get("volume"), "volume_note": s.get("volume_note"),
                          "volume_exact": bool(s.get("volume_exact")),
                          "key_characteristics": s.get("key_characteristics") or []}
                         for s in (plan.get("segments") or [])],
            "consent_note": "Consent + suppression enforced as non-removable clauses on every audience pull.",
        },
        "comms_strategy": {
            "belief_shift": bam.get("a_to_b_shift") or "",
            "message_ladder": [k.get("topic", "") for k in kms[:4]],
            "message_detail": [{"topic": k.get("topic", ""),
                                "supporting": [s for s in (k.get("supporting_messages") or []) if s and not s.startswith("[")][:2]}
                               for k in kms[:4]],
            "tone_guardrails": ["Fair balance on every efficacy claim", "No pressure framing on patient CTAs"]
                               + (["Unbranded-first for patient-facing surfaces"] if patient_facing else []),
            "core_claim": kit.get("core_claim") or "",
        },
        "deliverables": deliverables,
        "channel_journey": {
            # Always derived from the live mix (not the frozen studio answer): persona
            # rebalances update ctx["strategy"]["channel_mix_pct"], and the anchor line
            # must never disagree with the mix chips beside it.
            "anchor": (f"{ranked_mix[0][0]}-led mix ({ranked_mix[0][1]}%)" if ranked_mix else answers.get("channels") or ""),
            "mix": [{"channel": k, "pct": v} for k, v in ranked_mix[:6]],
            "cadence_note": "Frequency caps honoured; a rep touch + digital touch in the same week counts once.",
            "journey": _journey(plan),
        },
        "measurement_plan": {
            "kpis": (kpi.get("leading_indicators") or [])[:5],
            "link_matrix_note": "Link/tagging matrix is a deliverable: every URL carries campaign + job-code tagging (UTM taxonomy).",
            "test_design": variant_plan,
        },
        "scope_review": {
            "ladder": ladder,
            "rounds_note": "One consolidated client review per round; additional rounds = change request (schedule impact).",
            "change_control": "Complexity increases beyond planned execution scope trigger a change request.",
        },
        "risk_register": risks,
        "assumptions": assumptions,
        "timeline": {
            "window": answers.get("workplan") or _decided("S9") or "13-week standard wave",
            "note": "Backward-scheduled from go-live with the MLR buffer; executed and tracked in Engagement Orchestration.",
        },
        "approvals": [
            {"role": "Brand / client lead", "name": ""},
            {"role": "Strategy", "name": ""},
            {"role": "Project management", "name": ""},
            {"role": "Medical / regulatory", "name": ""},
        ],
        "traceability": [{"brief_section": ", ".join(r.get("feeds", [])), "stage_id": r.get("stage_id"),
                          "stage_name": r.get("stage_name"), "framework": r.get("framework")}
                         for r in recs],
        # Everything a reviewer may need to audit the brief but nobody needs in order to
        # read it. Rendered last, after approvals.
        "technical_appendix": {
            "review_and_pv": [
                "MLR-approved content required for every asset in this brief.",
                f"Assumed review path: {ladder}.",
                "Any surface collecting drug-experience responses is an AE-capture surface "
                "with a ~24h PV routing obligation.",
            ],
            "technical_decisions": [
                {"stage_id": r.get("stage_id"), "stage_name": r.get("stage_name"),
                 "decision": r.get("decision"), "framework": r.get("framework")}
                for r in recs if r.get("technical")
            ],
        },
    }
    # Preserve the deterministic projection so the SME grounding, decision records, and
    # campaign-ops skeleton remain visible to the user instead of being reworded by an LLM.
    # The LLM pass is opt-in for the same reason as the diagram above: it is an LLM round-trip
    # (plus cognee recall) and the brief is already complete and correct without it.
    if not enrich:
        return draft
    return llm_decisioning.enhance_campaign_brief(ctx, draft)


def compose_artifacts(ctx: dict, enrich: bool = False) -> dict:
    """Deterministic by default so this stays a fast read.

    `enrich=True` additionally renders the journey PNG and runs the LLM brief synthesis --
    both are slow enough that they belong behind an explicit opt-in, never on the path the
    workspace blocks on right after Stage 1 finishes.
    """
    return {"strategy": compose_strategy(ctx), "brief": compose_brief(ctx, enrich=enrich)}
