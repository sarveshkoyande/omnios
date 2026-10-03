"""Proposes brand-kit content for brands with no uploaded brand plan (Jardiance, Keytruda).

Client data (deciles, field force, reach) is SYNTHETIC (client_data.py). Brand content is
different: people read and act on it, so it is never random. This engine DRAFTS it from evidence
the kit already holds -- FDA label sections (indications, clinical studies, warnings), the US
patient flow from PubMed, audience segments, US geography, competitors -- and every section is
stored with status "proposed" plus its sources, so the pages can say "Proposed — to confirm".

Sections it proposes (only those still empty, unless force=True):
  evidence      -> clinical_data, references, message_hierarchy, core_claim, positioning_statement,
                   therapy_area, primary_audience
  personas      -> personas (hcp / patient / caregiver, with behaviours, barrier, moment, voice,
                   key message, tone), care_continuum, messages_by_persona
  voice         -> voice (principles say/not, tone by audience, vocabulary, avoid), tone_pillars,
                   voice_do, voice_dont, guardrails (from the label), unmet_need
  competition   -> competitors enriched (strength, weakness, counter, threat proposed), competition_self

Rules: the model only restates what the evidence supports and cites it; efficacy claims must come
from the label's clinical studies section; persona quotes are marked illustrative. With no model
it raises LLMUnavailable and writes nothing (R2).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import brand_kit  # noqa: E402
import public_sources as ps  # noqa: E402
from llm_json import LLMUnavailable, complete_json  # noqa: E402

_SYS = ("You are a US pharmaceutical brand strategist drafting a brand kit for review by the brand team and "
        "MLR. Use ONLY the evidence provided; cite it in every `source` field (e.g. 'FDA label · clinical studies "
        "(EMPEROR-Reduced)', 'PubMed 41165079', 'Brand IQ patient flow'). Never invent figures, trial names or "
        "claims. Efficacy claims must come from the label's clinical studies section and stay on-label. "
        "Reply with a single JSON object only.")


def _label(kit: dict, key: str, n: int) -> str:
    return (((kit.get("product_profile") or {}).get(key) or {}).get("value") or "")[:n]


def _evidence_pack(kit: dict) -> dict:
    flow = [{"indication": f.get("indication_id"),
             "stages": [{k: s.get(k) for k in ("stage", "value", "unit", "what", "verdict", "caveat", "source")} for s in f.get("stages") or []],
             "leaks": f.get("leaks")} for f in kit.get("patient_flow") or []]
    return {"brand": None, "generic": kit.get("generic"), "company": kit.get("company"),
            "situation": kit.get("brand_situation"),
            "indications": [{k: i.get(k) for k in ("name", "condition", "population", "line", "criteria")} for i in kit.get("indications") or []],
            "patient_flow_us": flow, "audience_segments": kit.get("audience_segments"),
            "competitors": [{k: c.get(k) for k in ("name", "type", "source")} for c in kit.get("competitors") or []][:15],
            "us_geography": [{"measure": l.get("measure"), "fit": l.get("fit"), "for": l.get("for_indication"),
                              "top_states": [s["state"] for s in (l.get("states") or [])[:6]]}
                             for l in (kit.get("us_geography") or {}).get("layers") or []]}


def propose_evidence(brand: str, kit: dict) -> dict:
    out = complete_json(_SYS + "\nFrom the label's clinical studies section, draft: clinical_data (3-6 pivotal "
                        "results: study, stat with the exact figures, context = label section), references (the "
                        "pivotal trials as references: id, title, type, key_data, promo_eligible true), "
                        "message_hierarchy (3-5 pillars: pillar, claim (on-label), evidence), core_claim (one "
                        "sentence), positioning_statement ('For <audience> with <need>, <brand> is the <frame> "
                        "that <benefit> because <reason>'), therapy_area, primary_audience.\n"
                        'Shape: {"clinical_data":[{"study":"","stat":"","context":""}],"references":[{"id":"","title":"",'
                        '"type":"","key_data":"","promo_eligible":true}],"message_hierarchy":[{"pillar":"","claim":"",'
                        '"evidence":""}],"core_claim":"","positioning_statement":"","therapy_area":"","primary_audience":""}',
                        {**_evidence_pack(kit), "brand": brand,
                         "label_indications": _label(kit, "indication", 6000),
                         "label_clinical_studies": _label(kit, "clinical_studies", 22000)}, max_tokens=6000)
    return out


def propose_personas(brand: str, kit: dict) -> dict:
    out = complete_json(_SYS + "\nDraft personas from the audience segments, the patient flow's leaks and the "
                        "indications. HCP personas (3-5): name (role + archetype, e.g. 'Cardiologist — the Cautious "
                        "Initiator'), specialties, who, tier (Primary/Secondary), behaviours (2-4, tied to the leaks "
                        "in the patient flow), barrier, moment (when they decide), key_message (on-label), tone, "
                        "voice (an ILLUSTRATIVE quote of how they think, marked as such by the UI), source. Patient "
                        "and caregiver personas (1-2 each) the same way. Then care_continuum stages (the patient "
                        "journey in plain words, 3-5 stages: stage, patient, source) and messages_by_persona "
                        "(persona, message, existing: 'Not captured', to_develop: content ideas).\n"
                        'Shape: {"personas":{"hcp":[{"name":"","specialties":"","who":"","tier":"","behaviours":[""],'
                        '"barrier":"","moment":"","key_message":"","tone":"","voice":"","source":""}],"patient":[],'
                        '"caregiver":[]},"care_continuum":{"stages":[{"stage":"","patient":"","source":""}]},'
                        '"messages_by_persona":[{"persona":"","message":"","existing":"","to_develop":""}]}',
                        {**_evidence_pack(kit), "brand": brand,
                         "message_hierarchy": kit.get("message_hierarchy")}, max_tokens=6000)
    return out


def propose_voice(brand: str, kit: dict) -> dict:
    out = complete_json(_SYS + "\nDraft: voice (register, reading_level, 4-5 principles each with a 'say' and a "
                        "'not' example, by_audience tone rows for each persona, vocabulary rows use/instead_of, "
                        "avoid list), tone_pillars (4-5 words), guardrails from the LABEL ONLY (dos/donts with "
                        "category and text citing the label section: indication limits, limitations of use, key "
                        "warnings, populations not studied), and unmet_need (summary, facts = figures from the US "
                        "patient flow with their source, gaps = where patients are lost and who it affects).\n"
                        'Shape: {"voice":{"register":"","reading_level":"","principles":[{"principle":"","say":"","not":""}],'
                        '"by_audience":[{"audience":"","tone":"","focus":""}],"vocabulary":[{"use":"","instead_of":""}],'
                        '"avoid":[""]},"tone_pillars":[""],"guardrails":{"dos":[{"category":"","text":""}],'
                        '"donts":[{"category":"","text":""}]},"unmet_need":{"summary":"","facts":[{"label":"","value":"",'
                        '"source":""}],"gaps":[{"gap":"","detail":"","who":"","source":""}]}}',
                        {**_evidence_pack(kit), "brand": brand, "personas": kit.get("personas"),
                         "label_indications": _label(kit, "indication", 6000),
                         "label_warnings": _label(kit, "warnings", 8000),
                         "label_contraindications": _label(kit, "contraindications", 2000)}, max_tokens=6000)
    return out


def propose_competition(brand: str, kit: dict) -> dict:
    out = complete_json(_SYS + "\nFor each competitor / alternative listed (keep the list, merge duplicates, keep at "
                        "most 8, prefer direct competitors and standard of care), add: type, status, strength, "
                        "weakness, counter (how this brand wins, on-label), threat (High/Medium/Low) and "
                        "threat_reason. Also describe the brand itself as competition_self (name, type, status, "
                        "strength, weakness). Use general, well-established knowledge of the class only where the "
                        "evidence names the competitor; otherwise say 'Not captured'.\n"
                        'Shape: {"competitors":[{"name":"","type":"","status":"","strength":"","weakness":"","counter":"",'
                        '"threat":"","threat_reason":"","source":""}],"competition_self":{"name":"","type":"","status":"",'
                        '"strength":"","weakness":""}}',
                        {**_evidence_pack(kit), "brand": brand, "message_hierarchy": kit.get("message_hierarchy")},
                        max_tokens=5000)
    for c in out.get("competitors") or []:
        c["threat_status"] = "proposed"
    return out


def propose_big_idea(brand: str, kit: dict, avoid: list[str] | None = None) -> dict:
    """The brand's Big Idea (creative platform), with its reasoning. AI-generated by design; the
    brand team can regenerate it. `avoid` lists earlier ideas so a regeneration is genuinely new."""
    out = complete_json(_SYS + "\nCreate the brand's Big Idea: a short, ownable creative platform line (max ~12 "
                        "words) that every campaign can express, plus 3 alternatives. Ground it in ONE sharp insight "
                        "about the priority audience (from the personas and the patient flow's leaks), stay on-label "
                        "(no claim beyond the message pillars), and fit the voice. Explain your reasoning: the insight, "
                        "why this idea answers it, which personas and evidence it draws on, how it differs from "
                        "competitors, and why you chose it over the alternatives. Don't repeat any idea in `avoid`.\n"
                        'Shape: {"big_idea":"","insight":"","reasoning":"","draws_on":[{"what":"","source":""}],'
                        '"why_not_competitors":"","alternatives":[{"idea":"","why_not_chosen":""}],"fit_check":{"on_label":true,"notes":""}}',
                        {**_evidence_pack(kit), "brand": brand, "positioning": kit.get("positioning_statement"),
                         "core_claim": kit.get("core_claim"), "message_hierarchy": kit.get("message_hierarchy"),
                         "personas": kit.get("personas"), "voice": kit.get("voice"), "tone_pillars": kit.get("tone_pillars"),
                         "unmet_need": kit.get("unmet_need"), "avoid": avoid or []}, max_tokens=2500)
    return out


def big_idea(brand: str) -> dict:
    """(Re)generate the Big Idea and save it with its reasoning; the previous one is kept in history."""
    kit = brand_kit.kit_for(brand)
    if not kit:
        raise KeyError(brand)
    prev = kit.get("big_idea") or {}
    history = list(prev.get("history") or [])
    if prev.get("text"):
        history.append({"text": prev["text"], "generated_at": prev.get("generated_at")})
    out = propose_big_idea(brand, kit, avoid=[h["text"] for h in history] + ([kit["tagline"]] if kit.get("tagline") else []))
    text = (out.get("big_idea") or "").strip()
    if not text:
        raise LLMUnavailable("the model returned no Big Idea")
    record = {"text": text, "insight": out.get("insight"), "reasoning": out.get("reasoning"),
              "draws_on": out.get("draws_on") or [], "why_not_competitors": out.get("why_not_competitors"),
              "alternatives": out.get("alternatives") or [], "fit_check": out.get("fit_check"),
              "generated_at": ps._today(), "status": "ai_generated", "history": history[-10:]}
    proposals = dict(kit.get("proposals") or {})
    proposals["tagline"] = {"status": "ai_generated", "engine": "kit_proposer.big_idea", "date": ps._today()}
    return brand_kit.apply_diff(brand, {"tagline": text, "big_idea": record, "proposals": proposals})


def _empty(v) -> bool:
    """Empty, a "Needs input" placeholder, or a container whose parts are all empty (e.g. a new
    kit's {"hcp": [], "patient": []} or {"dos": [], "donts": []})."""
    if isinstance(v, dict):
        return not v or all(_empty(x) for x in v.values())
    return v in (None, "", []) or (isinstance(v, str) and v.startswith("Needs input"))


def propose(brand: str, force: bool = False) -> dict:
    """Fill the brand's empty brand-content sections with sourced proposals and save them."""
    kit = brand_kit.kit_for(brand)
    if not kit:
        raise KeyError(brand)
    proposals = dict(kit.get("proposals") or {})
    fields: dict = {}

    def apply(section: str, out: dict, keys: tuple, always: tuple = ()):
        for k in keys:
            if k in out and (force or k in always or _empty(kit.get(k))):
                fields[k] = out[k]
                kit[k] = out[k]
                proposals[k] = {"status": "proposed", "engine": f"kit_proposer.{section}", "date": ps._today()}

    if force or any(_empty(kit.get(k)) for k in ("clinical_data", "message_hierarchy", "positioning_statement")):
        apply("evidence", propose_evidence(brand, kit),
              ("clinical_data", "references", "message_hierarchy", "core_claim", "positioning_statement", "therapy_area", "primary_audience"))
    if force or _empty((kit.get("personas") or {}).get("hcp")):
        apply("personas", propose_personas(brand, kit), ("personas", "care_continuum", "messages_by_persona"))
    if force or _empty(kit.get("voice")):
        out = propose_voice(brand, kit)
        voc = (out.get("voice") or {}).get("vocabulary") or []
        out["voice_do"] = [v.get("use") for v in voc if v.get("use")]
        out["voice_dont"] = (out.get("voice") or {}).get("avoid") or []
        if out.get("voice"):
            out["voice"]["status"] = "to_confirm"
            out["voice"]["note"] = "Drafted by Omni from the FDA label and public evidence — to confirm"
        apply("voice", out, ("voice", "tone_pillars", "voice_do", "voice_dont", "guardrails", "unmet_need"))
    if force or not any((c.get("strength") for c in kit.get("competitors") or [])):
        # enriching competitors replaces the bare list from PubMed, so it always applies
        apply("competition", propose_competition(brand, kit), ("competitors", "competition_self"), always=("competitors",))
    if force or _empty(kit.get("tagline")):
        kit_now = brand_kit.apply_diff(brand, {**fields, "proposals": proposals}) if fields else kit
        big_idea(brand)
        kit = brand_kit.kit_for(brand) or kit_now
        proposals = dict(kit.get("proposals") or proposals)
    if _empty(kit.get("approval_dates")):
        appr = ((kit.get("product_profile") or {}).get("us_approval") or {}).get("value") or {}
        if appr.get("date"):
            fields["approval_dates"] = [{"region": "US", "value": appr["date"], "source": f"Drugs@FDA {appr.get('application') or ''}"}]
    fields["proposals"] = proposals
    return brand_kit.apply_diff(brand, fields)


# --- Brand IQ Agent: each step is a separate skill, run one at a time from the agent workspace ---
SKILLS = [
    {"id": "label", "name": "Read the FDA label", "llm": False,
     "does": "Fetches the product profile from FDA label, Drugs@FDA, NIH MeSH and PubChem."},
    {"id": "audience_intel", "name": "Scan the HCP & patient landscape", "llm": False,
     "does": "PubMed key opinion leaders, ClinicalTrials.gov trial footprint, MedlinePlus patient resources."},
    {"id": "us_geography", "name": "Map US geography", "llm": False,
     "does": "State-level prevalence for the brand's conditions from CDC PLACES."},
    {"id": "evidence", "name": "Draft evidence & positioning", "llm": True,
     "does": "Clinical data, references, message hierarchy, core claim and positioning from the label."},
    {"id": "personas", "name": "Draft personas", "llm": True,
     "does": "HCP, patient and caregiver personas, care continuum and messages by persona."},
    {"id": "voice", "name": "Draft voice & guardrails", "llm": True,
     "does": "Voice principles, tone by audience, vocabulary, guardrails from the label, unmet need."},
    {"id": "competition", "name": "Analyse competition", "llm": True,
     "does": "Competitor strengths, weaknesses, counters and threat level."},
    {"id": "big_idea", "name": "Generate the Big Idea", "llm": True,
     "does": "The Big Idea and tagline, with its reasoning and alternatives."},
    {"id": "client_data", "name": "Load client data", "llm": False,
     "does": "HCP deciles, accounts, access, field force and reach (synthetic until real feeds are connected)."},
]


def run_skill(brand: str, skill: str) -> dict:
    """Run one Brand IQ skill for the brand and return the updated kit. LLM skills raise
    LLMUnavailable with no model (nothing written); public-source skills raise on fetch errors."""
    kit = brand_kit.kit_for(brand)
    if not kit:
        raise KeyError(brand)
    proposals = dict(kit.get("proposals") or {})

    def save(section: str, out: dict, keys: tuple) -> dict:
        fields = {k: out[k] for k in keys if k in out}
        for k in fields:
            proposals[k] = {"status": "proposed", "engine": f"kit_proposer.{section}", "date": ps._today()}
        return brand_kit.apply_diff(brand, {**fields, "proposals": proposals})

    if skill == "label":
        q = kit.get("public_source_query") or {}
        if not q.get("generic"):
            raise ValueError("This brand has no generic (INN) name set, so the FDA label can't be looked up.")
        return brand_kit.apply_diff(brand, {"product_profile": ps.fetch_product_profile(q["generic"], q.get("condition") or kit.get("indication", ""))})
    if skill == "audience_intel":
        q = kit.get("audience_query") or {}
        if not q.get("condition"):
            raise ValueError("This brand has no condition set for the audience scan.")
        return brand_kit.apply_diff(brand, {"audience_intel": ps.fetch_audience_intel(q["condition"], q.get("intervention", ""), q.get("pubmed_term") or q["condition"])})
    if skill == "us_geography":
        import us_geography
        return brand_kit.apply_diff(brand, {"us_geography": us_geography.build(brand, kit.get("indications") or [])})
    if skill == "evidence":
        return save("evidence", propose_evidence(brand, kit),
                    ("clinical_data", "references", "message_hierarchy", "core_claim", "positioning_statement", "therapy_area", "primary_audience"))
    if skill == "personas":
        return save("personas", propose_personas(brand, kit), ("personas", "care_continuum", "messages_by_persona"))
    if skill == "voice":
        out = propose_voice(brand, kit)
        voc = (out.get("voice") or {}).get("vocabulary") or []
        out["voice_do"] = [v.get("use") for v in voc if v.get("use")]
        out["voice_dont"] = (out.get("voice") or {}).get("avoid") or []
        if out.get("voice"):
            out["voice"]["status"] = "to_confirm"
            out["voice"]["note"] = "Drafted by Omni from the FDA label and public evidence — to confirm"
        return save("voice", out, ("voice", "tone_pillars", "voice_do", "voice_dont", "guardrails", "unmet_need"))
    if skill == "competition":
        return save("competition", propose_competition(brand, kit), ("competitors", "competition_self"))
    if skill == "big_idea":
        return big_idea(brand)
    if skill == "client_data":
        import client_data
        client_data.generate(brand, force=True)
        return brand_kit.kit_for(brand) or kit
    raise ValueError(f"Unknown skill '{skill}'")


__all__ = ["propose", "run_skill", "SKILLS", "LLMUnavailable"]
