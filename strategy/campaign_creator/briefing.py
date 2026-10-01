"""The Campaign Consultant: Camille's Campaign Briefing Document flow.

Prompts are Camille's (index.js BRIEFING_ANALYSIS_PROMPT, BRIEFING_GENERATION_PROMPT, the
inline ambiguity-review prompt of /campaign-briefing/answer, BRIEFING_UPDATE_PROMPT), with two
additions for OmniOS: an optional workspace block (the brand, engagement plan and campaign the
planner is scoped to, plus the brand kit's key facts) and the explicit decisions list the
generation step records as keyDecisions. When no model is configured the run stops (rules R1/R2);
`rules_briefing` (removed)
assembles the document from the typed text alone and marks every gap "Not specified by user".
"""
from __future__ import annotations

import json
import re

from . import llm

NOT_SPECIFIED = "Not specified by user"
MAX_QUESTIONS = 3
MAX_ASSUMPTIONS = 3


# ------------------------------------------------------------------ workspace context ---

def workspace_block(workspace: dict | None) -> str:
    """What the planner already knows about where this campaign lives. Empty when unscoped."""
    ws = workspace or {}
    kit = ws.get("kit") or {}
    lines: list[str] = []
    for label, key in (("Brand", "brand"), ("Engagement plan", "plan_name"), ("Campaign", "campaign_name")):
        if ws.get(key):
            lines.append(f"- {label}: {ws[key]}")
    facts: list[str] = []

    def fact(label: str, value) -> None:
        if isinstance(value, list):
            value = "; ".join(str(v) for v in value if v)
        value = str(value or "").strip()
        if value:
            facts.append(f"- {label}: {value[:400]}")

    fact("Generic name", kit.get("generic"))
    fact("Company", kit.get("company"))
    fact("Therapy area", kit.get("therapy_area"))
    fact("Approved indication", kit.get("approved_indication") or kit.get("indication"))
    fact("Core claim", kit.get("core_claim"))
    fact("Positioning", kit.get("positioning_statement"))
    fact("Safety reference", kit.get("safety_reference"))
    fact("Tone", kit.get("tone_pillars"))
    guard = kit.get("guardrails") or {}
    if isinstance(guard, dict):
        fact("Guardrails (do)", [g.get("text") for g in (guard.get("dos") or [])[:5] if isinstance(g, dict)])
        fact("Guardrails (don't)", [g.get("text") for g in (guard.get("donts") or [])[:5] if isinstance(g, dict)])
    personas = kit.get("personas") or {}
    if isinstance(personas, dict):
        fact("HCP personas", [p.get("name") for p in (personas.get("hcp") or []) if isinstance(p, dict)])
    fact("Competitors", [c.get("name") for c in (kit.get("competitors") or []) if isinstance(c, dict)])
    if not lines and not facts:
        return ""
    out = ["## OMNI WORKSPACE CONTEXT", "This campaign is being planned inside Omni for:", *lines]
    if facts:
        out += ["", "Brand facts on file in the brand kit. Use them only when the requirements are about "
                    "this brand; the user's requirements always take precedence over them:", *facts]
    return "\n".join(out)


# ------------------------------------------------------------------ prompts -------------

