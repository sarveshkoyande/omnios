"""Redesign Phase 5 assistants over a typed artifact: Refine (C13), Check guidelines (C12) and
brand-grounded Chat. All LLM-only (rule R1); an unreachable LLM raises LLMUnavailable (R2).

Nothing here writes to the artifact. Refine returns *proposed* field changes that the user
accepts or rejects one by one (accepted ones are then saved as a new version by
v3_artifacts.edit_fields); Check returns issues to highlight.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import brand_kit  # noqa: E402
from llm_json import complete_json  # noqa: E402


def _fields(artifact: dict) -> list[dict]:
    return [{"id": f["id"], "section": s["title"], "label": f["label"], "value": f["value"], "source": f["source"]}
            for s in artifact["artifact"]["sections"] for f in s["fields"]]


def _guardrails(brand: str) -> dict:
    kit = brand_kit.kit_for(brand) or {}
    g = kit.get("guardrails") or {}
    return {
        "approved_indication": kit.get("approved_indication", ""),
        "safety_reference": kit.get("safety_reference", ""),
        "approved_claims": [c.get("text") for c in kit.get("claims", []) if c.get("status") == "approved"],
        "other_claims": [{"text": c.get("text"), "status": c.get("status"), "fair_balance": c.get("fair_balance")}
                         for c in kit.get("claims", []) if c.get("status") != "approved"],
        "dos": [d.get("text") for d in g.get("dos", [])],
        "donts": [d.get("text") for d in g.get("donts", [])],
        "voice_do": kit.get("voice_do", []),
        "voice_dont": kit.get("voice_dont", []),
    }


_REFINE = """You edit a pharma campaign brief. The brief is structured: a list of fields, each \
with an id, label, current value and source. You get the user's instruction and the brand's \
compliance guardrails.

Propose the smallest set of field changes that carries out the instruction. Rules:
- Only change fields that exist (use their exact ids). Never add fields.
- Never invent facts, numbers, dates, claims or data the brief or instruction doesn't contain.
- Claims must come from approved_claims; respect the donts and voice rules.
- If a field says "Needs input" and the instruction doesn't supply the answer, leave it.
- If the instruction can't be done safely, propose no changes and say why.

Reply with JSON only:
{"reply": "<one or two plain sentences to the user>",
 "changes": [{"field_id": "<id>", "new_value": "<text>", "why": "<one short line>"}]}"""


def refine(artifact: dict, instruction: str) -> dict:
    fields = _fields(artifact)
    data = complete_json(_REFINE, {"instruction": instruction, "fields": fields,
                                   "guardrails": _guardrails(artifact["brand"])}, 3000)
    by_id = {f["id"]: f for f in fields}
    changes = []
    for c in data.get("changes") or []:
        fid, new = c.get("field_id"), str(c.get("new_value") or "").strip()
        if fid in by_id and new and new != by_id[fid]["value"]:
            changes.append({"field_id": fid, "label": by_id[fid]["label"], "old_value": by_id[fid]["value"],
                            "new_value": new, "why": str(c.get("why") or "").strip()})
    return {"reply": str(data.get("reply") or "").strip(), "changes": changes}


_CHECK = """You are a pharma MLR pre-reviewer. Check a structured campaign brief against the \
brand's compliance guardrails: approved indication, approved claims (anything claim-like that \
isn't an approved claim is an issue), claims that need fair balance, the dos and donts, and \
the voice rules. Also flag promotional overstatement, off-label implications, superlatives \
without support, and comparative claims.

Only report real issues, each tied to one field id. Don't flag "Needs input" fields (those \
are tracked separately). If the brief is clean, return no issues.

Reply with JSON only:
{"summary": "<one plain sentence>",
 "issues": [{"field_id": "<id>", "severity": "high|medium|low", "issue": "<what's wrong>",
             "suggestion": "<how to fix it>"}]}"""


def check(artifact: dict) -> dict:
    fields = _fields(artifact)
    data = complete_json(_CHECK, {"fields": fields, "guardrails": _guardrails(artifact["brand"])}, 3000)
    by_id = {f["id"]: f for f in fields}
    issues = []
    for i in data.get("issues") or []:
        fid = i.get("field_id")
        if fid in by_id:
            sev = i.get("severity") if i.get("severity") in ("high", "medium", "low") else "medium"
            issues.append({"field_id": fid, "label": by_id[fid]["label"], "severity": sev,
                           "issue": str(i.get("issue") or "").strip(), "suggestion": str(i.get("suggestion") or "").strip()})
    missing = [{"field_id": f["id"], "label": f["label"]} for s in artifact["artifact"]["sections"]
               for f in s["fields"] if f.get("needs_input")]
    return {"summary": str(data.get("summary") or "").strip(), "issues": issues, "needs_input": missing}


_CHAT = """You are Omni, an assistant for pharma omnichannel marketers. Answer the question \
using only the brand facts given (and general marketing knowledge, labelled as such). Never \
invent brand data, claims, numbers or results. If the facts don't cover it, say so. Suggest \
up to 2 agents from the list when one would help.

Reply with JSON only:
{"reply": "<plain text, at most 120 words>", "agent_ids": ["<id>", ...]}"""


def chat(question: str, brand: str | None, agents: list[dict]) -> dict:
    kit = (brand_kit.kit_for(brand) or {}) if brand else {}
    facts = {k: kit.get(k) for k in ("company", "therapy_area", "indication", "lifecycle_stage", "key_objective",
                                      "success_measure", "positioning_statement", "core_claim", "market_share",
                                      "primary_audience", "territory")} if kit else {}
    if kit:
        facts["pillars"] = [m.get("pillar") for m in kit.get("message_hierarchy", [])]
        facts["competitors"] = kit.get("competitors", [])
        facts["personas"] = {k: [p.get("name") for p in v] for k, v in (kit.get("personas") or {}).items()}
    data = complete_json(_CHAT, {"question": question, "brand": brand or "none selected", "brand_facts": facts,
                                 "agents": agents}, 1500)
    known = {a["id"] for a in agents}
    return {"reply": str(data.get("reply") or "").strip(),
            "agent_ids": [i for i in (data.get("agent_ids") or []) if i in known][:2]}
