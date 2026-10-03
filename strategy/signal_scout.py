"""Signal Scout agent: what changed in the market, and what should the brand team do about it.

Rebuilt as an agent from the Signal Scout pilot UI (three views: Synthesis & action, Market and
treatment landscape, Competitive landscape, plus signal history). Each step is a separate skill run
one at a time from the agent workspace, each grounded in the brand's Brand IQ kit (label, clinical
data, competitors, audience intel, US geography, brand plan fields) and in the earlier steps' output.

US only, pharma only. Rules: the model uses ONLY the evidence given and its well-established public
knowledge, says which (`basis`), never invents trial figures, and gives `reasoning` for every step.
Channel activity is the model's estimate from public knowledge, not observed media data, and is
labelled so. With no model a skill raises LLMUnavailable and writes nothing (R2).

Readouts are kept per brand under DATA_DIR/signal_scout/<brand>.json: `current` (being built) and
`previous` (the last completed readout), so the history step can say what changed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import brand_kit  # noqa: E402
import public_sources as ps  # noqa: E402
from llm_json import LLMUnavailable, complete_json  # noqa: E402
from paths import data_path  # noqa: E402

SKILLS = [
    {"id": "market", "name": "Scan the market & treatment landscape", "view": "market",
     "does": "Treatment gaps, unmet need and US market indicators for the brand's condition."},
    {"id": "clinical", "name": "Review key clinical evidence", "view": "market",
     "does": "The pivotal studies behind the brand and the evidence records that matter."},
    {"id": "competitive_set", "name": "Map the competitive set", "view": "competitive",
     "does": "Who matters: direct competitors and comparators, their mechanism, route and positioning."},
    {"id": "positioning", "name": "Compare positioning & evidence", "view": "competitive",
     "does": "How the competitive set differentiates, dimension by dimension."},
    {"id": "messages", "name": "Analyse message territory", "view": "competitive",
     "does": "Which themes are crowded, competitor-owned or underrepresented."},
    {"id": "channels", "name": "Estimate channel activity", "view": "competitive",
     "does": "Where competitors are visibly active across HCP and digital channels."},
    {"id": "synthesis", "name": "Synthesise the signals", "view": "synthesis",
     "does": "Only the signals that materially affect a brand decision, and where they converge."},
    {"id": "actions", "name": "Recommend team actions", "view": "synthesis",
     "does": "Specific actions for brand, content, channel and intelligence teams, linked to signals."},
    {"id": "history", "name": "Compare with the last readout", "view": "synthesis",
     "does": "Which signals are new, persistent, strengthened, weakened or resolved."},
]
_IDS = [s["id"] for s in SKILLS]

STEPS = [
    {"id": "understand", "name": "Understand the brief", "skills": []},
    {"id": "market", "name": "Scan the market", "skills": ["market", "clinical"]},
    {"id": "competition", "name": "Map the competition", "skills": ["competitive_set", "positioning", "messages", "channels"]},
    {"id": "act", "name": "Synthesise & act", "skills": ["synthesis", "actions", "history"]},
]

_SYS = ("You are Signal Scout, a US pharmaceutical competitive and market intelligence analyst working for the "
        "brand team. Scope: the United States only. Use the evidence provided first; you may add well-established "
        "public knowledge (approved products, mechanisms, routes, published pivotal trials) but mark each item's "
        "`basis` as 'Brand IQ' or 'Public knowledge'. Never invent trial names, figures or claims; when unsure, leave "
        "a value out and say so. Your JSON object MUST have a top-level `reasoning` array: 3-6 short sentences on what "
        "you used, what you concluded and why. Reply with a single JSON object only.")

_SHAPES = {
    "market": ('Describe the US market and treatment landscape for the brand\'s condition: 3 headline indicators '
               '(value + label, e.g. share of patients not at goal), one market insight, and 3-5 evidence records.\n'
               'Shape: {"indicators":[{"value":"","label":"","source":"","basis":""}],"insight":"",'
               '"evidence_records":[{"type":"CLINICAL|MARKET|REG|GUIDELINE","title":"","detail":"","status":"","source":""}],"reasoning":[]}'),
    "clinical": ('List the brand\'s key clinical evidence (from the label / clinical data in Brand IQ): 1-3 studies with '
                 'their headline metrics exactly as published.\n'
                 'Shape: {"studies":[{"name":"","phase":"","publication":"","relevance":"High|Medium|Low",'
                 '"metrics":[{"value":"","label":""}],"source":""}],"reasoning":[]}'),
    "competitive_set": ('Map the competitive set that matters for this brand in the US: 3-6 entities, direct competitors '
                        'first then the standard-of-care comparator.\n'
                        'Shape: {"entities":[{"name":"","generic":"","company":"","type":"Direct|Comparator","mechanism":"",'
                        '"route_dosing":"","positioning":"","key_metric":{"label":"","value":""},"outcomes":"",'
                        '"activity":"Very high|High|Moderate|Low","tags":[],"basis":""}],"reasoning":[]}'),
    "positioning": ('Compare how the brand and the competitive set differentiate. 5-7 dimensions (route, efficacy, '
                    'outcomes, dosing/adherence story, safety, core positioning...). Columns = the brand first, then '
                    'the competitive set names.\n'
                    'Shape: {"columns":[],"rows":[{"dimension":"","values":[]}],"reasoning":[]}'),
    "messages": ('Analyse the message territory: 4-6 themes, each Crowded, Competitor-owned, Contested or '
                 'Underrepresented, with who owns it and whether it is a potential territory for the brand.\n'
                 'Shape: {"themes":[{"theme":"","status":"","detail":"","owners":[],"potential":""}],"reasoning":[]}'),
    "channels": ('Estimate where each direct competitor is visibly active across HCP channels (LinkedIn/HCP social, '
                 'KOL webinars, HCP digital platforms, rep email, congress, paid search). This is an estimate from '
                 'public knowledge, not observed spend.\n'
                 'Shape: {"entities":[{"name":"","channels":[{"channel":"","level":"Very high|High|Moderate|Low"}]}],'
                 '"pattern":"","reasoning":[]}'),
    "synthesis": ('Synthesise: only the 2-4 signals that materially affect a brand decision, an executive headline '
                  '(the clearest opportunity or threat), a short summary and how many signals converge.\n'
                  'Shape: {"headline":"","summary":"","confidence":"High|Medium|Low","converging":0,'
                  '"signals":[{"id":"01","category":"","materiality":"High|Medium|Low","title":"","detail":"",'
                  '"source":"","confidence":"High|Medium|Low"}],"reasoning":[]}'),
    "actions": ('Recommend 3-5 specific actions for the brand team, each owned by a function (Brand / Strategy, '
                'Content / Medical, Channel / Media, Brand Intelligence), linked to signal ids, with priority and timing.\n'
                'Shape: {"actions":[{"function":"","area":"","title":"","detail":"","linked_signals":[],'
                '"priority":"High|Medium|Low","timing":"Next|Follow-up|Later"}],"reasoning":[]}'),
    "history": ('Compare the current signals with the previous readout\'s signals. Mark each as new, persistent, '
                'strengthened, weakened or resolved. If there is no previous readout, say this is the baseline.\n'
                'Shape: {"previous_summary":"","current_summary":"","changes":[{"signal":"","status":"new|persistent|'
                'strengthened|weakened|resolved","note":""}],"reasoning":[]}'),
}


def _path(brand: str) -> Path:
    return data_path("signal_scout", f"{brand}.json")


def load(brand: str) -> dict:
    p = _path(brand)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"brand": brand, "current": None, "previous": None}


def _save(brand: str, rec: dict) -> dict:
    p = _path(brand)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    return rec


def start(brand: str, focus: str) -> dict:
    """Begin a new readout. The last complete one becomes `previous` (for the history step)."""
    if not brand_kit.kit_for(brand):
        raise KeyError(brand)
    rec = load(brand)
    cur = rec.get("current")
    if cur and (cur.get("sections") or {}).get("synthesis"):
        rec["previous"] = cur
    rec["current"] = {"focus": focus, "started": ps._today(), "sections": {}, "reasoning": {}, "worklist": []}
    return _save(brand, rec)


def _grounding(brand: str, kit: dict) -> dict:
    prof = kit.get("product_profile") or {}
    return {
        "brand": brand, "generic": kit.get("generic"), "company": kit.get("company"),
        "therapy_area": kit.get("therapy_area"), "indication": kit.get("indication"),
        "indications": [{k: i.get(k) for k in ("name", "condition", "population", "line")} for i in kit.get("indications") or []],
        "positioning": kit.get("positioning_statement"), "core_claim": kit.get("core_claim"),
        "key_objective": kit.get("key_objective"), "unmet_need": kit.get("unmet_need"),
        "situation": kit.get("brand_situation"), "strategic_imperatives": kit.get("strategic_imperatives"),
        "clinical_data": kit.get("clinical_data"), "message_hierarchy": kit.get("message_hierarchy"),
        "label": {k: ((prof.get(k) or {}).get("value") or "")[:1500] for k in ("indications", "clinical_studies", "dosage")
                  if isinstance(prof.get(k), dict)},
        "us_approval": (prof.get("us_approval") or {}).get("value"),
        "competitors": [{k: c.get(k) for k in ("name", "type", "strength", "weakness", "threat", "source")}
                        for c in kit.get("competitors") or []][:12],
        "audience_segments": kit.get("audience_segments"),
        "audience_intel": {k: (v[:6] if isinstance(v, list) else v) for k, v in (kit.get("audience_intel") or {}).items()},
        "us_geography": [{"measure": l.get("measure"), "top_states": [s["state"] for s in (l.get("states") or [])[:5]]}
                         for l in (kit.get("us_geography") or {}).get("layers") or []],
    }


def run_skill(brand: str, skill: str) -> dict:
    """Run one Signal Scout skill; saves its section into the current readout."""
    if skill not in _IDS:
        raise ValueError(f"Unknown skill '{skill}'")
    kit = brand_kit.kit_for(brand)
    if not kit:
        raise KeyError(brand)
    rec = load(brand)
    if not rec.get("current"):
        rec = start(brand, "")
    cur = rec["current"]
    payload = {"focus": cur.get("focus") or "", "brand_iq": _grounding(brand, kit), "earlier_steps": cur.get("sections") or {}}
    if skill == "history":
        prev = rec.get("previous") or {}
        payload = {"current_signals": (cur["sections"].get("synthesis") or {}).get("signals"),
                   "previous_signals": ((prev.get("sections") or {}).get("synthesis") or {}).get("signals"),
                   "previous_date": prev.get("started")}
    out = complete_json(_SYS + "\n" + _SHAPES[skill], payload, max_tokens=3500)
    reasoning = out.pop("reasoning", None) or []
    if isinstance(reasoning, str):
        reasoning = [reasoning]
    cur["sections"][skill] = out
    cur["reasoning"][skill] = reasoning
    cur["updated"] = ps._today()
    _save(brand, rec)
    return {"readout": cur, "reasoning": reasoning}


def toggle_worklist(brand: str, index: int) -> dict:
    rec = load(brand)
    cur = rec.get("current") or {}
    wl = set(cur.get("worklist") or [])
    wl.symmetric_difference_update({index})
    cur["worklist"] = sorted(wl)
    _save(brand, rec)
    return cur


def acknowledge(brand: str, focus: str) -> dict:
    """Step 1: read the focus (or none) and Brand IQ's coverage; say what the scan can and can't rely on."""
    kit = brand_kit.kit_for(brand)
    if not kit:
        raise KeyError(brand)
    g = _grounding(brand, kit)
    coverage = {k: bool(v) for k, v in g.items() if k not in ("brand",)}
    rec = load(brand)
    return complete_json(
        "You are Signal Scout about to scan the US market for a pharma brand. Read the person's focus (may be empty) "
        "and which Brand IQ inputs are present. Reply in plain words: what you understood the scan should answer "
        "(if no focus, say you'll run an open scan for the most material signals), what Brand IQ gives you, what is "
        "missing and what that means (e.g. no clinical data -> evidence comes from public knowledge, marked so), "
        "and whether there is a previous readout to compare with. Reply with one JSON object.\n"
        'Shape: {"mode":"focused|open","understood":"","have":[{"what":"","detail":""}],'
        '"missing":[{"what":"","impact":""}],"approach":[""],"question":""}',
        {"brand": brand, "focus": focus, "brand_iq_present": coverage,
         "competitors": [c.get("name") for c in kit.get("competitors") or []][:10],
         "previous_readout": bool((rec.get("current") or {}).get("sections"))}, max_tokens=1200)


__all__ = ["SKILLS", "STEPS", "acknowledge", "load", "start", "run_skill", "toggle_worklist", "LLMUnavailable"]