def analysis_prompt(requirements: str, is_from_document: bool, workspace: str = "") -> str:
    return f"""
You are a senior pharmaceutical marketing strategist with 15+ years of SFMC (Salesforce Marketing Cloud) campaign design experience.

Your job is to deeply read and understand the provided campaign requirements, then determine if any CRITICAL details are missing that would make the Campaign Briefing Document incomplete or ambiguous.

## INPUT
Source: {"Extracted from uploaded document" if is_from_document else "Typed by user"}
Requirements:
\"\"\"
{requirements}
\"\"\"
{workspace}

## YOUR PROCESS — FOLLOW EXACTLY

### Step 1: Extract and Summarize
Read every detail in the requirements. In "extractedContext", write a detailed summary of EVERYTHING the user specified — brand, product, therapeutic area, audience, channels, journey steps, timing, KPIs, compliance rules, etc. Be thorough. This summary will be used downstream.

### Step 2: Identify Genuinely Missing Critical Gaps
Compare what the user provided against what is ACTUALLY NEEDED to build a deployable SFMC journey. Only flag items that are:
- Truly absent (not merely implied or inferable)
- Critical for campaign execution (not nice-to-have details)
- Ambiguous in a way that could lead to a wrong design choice

DO NOT ask about items that are clearly stated, reasonably implied, or standard industry defaults.
DO NOT ask generic checklist questions. Every question must be grounded in the specific campaign context provided.

### Step 3: Generate Context-Specific Questions (if needed)
If you identify genuine gaps, create questions that:
- Reference the user's ACTUAL brand name, product, therapeutic area, or audience
- Provide options that are realistic for the user's specific domain (not generic marketing options)
- Show that you understood their campaign and are asking to refine it, not starting from scratch

## OUTPUT FORMAT
You MUST output valid JSON only. No markdown, no explanation.

If the requirements are SUFFICIENT (be lenient especially for uploaded documents — assume standard pharma defaults for minor gaps):
{{
  "needsQuestions": false,
  "questions": [],
  "extractedContext": "Detailed summary of everything understood from the requirements"
}}

If genuinely critical details are MISSING (maximum 3 questions):
{{
  "needsQuestions": true,
  "questions": [
    {{
      "id": 1,
      "question": "Context-specific question referencing the user's actual campaign details",
      "options": [
        {{ "label": "Specific option referencing user's domain", "description": "Concrete description tied to their brand/product/audience", "recommended": true }},
        {{ "label": "Another specific option", "description": "Alternative approach relevant to their therapeutic area" }},
        {{ "label": "Third specific option", "description": "Different strategy appropriate for their stated goals" }}
      ]
    }}
  ],
  "extractedContext": "Detailed summary of everything understood so far"
}}

## STRICT RULES FOR QUESTIONS AND OPTIONS

1. NEVER generate generic questions like "What is your campaign objective?" or "Who is your target audience?" if the user already stated these.
2. NEVER generate generic options like "Recommended Approach", "Standard Digital Plan", "Custom Configuration", or "Conservative Engagement". These are meaningless.
3. Every option label and description MUST reference the user's specific context. For example:
   - If the user mentioned "Cardiology" → options should reference cardiologists, interventional cardiologists, heart failure specialists, etc.
   - If the user mentioned a drug name → options should reference that drug's specific use cases, dosing scenarios, or patient populations.
   - If the user mentioned "email campaign" → options should specify email cadence, content types, or segmentation relevant to their stated audience.
4. Questions must feel like they come from a consultant who READ the brief, not from a form generator.
5. For uploaded documents: be EXTRA lenient. Only ask if something is genuinely ambiguous or has multiple valid interpretations that would change the campaign architecture.
6. Maximum 3 questions. Consolidate related gaps.
"""


def assumptions_prompt(full_context: str) -> str:
    return f"""You are a senior pharmaceutical marketing strategist. Analyze the following campaign context and user answers to identify any IMPACTFUL assumptions or ambiguities that remain unresolved.

## CAMPAIGN CONTEXT
{full_context}

## RULES
- Only flag genuinely impactful assumptions that could change the campaign flow design
- Reference the user's ACTUAL campaign details (brand, product, audience, timing, etc.)
- Explain what you assumed and WHY it matters
- Do NOT list obvious defaults or standard industry practices
- Do NOT list more than 3 assumptions. If everything is clear, return an empty array.
- Each assumption should be specific enough that overriding it would change the campaign architecture

BAD examples (too generic, NEVER write these):
- "Assumed standard email delivery"
- "Assumed Contact & Account objects as primary recipient targets"

GOOD examples (specific, references the brief):
- "The brief mentions 'follow-up after engagement' but doesn't specify whether engagement means email open or link click — assumed email open as the trigger"
- "No re-entry rule specified — assumed each HCP enters the journey only once"

## OUTPUT FORMAT
Return ONLY valid JSON. No markdown, no code blocks:
{{
  "assumptions": ["Specific assumption 1 referencing the campaign", "Specific assumption 2"]
}}
If everything is clear and no impactful assumptions remain, return:
{{ "assumptions": [] }}"""


def generation_prompt(context: str, answers: str | None) -> str:
    if answers:
        key_rule = ('The user provided specific answers to follow-up questions and/or resolved ambiguities. You MUST capture '
                    'each of these decisions in the "keyDecisions" array. Each decision should clearly state what was asked, '
                    'what the user chose, and how it impacts the campaign design. These decisions must also be reflected in '
                    'the relevant sections of the briefing (e.g., if the user specified email cadence, it must appear in both '
                    '"keyDecisions" AND "operationalRules").')
    else:
        key_rule = ('If no follow-up questions were asked, populate "keyDecisions" with any significant design assumptions '
                    'you made based on the brief (e.g., assumed engagement metric, assumed re-entry rules, assumed channel priority).')
    answers_block = f"## USER ANSWERS TO FOLLOW-UP QUESTIONS\n{answers}" if answers else ""
    return f"""
You are an expert pharmaceutical marketing consultant. Generate a comprehensive Campaign Briefing Document based on the provided information.

## CONTEXT
{context}

{answers_block}

## OUTPUT FORMAT
Return ONLY valid JSON. No markdown, no code blocks, no explanation.

## CRITICAL GENERATION RULES
1. STRICT FACT-BINDING: Populate this Campaign Briefing Document STRICTLY and EXCLUSIVELY using the facts, requirements, metrics, channels, and rules explicitly provided by the user in the CONTEXT and USER ANSWERS TO FOLLOW-UP QUESTIONS.
2. NO HALLUCINATION OR FABRICATION: Do NOT invent, extrapolate, or fabricate numbers, deciles, drug names, HCP segments, or channels that the user did not specify.
3. DYNAMIC CONTENT & COLUMNS: Only generate table entries, list items, and sections for entities and data points that the user actually discussed. For example, if only Email was mentioned, do not create entries for SMS or Veeva CRM.
4. UNSPECIFIED SECTIONS: If a section, metric, or channel was not mentioned by the user at all, explicitly write "Not specified by user" or omit dummy items rather than filling them with invented industry defaults.
5. PROFESSIONAL AESTHETICS: Use the JSON schema below as a design style guide for clean, executive presentation.
6. KEY DECISIONS — CRITICAL: {key_rule}

{{
  "campaignName": "Brand/Campaign Name",
  "campaignOverview": {{
    "objective": "Clear campaign objective statement",
    "product": "Product name",
    "indication": "Medical indication",
    "primaryAudience": "HCP specialties and segments",
    "primaryChannel": "Email/SMS/Multi-channel etc.",
    "complianceRole": "Description of compliance requirements"
  }},
  "keyDecisions": [
    {{
      "question": "The clarification question that was asked or the ambiguity that was identified",
      "decision": "The user's selected answer or the assumption that was accepted",
      "impact": "How this decision shapes the campaign design"
    }}
  ],
  "audienceSegmentation": {{
    "rule": "Segmentation rule description",
    "segments": [
      {{
        "name": "Segment 1",
        "hcpSpecialty": "Specialty name",
        "segmentType": "Type description",
        "details": ["Detail point 1", "Detail point 2", "Detail point 3"],
        "messageFocus": "Key message focus for this segment"
      }}
    ]
  }},
  "sfmcCapabilities": [
    {{ "capability": "Journey Builder", "use": "Description of how it's used" }},
    {{ "capability": "Contact Builder", "use": "Description" }},
    {{ "capability": "Email Studio", "use": "Description" }},
    {{ "capability": "Automation Studio", "use": "Description" }},
    {{ "capability": "Brand Logo and Data Views", "use": "Description" }},
    {{ "capability": "Suppression rules", "use": "Description" }}
  ],
  "journeyEntryCriteria": [
    "Criterion 1",
    "Criterion 2",
    "Criterion 3",
    "Criterion 4"
  ],
  "designPrinciples": [
    {{
      "category": "Core campaign rules",
      "principles": ["Principle 1", "Principle 2"]
    }},
    {{
      "category": "Safety and contraindicated communications",
      "principles": ["Principle 1", "Principle 2"]
    }},
    {{
      "category": "Consent and governance",
      "principles": ["Principle 1", "Principle 2"]
    }}
  ],
  "journeyFlow": [
    {{
      "timing": "Day 1",
      "stage": "Stage name",
      "actions": "Detailed action description"
    }}
  ],
  "decisionLogic": {{
    "keyQuestion": "Key decision question for the campaign",
    "rules": [
      {{ "id": 1, "rule": "Decision rule 1" }},
      {{ "id": 2, "rule": "Decision rule 2" }}
    ]
  }},
  "operationalRules": [
    "Rule 1: Maximum email frequency",
    "Rule 2: Content requirements",
    "Rule 3: Compliance requirements",
    "Rule 4: Opt-out handling"
  ],
  "measurementReporting": [
    {{ "tier": "Primary KPIs", "metrics": "Key metrics description" }},
    {{ "tier": "Secondary KPIs", "metrics": "Secondary metrics description" }},
    {{ "tier": "Compliance metrics", "metrics": "Compliance metrics description" }}
  ],
  "journeyEndGoals": "Description of the journey end goals and success criteria"
}}
"""


def update_prompt(existing: dict, modifications: str) -> str:
    return f"""
You are an expert pharmaceutical marketing consultant. You have an existing Campaign Briefing Document that needs to be updated based on the user's feedback.

## EXISTING BRIEFING
{json.dumps(existing, indent=2, ensure_ascii=False)}

## USER'S MODIFICATION REQUEST
"{modifications}"

## INSTRUCTIONS
1. Start with the EXISTING briefing as your base
2. Apply ONLY the requested changes from the user
3. STRICT FACT-BINDING: Do NOT invent, extrapolate, or fabricate numbers, deciles, drug names, HCP segments, or channels that the user did not specify.
4. Preserve all unchanged sections exactly as they are
5. Return the COMPLETE updated briefing in the same JSON format

## OUTPUT FORMAT
Return ONLY valid JSON. No markdown, no code blocks, no explanation. Same schema as the existing briefing.
"""


# ------------------------------------------------------------------ model calls ---------

def analyze(requirements: str, is_from_document: bool, workspace: str, should_stop=None) -> tuple[dict, dict]:
    """(analysis, usage). A reply that can't be read is treated as "no questions needed",
    exactly as Camille did."""
    try:
        data, usage = llm.complete_json(analysis_prompt(requirements, is_from_document, workspace), should_stop=should_stop)
    except ValueError:
        return {"needsQuestions": False, "questions": [], "extractedContext": requirements}, {}
    return data, usage


def normalize_questions(raw) -> list[dict]:
    """Questions as {id, question, options:[{label, description, recommended}]}, at most 3.
    Strings become write-in questions (no invented options, as in Camille's question card)."""
    out: list[dict] = []
    for i, q in enumerate(raw if isinstance(raw, list) else []):
        if isinstance(q, str):
            if q.strip():
                out.append({"id": i + 1, "question": q.strip(), "options": []})
            continue
        if not isinstance(q, dict):
            continue
        options = []
        for o in q.get("options") if isinstance(q.get("options"), list) else []:
            if isinstance(o, str) and o.strip():
                options.append({"label": o.strip(), "description": "", "recommended": False})
            elif isinstance(o, dict) and str(o.get("label") or "").strip():
                options.append({"label": str(o["label"]).strip(), "description": str(o.get("description") or "").strip(),
                                "recommended": bool(o.get("recommended"))})
        text = str(q.get("question") or "").strip() or "Please clarify:"
        out.append({"id": q.get("id") or i + 1, "question": text, "options": options})
        if len(out) >= MAX_QUESTIONS:
            break
    return out[:MAX_QUESTIONS]


def find_assumptions(full_context: str, should_stop=None) -> tuple[list[str], dict]:
    """Up to 3 impactful assumptions. Non-blocking: any failure means "none"."""
    try:
        data, usage = llm.complete_json(assumptions_prompt(full_context), should_stop=should_stop)
    except llm.Cancelled:
        raise
    except Exception as exc:  # noqa: BLE001 -- Camille: ambiguity analysis is non-blocking
        print(f"[campaign-creator] assumption review skipped ({exc})")
        return [], {}
    items = data.get("assumptions") if isinstance(data, dict) else None
    out = []
    for a in items if isinstance(items, list) else []:
        text = a if isinstance(a, str) else (a.get("text") or a.get("description") or json.dumps(a)) if isinstance(a, dict) else str(a)
        if str(text).strip():
            out.append(str(text).strip())
    return out[:MAX_ASSUMPTIONS], usage


def generate(context: str, answers: str | None, should_stop=None) -> tuple[dict, dict]:
    data, usage = llm.complete_json(generation_prompt(context, answers), should_stop=should_stop)
    return normalize_briefing(data), usage


def update(existing: dict, modifications: str, should_stop=None) -> tuple[dict, dict]:
    data, usage = llm.complete_json(update_prompt(existing, modifications), should_stop=should_stop)
    return normalize_briefing(data), usage


# ------------------------------------------------------------------ normalising ---------

def _text(v) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        return "; ".join(t for t in (_text(x) for x in v) if t)
    if isinstance(v, dict):
        return "; ".join(f"{k}: {_text(x)}" for k, x in v.items() if _text(x))
    return str(v).strip()


def _texts(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [t for t in (_text(x) for x in v) if t]
    t = _text(v)
    return [t] if t else []


def _records(v, keys: tuple[str, ...]) -> list[dict]:
    """A list of objects with string fields `keys`; a bare string fills the first key."""
    out = []
    for item in v if isinstance(v, list) else ([v] if v else []):
        if isinstance(item, dict):
            rec = {k: _text(item.get(k)) for k in keys}
        else:
            rec = {k: "" for k in keys}
            rec[keys[0]] = _text(item)
        if any(rec.values()):
            out.append(rec)
    return out


_OVERVIEW_KEYS = ("objective", "product", "indication", "primaryAudience", "primaryChannel", "complianceRole")


def normalize_briefing(raw) -> dict:
    """The briefing in exactly the schema the document view, the exports and the blueprint
    agents read, whatever shape the model returned it in."""
    b = raw if isinstance(raw, dict) else {}
    ov_raw = b.get("campaignOverview") if isinstance(b.get("campaignOverview"), dict) else {}
    overview = {k: _text(ov_raw.get(k)) for k in _OVERVIEW_KEYS}
    for k, v in ov_raw.items():
        if k not in overview and _text(v):
            overview[k] = _text(v)
    seg_raw = b.get("audienceSegmentation") if isinstance(b.get("audienceSegmentation"), dict) else {}
    segments = []
    for s in seg_raw.get("segments") if isinstance(seg_raw.get("segments"), list) else []:
        if isinstance(s, dict):
            seg = {"name": _text(s.get("name")), "hcpSpecialty": _text(s.get("hcpSpecialty")),
                   "segmentType": _text(s.get("segmentType")), "details": _texts(s.get("details")),
                   "messageFocus": _text(s.get("messageFocus"))}
        else:
            seg = {"name": _text(s), "hcpSpecialty": "", "segmentType": "", "details": [], "messageFocus": ""}
        if any(seg.values()):
            segments.append(seg)
    principles = []
    for p in b.get("designPrinciples") if isinstance(b.get("designPrinciples"), list) else []:
        if isinstance(p, dict):
            rec = {"category": _text(p.get("category")), "principles": _texts(p.get("principles"))}
        else:
            rec = {"category": "", "principles": _texts(p)}
        if rec["category"] or rec["principles"]:
            principles.append(rec)
    dl_raw = b.get("decisionLogic") if isinstance(b.get("decisionLogic"), dict) else {}
    rules = []
    for i, r in enumerate(dl_raw.get("rules") if isinstance(dl_raw.get("rules"), list) else []):
        text = _text(r.get("rule")) if isinstance(r, dict) else _text(r)
        if text:
            rid = r.get("id") if isinstance(r, dict) and r.get("id") not in (None, "") else i + 1
            rules.append({"id": rid, "rule": text})
    return {
        "campaignName": _text(b.get("campaignName")) or "Campaign Briefing",
        "campaignOverview": overview,
        "keyDecisions": _records(b.get("keyDecisions"), ("question", "decision", "impact")),
        "audienceSegmentation": {"rule": _text(seg_raw.get("rule")), "segments": segments},
        "sfmcCapabilities": _records(b.get("sfmcCapabilities"), ("capability", "use")),
        "journeyEntryCriteria": _texts(b.get("journeyEntryCriteria")),
        "designPrinciples": principles,
        "journeyFlow": _records(b.get("journeyFlow"), ("timing", "stage", "actions")),
        "decisionLogic": {"keyQuestion": _text(dl_raw.get("keyQuestion")), "rules": rules},
        "operationalRules": _texts(b.get("operationalRules")),
        "measurementReporting": _records(b.get("measurementReporting"), ("tier", "metrics")),
        "journeyEndGoals": _text(b.get("journeyEndGoals")),
    }


# ------------------------------------------------------------------ rules fallback ------

def as_text(b: dict) -> str:
    """The briefing as readable text, for the blueprint agents' prompt."""
    b = normalize_briefing(b)
    ov = b["campaignOverview"]
    out = [f"Campaign: {b['campaignName']}", "", "Campaign overview:"]
    out += [f"- {_label(k)}: {v}" for k, v in ov.items() if v]
    if b["keyDecisions"]:
        out += ["", "Key decisions:"] + [f"- {d['question']} -> {d['decision']}" + (f" (impact: {d['impact']})" if d["impact"] else "")
                                         for d in b["keyDecisions"]]
    seg = b["audienceSegmentation"]
    out += ["", f"Audience segmentation rule: {seg['rule'] or NOT_SPECIFIED}"]
    for s in seg["segments"]:
        out.append(f"- Segment {s['name']}: specialty {s['hcpSpecialty']}; type {s['segmentType']}; "
                   f"message focus {s['messageFocus']}" + (f"; details: {'; '.join(s['details'])}" if s["details"] else ""))
    if b["sfmcCapabilities"]:
        out += ["", "SFMC capabilities:"] + [f"- {c['capability']}: {c['use']}" for c in b["sfmcCapabilities"]]
    if b["journeyEntryCriteria"]:
        out += ["", "Journey entry criteria:"] + [f"- {c}" for c in b["journeyEntryCriteria"]]
    if b["designPrinciples"]:
        out += ["", "Design principles:"] + [f"- {p['category']}: {'; '.join(p['principles'])}" for p in b["designPrinciples"]]
    if b["journeyFlow"]:
        out += ["", "Journey flow (step by step):"] + [f"- {j['timing']} | {j['stage']} | {j['actions']}" for j in b["journeyFlow"]]
    dl = b["decisionLogic"]
    out += ["", f"Decision logic — key question: {dl['keyQuestion'] or NOT_SPECIFIED}"] + [f"- Rule {r['id']}: {r['rule']}" for r in dl["rules"]]
    if b["operationalRules"]:
        out += ["", "Operational rules:"] + [f"- {r}" for r in b["operationalRules"]]
    if b["measurementReporting"]:
        out += ["", "Measurement & reporting:"] + [f"- {m['tier']}: {m['metrics']}" for m in b["measurementReporting"]]
    out += ["", f"Journey end goals: {b['journeyEndGoals'] or NOT_SPECIFIED}"]
    return "\n".join(out)


def _label(key: str) -> str:
    """campaignOverview key -> label, as Camille's document view did ("primaryAudience" ->
    "Primary Audience")."""
    spaced = re.sub(r"([A-Z])", r" \1", key).strip()
    return spaced[:1].upper() + spaced[1:]


def _cell(v) -> str:
    return re.sub(r"\s+", " ", str(v or "")).replace("|", "/").strip() or "—"


def as_markdown(b: dict) -> str:
    """The briefing as markdown in the shapes plan_export understands (headings, tables,
    bullets), for the Word and PDF downloads. Section numbering follows the document view:
    Key Decisions is section 2 when present, and every later section keeps its number."""
    b = normalize_briefing(b)
    md: list[str] = ["CAMPAIGN BRIEFING DOCUMENT — Confidential", ""]

    def table(header: list[str], rows: list[list[str]]) -> None:
        md.append("| " + " | ".join(header) + " |")
        md.append("|" + "|".join("---" for _ in header) + "|")
        for r in rows:
            md.append("| " + " | ".join(_cell(c) for c in r) + " |")
        md.append("")

    md += ["## 1. Campaign Overview", ""]
    table(["Field", "Detail"], [[_label(k), v] for k, v in b["campaignOverview"].items()])
    if b["keyDecisions"]:
        md += ["## 2. Key Decisions & Assumptions", ""]
        table(["Decision Point", "User Decision", "Impact on Campaign"], [[d["question"], d["decision"], d["impact"]] for d in b["keyDecisions"]])
    seg = b["audienceSegmentation"]
    md += ["## 3. Audience Segmentation", "", f"*Rule: {seg['rule'] or NOT_SPECIFIED}*", ""]
    for s in seg["segments"]:
        md += [f"### {s['name'] or 'Segment'}", "", f"**HCP Specialty:** {s['hcpSpecialty'] or '—'}", "",
               f"**Segment:** {s['segmentType'] or '—'}", ""]
        if s["details"]:
            md += [f"- {d}" for d in s["details"]] + [""]
        if s["messageFocus"]:
            md += [f"**Message focus:** {s['messageFocus']}", ""]
    md += ["## 4. SFMC Capabilities Used", ""]
    if b["sfmcCapabilities"]:
        table(["Capability", "Use"], [[c["capability"], c["use"]] for c in b["sfmcCapabilities"]])
    else:
        md += [NOT_SPECIFIED, ""]
    md += ["## 5. Journey Entry Criteria", ""]
    md += ([f"- {c}" for c in b["journeyEntryCriteria"]] or [NOT_SPECIFIED]) + [""]
    md += ["## 6. Design Principles (incl. Consent Governance)", ""]
    if b["designPrinciples"]:
        table(["Category", "Principles"], [[p["category"], "; ".join(p["principles"])] for p in b["designPrinciples"]])
    else:
        md += [NOT_SPECIFIED, ""]
    md += ["## 7. Journey Flow (Step-by-Step)", ""]
    if b["journeyFlow"]:
        table(["Timing", "Stage", "Actions"], [[j["timing"], j["stage"], j["actions"]] for j in b["journeyFlow"]])
    else:
        md += [NOT_SPECIFIED, ""]
    dl = b["decisionLogic"]
    md += ["## 8. Decision Logic (Compact)", "", f"*Key decision question: {dl['keyQuestion'] or NOT_SPECIFIED}*", ""]
    md += [f"- {r['rule']}" for r in dl["rules"]] + [""]
    md += ["## 9. Operational Rules & Safeguards", ""]
    md += ([f"- {r}" for r in b["operationalRules"]] or [NOT_SPECIFIED]) + [""]
    md += ["## 10. Measurement & Reporting", ""]
    if b["measurementReporting"]:
        table(["Tier", "Metrics"], [[m["tier"], m["metrics"]] for m in b["measurementReporting"]])
    else:
        md += [NOT_SPECIFIED, ""]
    md += ["## 11. Journey End Goals", "", b["journeyEndGoals"] or NOT_SPECIFIED, ""]
    return "\n".join(md)
