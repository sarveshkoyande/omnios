"""
Deterministic conversational slot-filler for the campaign-planning agent.

The agent leads the conversation: it asks what the user is planning, then extracts
brand / therapy area / lifecycle phase / (optional) budget from free-text replies --
no forms, no submit button. When all required slots are captured it signals the
orchestrator to start the multi-agent research run.

This is intentionally a rules-based interpreter (no LLM dependency, so it runs fully
offline). `interpret_message()` is the single seam -- swap its body for an Anthropic
call later and the rest of the app is unchanged.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import time

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from brand_catalog import lookup_brand  # noqa: E402
from brand_memory import get_brand_memory  # noqa: E402
from lifecycle import LIFECYCLE_BY_KEY  # noqa: E402
_seeds = json.loads((BASE_DIR / "config" / "seed_terms.json").read_text())
KNOWN_BRANDS = [b.lower() for b in _seeds.get("drugs", [])]
KNOWN_THERAPIES = [t.lower() for t in _seeds.get("therapy_areas", [])]

LIFECYCLE_KEYWORDS = {
    "launch": ["launch", "pre-launch", "prelaunch", "about to launch", "newly approved", "new approval", "just approved", "going to launch"],
    "growth": ["growth", "growing", "gaining traction", "scaling", "uptake", "ramp", "early adoption", "building share"],
    "mature": ["mature", "established", "in-line", "in line", "routine", "defend", "defending", "steady state", "well established"],
    "loe": ["loe", "loss of exclusivity", "patent cliff", "patent expir", "going generic", "generic erosion", "decline", "end of life", "biosimilar"],
}

_FILLER_LEADS = ["it's", "its", "it is", "for", "in", "the", "a", "an", "we're", "we are", "planning", "brand", "drug", "molecule", "therapy area is", "indication is", "the brand is", "brand is"]

_DEFERRALS = ["you decide", "you choose", "you pick", "your call", "your choice", "whatever you think",
              "whatever you want", "up to you", "not sure", "no idea", "i don't know", "i dont know",
              "idk", "dunno", "anything", "you tell me", "surprise me", "doesn't matter", "does not matter"]


def _is_deferral(text: str) -> bool:
    t = text.strip().lower().strip(".!?")
    return any(d in t for d in _DEFERRALS)


def _match_lifecycle(text: str) -> str | None:
    t = text.lower()
    for key, kws in LIFECYCLE_KEYWORDS.items():
        for kw in kws:
            if kw in t:
                return key
    return None


def _match_known_brand(text: str) -> str | None:
    t = text.lower()
    for i, b in enumerate(KNOWN_BRANDS):
        if re.search(rf"\b{re.escape(b)}\b", t):
            return _seeds["drugs"][i]  # original casing
    return None


def _match_known_therapy(text: str) -> str | None:
    t = text.lower()
    for i, th in enumerate(KNOWN_THERAPIES):
        if th in t:
            return _seeds["therapy_areas"][i]
    return None


def _clean_freetext(text: str) -> str:
    s = text.strip().strip(".!?,")
    low = s.lower()
    for lead in sorted(_FILLER_LEADS, key=len, reverse=True):
        if low.startswith(lead + " "):
            s = s[len(lead) + 1:].strip()
            low = s.lower()
    return s


def _parse_budget(text: str) -> float | None:
    t = text.lower()
    # Whole-word match so a skip token can't fire on a substring (e.g. "na" inside "additional").
    if re.search(r"\b(skip|no budget|not sure|none|later|don't have|dont have|n/?a)\b", t):
        return 0.0
    m = re.search(r"\$?\s*([\d][\d,\.]*)\s*(k|m|mm|thousand|million|bn|billion)?", t)
    if not m:
        return None
    try:
        num = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    unit = (m.group(2) or "").strip()
    if unit in ("k", "thousand"):
        num *= 1_000
    elif unit in ("m", "mm", "million"):
        num *= 1_000_000
    elif unit in ("bn", "billion"):
        num *= 1_000_000_000
    return num


# --------------------------------------------------------------------- brief extraction ---
# The intake is a fill-in-the-blanks paragraph:
#   "[Name] is an omnichannel campaign for [Brand], a [Molecule] indicated for [Indication],
#    currently in the [Lifecycle Stage]. We are planning to engage [Audience] in [Region]
#    over [Duration] with a budget of [Budget]. Our goal is to [Objective] by driving [KPI].
#    We already have [Assets] available and plan to use [Channels], while considering
#    [Constraints]. Additional context or known challenges include [Notes]."
# Each field is pulled independently off its connective phrase, so a reordered or partially
# filled brief still yields whatever clauses ARE present (a missing clause just stays empty).
# The core matchers in _extract() also scan the whole text, so brand/lifecycle/budget are
# caught even when the surrounding template wording differs.
_BRIEF_RE = {
    "campaign_name":      re.compile(r"^\s*(.+?)\s+is an?\b[^.]*?\bcampaign\b", re.I),
    "brand":              re.compile(r"campaign\s+for\s+(.+?)(?=,|\.|\s+a\s+[A-Za-z])", re.I),
    "molecule":           re.compile(r",\s*an?\s+(.+?)\s+indicated\s+for", re.I),
    "indication":         re.compile(r"indicated\s+for\s+(.+?)(?=,|\.|;|\s+currently\b)", re.I),
    "lifecycle_text":     re.compile(r"currently\s+in(?:\s+the)?\s+(.+?)(?=[.,;]|$)", re.I),
    "duration":           re.compile(r"\bover\s+(.+?)(?=\s+with\s+a\s+budget\b|[.,;]|$)", re.I),
    "objective":          re.compile(r"goal\s+is\s+to\s+(.+?)(?=\s+by\s+driving\b|[.]|$)", re.I),
    "kpi":                re.compile(r"by\s+driving\s+(.+?)(?=[.]|$)", re.I),
    "existing_assets":    re.compile(r"already\s+have\s+(.+?)(?=\s+available\b|\s+and\s+plan\s+to\s+use\b|[.]|$)", re.I),
    "preferred_channels": re.compile(r"plan\s+to\s+use\s+(.+?)(?=\s+while\s+considering\b|[.]|$)", re.I),
    "constraints":        re.compile(r"while\s+considering\s+(.+?)(?=[.]|$)", re.I),
    "notes":              re.compile(r"(?:challenges|context|notes)[^.]*?\binclude\s+(.+?)(?=$|\.)", re.I),
}
# The "engage [Audience] in [Region]" clause needs both halves captured together so the
# generic "in ..." doesn't run past the region.
_BRIEF_ENGAGE_RE = re.compile(r"engage\s+(?P<audience>.+?)\s+in\s+(?P<geography>.+?)(?=\s+over\b|\s+with\s+a\s+budget\b|[.,;]|$)", re.I)
# Stop on a sentence-ending period (". " or end) or a comma/semicolon -- NOT on the decimal
# point inside an amount like "$2.5M". _parse_budget then reads the first number in the clause.
_BRIEF_BUDGET_RE = re.compile(r"budget\s+of\s+([^,;]+?)(?=\.\s|\.$|[,;]|$)", re.I)


def _clean_field(v: str) -> str:
    """Trim a captured field and drop unfilled '[Placeholder]' tokens and empty strings."""
    v = (v or "").strip().strip(".,;:").strip()
    if not v or (v.startswith("[") and v.endswith("]")):
        return ""
    return v[:400]


def _looks_like_brief(message: str) -> bool:
    """Only run the paragraph extractor on something that reads like the intake brief, so
    short conversational replies never trip a connective by accident."""
    t = message.lower()
    return sum(k in t for k in ("campaign for", "indicated for", "goal is to", "budget of",
                                "plan to use", "currently in", "we are planning", "engage")) >= 2


def _extract_brief(message: str, slots: dict) -> None:
    """Fill any still-empty brief slots from the fill-in-the-blanks paragraph. Never
    overwrites a slot that already has a value."""
    if not _looks_like_brief(message):
        return
    for field, rx in _BRIEF_RE.items():
        if field == "lifecycle_text":
            if not slots.get("lifecycle_key"):
                m = rx.search(message)
                if m:
                    lc = _match_lifecycle(_clean_field(m.group(1)))
                    if lc:
                        slots["lifecycle_key"] = lc
            continue
        if not slots.get(field):
            m = rx.search(message)
            if m:
                slots[field] = _clean_field(m.group(1))
    m = _BRIEF_ENGAGE_RE.search(message)
    if m:
        if not slots.get("audience"):
            slots["audience"] = _clean_field(m.group("audience"))
        if not slots.get("geography"):
            slots["geography"] = _clean_field(m.group("geography"))
    if not slots.get("budget"):
        mb = _BRIEF_BUDGET_RE.search(message)
        if mb:
            b = _parse_budget(mb.group(1))
            if b:
                slots["budget"] = b


# --------------------------------------------------------------------- brand-plan import ---
# A brand plan rarely follows the fill-in-the-blanks template, but it almost always states
# its facts as labelled lines ("Brand: Nuvexa", "Indication — mBC", "Total budget: $2.5M")
# or short bullets. This pass reads those labels off the document so an uploaded plan fills
# the SAME brief slots as if the details had been typed. Each slot maps to an ordered set of
# label synonyms (most specific first); the first labelled line that matches wins, then the
# connective extractor and the whole-document core matchers sweep up anything unlabelled.
_DOC_FIELD_LABELS: list[tuple[str, list[str]]] = [
    ("campaign_name",      ["campaign name", "campaign title", "initiative", "program name", "plan name"]),
    ("brand",              ["brand name", "product name", "brand", "product", "asset"]),
    ("molecule",           ["molecule", "inn", "generic name", "compound", "active ingredient"]),
    ("indication",         ["indication", "disease", "condition", "patient population"]),
    ("therapy_area",       ["therapy area", "therapeutic area", "disease area", "specialty", "ta"]),
    ("audience",           ["target audience", "target customer", "target segment", "hcp segment", "audience", "customer segment", "customer"]),
    ("geography",          ["geography", "geographies", "markets", "market", "region", "countries", "country", "territory"]),
    ("duration",           ["campaign period", "flight dates", "timeline", "timeframe", "time frame", "duration", "flight", "period", "dates"]),
    ("objective",          ["business objective", "objectives", "objective", "goals", "goal", "aim", "purpose", "ambition"]),
    ("kpi",                ["success metrics", "success metric", "measure of success", "kpis", "kpi", "measures", "metric", "metrics"]),
    ("preferred_channels", ["preferred channels", "channel mix", "channels", "tactics", "touchpoints", "media plan", "media"]),
    ("existing_assets",    ["existing assets", "available assets", "content available", "assets"]),
    ("constraints",        ["constraints", "considerations", "limitations", "barriers", "risks"]),
    ("lifecycle",          ["lifecycle stage", "life cycle stage", "lifecycle", "life cycle", "brand stage", "maturity", "stage", "phase"]),
    ("reason",             ["rationale", "background", "situation", "reason", "why now", "context"]),
    ("budget",             ["total budget", "media budget", "budget", "investment", "spend"]),
]


def _find_labeled(text: str, labels: list[str]) -> str:
    """First 'Label: value' (or 'Label - value') line matching any synonym, falling back to
    'Label   value' (a wide gap, no punctuation -- how a two-column PDF table row usually
    serializes) and finally a label alone on its own line with the value on the next
    non-blank line (how a single-cell-per-line PDF table extraction usually serializes).
    Anchored at the line start (after an optional bullet) so a label can't fire inside a
    longer word/phrase."""
    lines = text.splitlines()
    for label in labels:
        esc = re.escape(label)
        same_line_punct = re.compile(rf"(?im)^[ \t\-\*•]*{esc}[ \t]*[:\-–—][ \t]+(.+?)[ \t]*$")
        m = same_line_punct.search(text)
        if m:
            val = _clean_field(m.group(1))
            if val:
                return val

        same_line_gap = re.compile(rf"(?im)^[ \t\-\*•]*{esc}[ \t]{{2,}}(.+?)[ \t]*$")
        m = same_line_gap.search(text)
        if m:
            val = _clean_field(m.group(1))
            if val:
                return val

        label_only = re.compile(rf"(?im)^[ \t\-\*•]*{esc}[ \t]*[:\-–—]?[ \t]*$")
        for i, line in enumerate(lines):
            if label_only.match(line):
                for nxt in lines[i + 1: i + 3]:
                    candidate = nxt.strip()
                    if candidate:
                        val = _clean_field(candidate)
                        if val:
                            return val
                break
    return ""


def _extract_brief_from_text_llm(text: str) -> dict:
    """LLM-first brief extraction from uploaded/pasted strategic material.

    The rules extractor remains below as a fallback and hole-filler, but the primary read
    should be semantic: decks rarely preserve labels cleanly after PDF/DOCX extraction.
    """
    try:
        import conversation_llm
        if not conversation_llm.llm_available():
            return {"fields": {}, "items": []}
        client = conversation_llm._get_client()
        system = """You extract campaign-planning brief fields from pharma strategic-plan text.
Return STRICT JSON only: {"fields": object}. Valid fields are:
campaign_name, brand, molecule, indication, therapy_area, lifecycle_key, audience,
geography, duration, objective, kpi, preferred_channels, existing_assets, constraints,
notes, reason, budget.

Rules:
- Read semantically, not just labels. The text may be copied from slides or a PDF.
- Use only facts present or clearly implied in the text; do not invent.
- lifecycle_key must be one of launch, growth, mature, loe, or omitted.
- budget must be a number in USD if stated, otherwise omit.
- Keep field values concise but specific enough to drive a tactical campaign brief."""
        resp = client.messages.create(
            model=conversation_llm.MODEL,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": text[:24000]}],
        )
        out = next(b.text for b in resp.content if b.type == "text").strip()
        if out.startswith("```"):
            out = out.strip("`")
            out = out[4:] if out.lower().startswith("json") else out
        data = json.loads(out.strip())
        fields = data.get("fields") if isinstance(data, dict) else {}
        if not isinstance(fields, dict):
            return {"fields": {}, "items": []}

        cleaned = {}
        for key in (
            "campaign_name", "brand", "molecule", "indication", "therapy_area", "lifecycle_key",
            "audience", "geography", "duration", "objective", "kpi", "preferred_channels",
            "existing_assets", "constraints", "notes", "reason",
        ):
            val = fields.get(key)
            if isinstance(val, str) and val.strip():
                cleaned[key] = _clean_field(val)
        lc = str(fields.get("lifecycle_key") or "").lower().strip()
        if lc in LIFECYCLE_BY_KEY:
            cleaned["lifecycle_key"] = lc
        budget = fields.get("budget")
        if isinstance(budget, (int, float)) and budget:
            cleaned["budget"] = float(budget)
        elif isinstance(budget, str):
            parsed = _parse_budget(budget)
            if parsed:
                cleaned["budget"] = parsed
        return {"fields": cleaned, "items": []}
    except Exception as exc:  # noqa: BLE001
        print(f"[conversation] LLM brief extraction failed; falling back to rules: {exc}")
        return {"fields": {}, "items": []}


def extract_brief_from_text(text: str) -> dict:
    """Read a brand-plan document and pull the brief slots out of it -- labelled facts first
    (Brand:, Indication:, Budget:, Objective: ...), then the connective/template extractor,
    then the whole-document core matchers as a fallback. Returns the resolved field values
    plus a display list of exactly what was captured, so the UI can show it back to the user."""
    print(f"[brief-extract] input text length={len(text)} chars")
    llm_first = _extract_brief_from_text_llm(text)
    fields: dict = dict(llm_first.get("fields") or {})
    print(f"[brief-extract] llm pass fields={sorted(fields.keys())}")

    # 1) Labelled facts, line by line.
    labeled: dict[str, str] = {}
    for key, labels in _DOC_FIELD_LABELS:
        val = _find_labeled(text, labels)
        if val:
            labeled[key] = val
    print(f"[brief-extract] labelled-regex fields={sorted(labeled.keys())}")

    # 2) Connective / template prose fills anything the labels missed.
    prose: dict = {}
    _extract_brief(text, prose)
    print(f"[brief-extract] prose fields={sorted(prose.keys())}")

    for key in ("campaign_name", "molecule", "indication", "audience", "geography", "duration",
                "objective", "kpi", "preferred_channels", "existing_assets", "constraints",
                "notes", "reason"):
        v = labeled.get(key) or prose.get(key)
        if v and key not in fields:
            fields[key] = v

    # Brand: labelled -> known-brand match -> whole-document scan.
    brand = ""
    if labeled.get("brand"):
        brand = _match_known_brand(labeled["brand"]) or labeled["brand"].split(",")[0].strip()
    if not brand:
        brand = _match_known_brand(text) or ""
    if brand and "brand" not in fields:
        fields["brand"] = brand

    # Therapy area: labelled -> catalog mapping from the brand -> known-therapy scan.
    ta = labeled.get("therapy_area") or ""
    if not ta and brand:
        cat = lookup_brand(brand)
        if cat and cat.get("therapy_area"):
            ta = cat["therapy_area"]
    if not ta:
        ta = _match_known_therapy(text) or ""
    if ta and "therapy_area" not in fields:
        fields["therapy_area"] = ta

    # Lifecycle: keyword-map the labelled stage, else scan the whole document.
    lc = _match_lifecycle(labeled.get("lifecycle", "")) or _match_lifecycle(text) or ""
    if lc and "lifecycle_key" not in fields:
        fields["lifecycle_key"] = lc

    # Budget: labelled amount -> the connective 'budget of ...' clause.
    budget = 0.0
    if labeled.get("budget"):
        budget = _parse_budget(labeled["budget"]) or 0.0
    if not budget:
        budget = prose.get("budget") or 0.0
    if budget and "budget" not in fields:
        fields["budget"] = budget

    # Human-readable display list (non-empty only), in a natural reading order.
    lc_label = LIFECYCLE_BY_KEY.get(fields.get("lifecycle_key", ""), {}).get("label", "")
    _display_order = [
        ("campaign_name", "Campaign"), ("brand", "Brand"), ("molecule", "Molecule"),
        ("indication", "Indication"), ("therapy_area", "Therapy area"), ("lifecycle_key", "Lifecycle"),
        ("audience", "Audience"), ("geography", "Geography"), ("duration", "Duration"),
        ("budget", "Budget"), ("objective", "Objective"), ("kpi", "Target KPI"),
        ("preferred_channels", "Preferred channels"), ("existing_assets", "Existing assets"),
        ("constraints", "Constraints"), ("reason", "Reason"),
    ]
    items = []
    for key, label in _display_order:
        if key not in fields:
            continue
        if key == "budget":
            disp = _human_budget(fields["budget"])
        elif key == "lifecycle_key":
            disp = lc_label or str(fields[key])
        else:
            disp = str(fields[key])
        items.append({"key": key, "label": label, "value": disp})

    return {"fields": fields, "items": items}


def new_state() -> dict:
    return {
        "slots": {
            # Core facts the research run requires.
            "brand": "", "therapy_area": "", "indication": "", "lifecycle_key": "",
            "budget": 0.0, "maturity_notes": "",
            # Richer brief captured from the fill-in-the-blanks intake (all optional -- the
            # agents infer what's missing). Extracted from the pasted paragraph; surfaced in
            # the brief panel and folded into the plan.
            "campaign_name": "", "molecule": "", "audience": "", "geography": "",
            "duration": "", "objective": "", "kpi": "", "existing_assets": "",
            "preferred_channels": "", "constraints": "", "notes": "", "reason": "",
        },
        "budget_asked": False,
        "reason_asked": False,   # whether we've asked the always-on 'why this campaign' follow-up
        "awaiting": None,   # which slot we last asked for
        "phase": "collecting",  # collecting -> ready -> running -> done (-> clarify Q&A while done)
        "ta_from_catalog": False,   # therapy area was auto-mapped from a known brand
        "indication_options": [],   # the brand's indication choices we last offered
        "open_questions": [],   # toolkit 'needs alignment' groups, seeded after each run
        "clarify_idx": 0,
        "clarify_answers": {},
        "clarify_resolved_ids": [],   # group ids ever asked in THIS project -- never reseeded, even
                                       # after a later regeneration whose feasibility scoring still
                                       # can't structurally auto-answer the underlying question
        "awaiting_clarify": None,
        "plan_frozen": False,   # set by 'close updates' -- stops further auto-adjustment of the plan
        "recall_offered": False,   # whether we've already checked/offered remembered brand details
        "recalled_memory": None,   # the remembered slots, held until the recall_confirm reply arrives
    }


def _match_indication(message: str, options: list[str]) -> str | None:
    """Resolve a user's reply to one of the offered indication options -- accepts a
    number ('2'), a verbatim/substring name, or the best keyword-overlap match."""
    if not options:
        return None
    t = message.strip().lower()
    m = re.match(r"^\s*(\d{1,2})\b", t)
    if m:
        idx = int(m.group(1)) - 1
        if 0 <= idx < len(options):
            return options[idx]
    for opt in options:
        key = opt.lower()
        if key in t or (len(t) >= 5 and t in key):
            return opt
    reply_words = set(re.findall(r"[a-z0-9]+", t))
    best, best_score = None, 0
    for opt in options:
        opt_words = set(re.findall(r"[a-z0-9]+", opt.lower())) - {"the", "of", "with", "and", "for"}
        score = len(opt_words & reply_words)
        if score > best_score:
            best, best_score = opt, score
    return best if best_score >= 1 else None


def opening_message(brand: str = "", campaign: str = "") -> str:
    if brand:
        return (
            f"Hi — I'm your campaign planning agent for **{brand}**"
            + (f", campaign **{campaign}**" if campaign else "")
            + ". **Fill in the brief above** (edit the blanks, or paste your own in any wording) and "
            "I'll pull out the details — indication, lifecycle stage, audience, budget and the rest. "
            "I'll infer what I can and ask about anything important that's missing."
        )
    return (
        "Hi — I'm your campaign planning agent. **Fill in the brief above** (edit the "
        "blanks, or paste your own in any wording) and I'll pull out the details — brand, molecule, "
        "indication, lifecycle stage, audience, budget and the rest. Don't worry about filling every "
        "blank; I'll infer what I can and ask about anything important that's missing. Prefer to just "
        "talk? Tell me the **brand**, **indication** and **lifecycle stage** and we'll go from there."
    )


def _extract(message: str, state: dict) -> None:
    """Mutates state['slots'] with anything found in the message, context-aware on state['awaiting']."""
    slots = state["slots"]
    awaiting = state["awaiting"]

    # Pull the whole fill-in-the-blanks brief first; the core matchers below then only fill gaps.
    _extract_brief(message, slots)
    if slots.get("budget") and not state.get("budget_asked"):
        state["budget_asked"] = True   # the brief already gave a budget -- don't re-ask it

    # 'Reason for this campaign' -- the always-on follow-up. Once asked, always record something
    # (a deferral becomes an explicit '(not specified)') so we never loop on it.
    if awaiting == "reason" and not slots.get("reason"):
        low = message.strip().lower().strip(".!?")
        if _is_deferral(message) or low in ("skip", "none", "n/a", "na", "pass", "later", "no reason"):
            slots["reason"] = "(not specified)"
        else:
            slots["reason"] = message.strip()[:600]

    # Lifecycle (distinct keywords, safe to always scan)
    if not slots["lifecycle_key"]:
        lc = _match_lifecycle(message)
        if lc:
            slots["lifecycle_key"] = lc

    # Brand
    if not slots["brand"]:
        kb = _match_known_brand(message)
        if kb:
            slots["brand"] = kb
        else:
            m = re.search(r"(?:brand|drug|molecule|for|planning)\s+([A-Z][A-Za-z0-9\-]{2,})", message)
            if m and m.group(1).lower() not in ("the", "our", "this", "that"):
                slots["brand"] = m.group(1)
            elif awaiting == "brand" and not _is_deferral(message):
                cand = _clean_freetext(message)
                if cand and len(cand.split()) <= 3:
                    slots["brand"] = cand.split(",")[0].strip()

    # Fixed brand -> therapy-area mapping: a known brand leads to exactly one therapy
    # area, so auto-fill it rather than asking (the variable dimension is indication).
    if slots["brand"] and not slots["therapy_area"]:
        cat = lookup_brand(slots["brand"])
        if cat and cat["therapy_area"]:
            slots["therapy_area"] = cat["therapy_area"]
            state["ta_from_catalog"] = True

    # Therapy area (only reached for brands NOT in the catalog)
    if not slots["therapy_area"]:
        kt = _match_known_therapy(message)
        if kt:
            slots["therapy_area"] = kt
        else:
            m = re.search(r"\bin\s+([a-z][a-z\s\-]{4,40})", message.lower())
            if m and awaiting != "brand" and not _is_deferral(message):
                slots["therapy_area"] = m.group(1).strip().strip(".!?,")
            elif awaiting == "therapy_area" and not _is_deferral(message):
                cand = _clean_freetext(message)
                if cand:
                    slots["therapy_area"] = cand

    # Indication (only when we've offered the brand's options and are waiting on a pick)
    if awaiting == "indication" and not slots.get("indication") and not _is_deferral(message):
        picked = _match_indication(message, state.get("indication_options") or [])
        if picked:
            slots["indication"] = picked

    # Budget (only when relevant, to avoid grabbing unrelated numbers). Skipped once a budget
    # is already captured, so scanning a long brief can't overwrite it with a stray number.
    if not slots.get("budget") and (awaiting == "budget" or "$" in message or "budget" in message.lower()):
        b = _parse_budget(message)
        if b is not None:
            slots["budget"] = b
            state["budget_asked"] = True

    # CX-maturity signal (SFMC/tagging/dashboard mentions) -- opportunistic only, never asked for.
    try:
        import pathlib as _pathlib
        import sys as _sys
        _sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parent))
        from bam import has_maturity_signal
        if has_maturity_signal(message):
            existing = slots.get("maturity_notes", "")
            slots["maturity_notes"] = (existing + " " + message).strip()[-2000:]
    except Exception:  # noqa: BLE001 -- purely additive signal, never block the dialog on it
        pass


# Last known state of the LLM path, refreshed on every interpret_message() call so the UI can
# show *why* a given turn was answered by Claude vs. the rules fallback, not just a boot-time flag.
_LAST_STATUS = {"engine": "rules", "ok": None, "detail": "not yet attempted", "ts": None}


def _set_status(engine: str, ok: bool | None, detail: str) -> None:
    global _LAST_STATUS
    _LAST_STATUS = {"engine": engine, "ok": ok, "detail": detail,
                     "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def get_llm_status() -> dict:
    """Snapshot of the last LLM attempt, for surfacing in the UI (pill + log line)."""
    return dict(_LAST_STATUS)


def interpret_message(message: str, state: dict) -> tuple[dict, str, str]:
    """Advance the dialog. Returns (state, agent_reply, action) where action is 'ask' or 'run'.

    If the LLM path (Claude via Microsoft Foundry) is configured, the conversation is driven by
    it; otherwise it uses the deterministic rules below. Any LLM error falls back to the rules
    path so the chat never breaks -- but the failure reason is recorded in get_llm_status() so
    it's visible in the UI instead of silently swallowed.
    """
    # Post-plan clarify phase (toolkit open questions) is deterministic by design --
    # it must record answers verbatim, so it runs before the LLM path.
    if state.get("phase") == "done" and state.get("open_questions") and \
            state.get("clarify_idx", 0) < len(state["open_questions"]):
        return _interpret_clarify(message, state)

    # Once the plan exists (and there's no active clarify turn to answer), handle a couple of
    # fixed control phrases before falling through to the LLM/rules dialog below -- which
    # assumes slots are still being collected. 'regenerate' used to fall through to the rules
    # path's final 'all slots filled -> kick off a run' branch and silently rerun the full
    # agent pipeline, reseeding the clarify Q&A with the same still-unresolved questions (the
    # feasibility checklist can't always structurally parse a free-text answer). That's no
    # longer needed: every clarify answer is folded into the plan the moment it's given.
    if state.get("phase") == "done":
        low = message.strip().lower().strip(".!?")
        if any(p in low for p in _CLOSE_UPDATES_PHRASES):
            return state, ("Locking the plan in — no further automatic updates from here. "
                           "You can still ask me questions about it any time."), "freeze"
        if "regenerate" in low:
            return state, ("Already up to date — every answer you've given me is already folded into "
                           "the plan on the right. Say **close updates** to lock it in, or tell me what "
                           "you'd like to change and I'll factor it in."), "ask"

    # The always-on 'reason for this campaign' answer is captured deterministically for both
    # engines (the rules path records it and then proceeds straight to the run).
    if state.get("awaiting") == "reason":
        return _interpret_message_rules(message, state)

    # Pull the fill-in-the-blanks brief up front so the richer fields (audience, geography,
    # objective, channels, ...) are captured regardless of which engine drives the turn --
    # the LLM path only tracks the four core slots. Fills empty slots only.
    if state.get("phase") in (None, "collecting"):
        _extract_brief(message, state["slots"])

    # For a brand in the fixed catalog, the collecting dialog is handled deterministically
    # (rules path) rather than by the LLM: this guarantees the brand's fixed therapy area
    # is auto-mapped and its real indications are offered as explicit choices, instead of
    # therapy area being asked as an open free-text question. Unknown brands still use the
    # LLM path below.
    if state.get("phase") in (None, "collecting"):
        known = state["slots"].get("brand") or _match_known_brand(message)
        if known and lookup_brand(known):
            return _interpret_message_rules(message, state)

    try:
        import pathlib as _pathlib
        import sys as _sys
        _sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parent))
        from conversation_llm import llm_available, interpret_message_llm, active_provider
        if llm_available():
            provider = active_provider()
            provider_label = {"gemini": "Gemini", "azure-foundry": "Claude (via Microsoft Foundry)"}.get(provider, provider)
            try:
                state, reply, action = interpret_message_llm(message, state)
                _set_status(provider, True, f"{provider_label} answered this turn.")
                print(f"[conversation] {provider_label} answered this turn.")
                return _reason_gate(state, reply, action)  # ask 'why this campaign' before any run
            except Exception as e:  # noqa: BLE001 -- fall back to rules on any LLM/auth failure
                # splitlines() is empty for an exception with a blank message, so fall back to
                # the class name rather than IndexError-ing inside the error handler itself.
                short = (str(e).strip().splitlines() or [type(e).__name__])[0][:200]
                detail = f"{provider_label} call failed ({short}); used the rule-based fallback for this turn."
                print(f"[conversation] {provider_label} call failed, using rules ({e})")
                _set_status("rules", False, detail)
                return _interpret_message_rules(message, state)
        else:
            _set_status("rules", None, "LLM not configured (SDK or azure-identity not importable) -- using rule-based dialog.")
    except Exception as e:  # noqa: BLE001 -- fall back to rules on any LLM failure
        detail = f"LLM path unavailable ({e}); using rule-based fallback."
        print(f"[conversation] {detail}")
        _set_status("rules", False, detail)
    return _interpret_message_rules(message, state)


def llm_enabled() -> bool:
    """True when the LLM path is configured (SDK + azure-identity importable, endpoint set)."""
    try:
        import pathlib as _pathlib
        import sys as _sys
        _sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parent))
        from conversation_llm import llm_available
        return llm_available()
    except Exception:  # noqa: BLE001
        return False


def clarify_payload(state: dict) -> dict | None:
    """Structured progress for the clarify group currently being asked, so the UI can
    render it as a question card with a progress bar (Section X of N · Questions a-b of T).
    None when the clarify phase isn't active or is finished. (Gated on open_questions
    being populated -- which only happens post-run -- rather than on phase, so the first
    group's payload is available in the run-stream 'done' branch before phase flips.)"""
    groups = state.get("open_questions") or []
    idx = state.get("clarify_idx", 0)
    if not groups or idx >= len(groups):
        return None
    q_total = sum(len(g["questions"]) for g in groups)
    q_before = sum(len(g["questions"]) for g in groups[:idx])
    g = groups[idx]
    return {
        "group_index": idx + 1,
        "group_total": len(groups),
        "title": g["title"],
        "source": g["source"],
        "questions": g["questions"],
        "q_start": q_before + 1,
        "q_end": q_before + len(g["questions"]),
        "q_total": q_total,
        "answered_before": q_before,
    }


def ask_clarify_group(state: dict) -> str | None:
    """The chat message asking the current open-question group (or None when done).
    Called by the server right after a run finishes, and by the clarify handler to
    advance to the next group."""
    groups = state.get("open_questions") or []
    idx = state.get("clarify_idx", 0)
    if idx >= len(groups):
        return None
    g = groups[idx]
    qs = "\n".join(f"• {q}" for q in g["questions"])
    state["awaiting_clarify"] = g["id"]
    return (
        f"To sharpen the plan, I have a few things only your brand team can answer "
        f"({idx + 1} of {len(groups)}) — **{g['title']}** *(from the {g['source']})*:\n{qs}\n\n"
        "Answer in a sentence or two — or say *skip* to move on, or *skip all* to leave "
        "the rest flagged in the plan."
    )


_SKIP_ALL = ["skip all", "stop asking", "leave them", "skip the rest", "no more questions", "that's all", "thats all"]
_CLOSE_UPDATES_PHRASES = ["close updates", "close the updates", "lock the plan", "lock it in", "finalize the plan",
                          "finalise the plan", "freeze the plan", "stop updating"]


def _mark_resolved(state: dict, *group_ids: str) -> None:
    resolved = set(state.get("clarify_resolved_ids") or [])
    resolved.update(group_ids)
    state["clarify_resolved_ids"] = sorted(resolved)


def _interpret_clarify(message: str, state: dict) -> tuple[dict, str, str]:
    """Post-plan phase: record the user's answers to the toolkit's open-question groups
    verbatim (they also feed feasibility auto-answers via maturity_notes), then signal the
    server to fold each answer into the plan immediately -- action='update_plan' on every
    turn here, not just at the end, so the plan updates section-by-section as the user
    answers rather than waiting for a manual 'regenerate'. Every group answered (or skipped)
    is recorded in clarify_resolved_ids so it is never asked again for this project, even if
    a later full regeneration still can't structurally auto-answer the underlying checklist
    item from free text."""
    groups = state["open_questions"]
    idx = state.get("clarify_idx", 0)
    low = message.strip().lower().strip(".!?")

    if any(s in low for s in _SKIP_ALL):
        _mark_resolved(state, *(g["id"] for g in groups[idx:]))
        state["clarify_idx"] = len(groups)
        state["awaiting_clarify"] = None
        return state, ("No problem — the remaining items stay highlighted as **Needs alignment** in the plan, "
                       "and I won't ask about them again. Say **close updates** any time to lock the plan in."), "update_plan"

    if low in ("skip", "pass", "next", "later"):
        state["clarify_answers"] = state.get("clarify_answers", {})
        state["clarify_answers"][groups[idx]["id"]] = "(skipped)"
    else:
        state["clarify_answers"] = state.get("clarify_answers", {})
        state["clarify_answers"][groups[idx]["id"]] = message.strip()
        # Feed the raw answer into the same signal stream feasibility.py auto-answers from,
        # and opportunistically pick up budget/lifecycle corrections mentioned in passing.
        slots = state["slots"]
        slots["maturity_notes"] = ((slots.get("maturity_notes", "") + " " + message).strip())[-2000:]
        _extract(message, state)

    _mark_resolved(state, groups[idx]["id"])
    state["clarify_idx"] = idx + 1
    nxt = ask_clarify_group(state)
    if nxt:
        return state, "Captured — folding that into the plan now. " + nxt, "update_plan"

    state["awaiting_clarify"] = None
    answered = sum(1 for v in state.get("clarify_answers", {}).values() if v != "(skipped)")
    return state, (
        f"That's everything — **{answered}** of {len(groups)} open-question groups answered, and I've "
        "folded each one into the plan as you went. It's fully up to date on the right. Keep chatting "
        "any time to refine it further, or say **close updates** to lock it in."
    ), "update_plan"


_REUSE_PHRASES = ["same", "no change", "unchanged", "reuse", "keep it", "keep the same", "as before", "identical", "still the same", "still holds"]
_CHANGE_NEGATIONS = ["not the same", "isn't the same", "is not the same", "no longer", "something's different", "something is different", "different this time"]


def _human_budget(amount: float) -> str:
    if not amount:
        return "not set"
    if amount >= 1_000_000:
        return f"${amount / 1_000_000:.1f}M".replace(".0M", "M")
    if amount >= 1_000:
        return f"${amount / 1_000:.0f}K"
    return f"${amount:,.0f}"


def _human_date(iso_ts: str) -> str:
    try:
        return time.strftime("%b %d, %Y", time.strptime(iso_ts, "%Y-%m-%dT%H:%M:%SZ"))
    except Exception:  # noqa: BLE001
        return "previously"


def _recall_prompt(brand: str, remembered: dict) -> str:
    lc = remembered.get("lifecycle_key")
    lc_label = LIFECYCLE_BY_KEY.get(lc, {}).get("label", lc) if lc else None
    lines = []
    if remembered.get("indication"):
        lines.append(f"  • Indication: **{remembered['indication']}**")
    if lc_label:
        lines.append(f"  • Lifecycle: **{lc_label}**")
    if remembered.get("budget"):
        lines.append(f"  • Budget: **{_human_budget(remembered['budget'])}**")
    if remembered.get("maturity_notes"):
        lines.append(f"  • Notes: {remembered['maturity_notes'][-160:]}")
    details = "\n".join(lines) if lines else "  • (a few details, no major ones missing)"
    return (
        f"I've planned for **{brand}** before ({_human_date(remembered.get('updated_at', ''))}). Here's what you told me last time:\n"
        f"{details}\n\n"
        "Should I use the **same details** again, or is something **different** this time? Reply *same* to reuse "
        "everything, or just tell me what's changed (e.g. \"budget is now $3M\" or \"it's mature now, not growing\")."
    )


def _resolve_recall_reply(message: str, state: dict) -> None:
    """Merge the remembered brand details into slots, honoring any override mentioned
    in this reply (e.g. 'same but budget is $5M'); called once, right after the user
    answers the recall-confirm prompt."""
    remembered = state.pop("recalled_memory", None) or {}
    slots = state["slots"]
    low = message.strip().lower().strip(".!?")
    reuse_all = any(p in low for p in _REUSE_PHRASES) and not any(p in low for p in _CHANGE_NEGATIONS)

    if remembered.get("indication") and not slots.get("indication"):
        cat = lookup_brand(slots.get("brand", ""))
        opts = (cat or {}).get("indications") or []
        overridden = None if reuse_all else _match_indication(message, opts)
        slots["indication"] = overridden or remembered["indication"]

    if remembered.get("lifecycle_key") and not slots.get("lifecycle_key"):
        overridden = None if reuse_all else _match_lifecycle(message)
        slots["lifecycle_key"] = overridden or remembered["lifecycle_key"]

    if remembered.get("budget") and not state.get("budget_asked"):
        overridden = None if reuse_all else (_parse_budget(message) if ("$" in message or "budget" in low) else None)
        slots["budget"] = overridden if overridden is not None else remembered["budget"]
        state["budget_asked"] = True

    if remembered.get("maturity_notes") and not slots.get("maturity_notes"):
        slots["maturity_notes"] = remembered["maturity_notes"]


def _reason_prompt(slots: dict) -> str:
    brand = slots.get("brand") or "this brand"
    return (
        f"Last thing before I bring in the agents — **what's prompting this campaign for "
        f"{brand}** right now? For example: a new launch or indication, defending share against "
        "a competitor, an upcoming data readout, slowing uptake, or a patient-access push. This "
        "anchors the whole strategy (and helps me read anything ambiguous in your notes). One "
        "line is plenty — or say *skip*."
    )


def _reason_gate(state: dict, reply: str, action: str) -> tuple[dict, str, str]:
    """Before any run kicks off, ensure we've asked the always-on 'why this campaign now'
    follow-up. Applied to both the rules and LLM engines so the behaviour is identical."""
    slots = state["slots"]
    if action == "run" and not slots.get("reason") and not state.get("reason_asked"):
        state["reason_asked"] = True
        state["awaiting"] = "reason"
        state["phase"] = "collecting"
        return state, _reason_prompt(slots), "ask"
    return state, reply, action


def _interpret_message_rules(message: str, state: dict) -> tuple[dict, str, str]:
    """Deterministic slot-filling dialog (no LLM). Used as the default and as the LLM fallback."""
    _extract(message, state)
    slots = state["slots"]
    deferred = _is_deferral(message)

    if state.get("awaiting") == "recall_confirm":
        state["awaiting"] = None
        _resolve_recall_reply(message, state)

    if not slots["brand"]:
        state["awaiting"] = "brand"
        if deferred:
            return state, ("That's your real product to name — I can't invent it. Which **brand or molecule** is "
                           "this campaign for? (e.g. the drug you're working on.)"), "ask"
        return state, "Which **brand or molecule** are we planning for?", "ask"

    # First time this conversation sees a resolved brand -- check whether we've planned
    # for it before and offer to reuse those captured details instead of re-asking them.
    if slots["brand"] and not state.get("recall_offered"):
        state["recall_offered"] = True
        remembered = get_brand_memory(slots["brand"])
        if remembered:
            state["recalled_memory"] = remembered
            state["awaiting"] = "recall_confirm"
            return state, _recall_prompt(slots["brand"], remembered), "ask"

    if not slots["therapy_area"]:
        state["awaiting"] = "therapy_area"
        if deferred:
            return state, (f"I need the actual indication for **{slots['brand']}** — that's a real clinical fact, not "
                           "something to guess. Which **therapy area / indication** is this campaign for?"), "ask"
        return state, f"Got it — **{slots['brand']}**. And which **therapy area / indication** is this campaign for?", "ask"

    # Known brand -> offer its indications as choices (never an open question).
    cat = lookup_brand(slots["brand"])
    # If the brief already named an indication, snap it to the closest catalog label so the
    # content library and plan tailoring match (e.g. "HR+/HER2- breast cancer" -> the roster's
    # canonical label). Leaves it untouched if nothing is close.
    if cat and cat["indications"] and slots.get("indication"):
        picked = _match_indication(slots["indication"], cat["indications"])
        if picked:
            slots["indication"] = picked
    if cat and cat["indications"] and not slots.get("indication"):
        inds = cat["indications"]
        if len(inds) == 1:
            slots["indication"] = inds[0]  # single approved use -- nothing to choose
        elif deferred:
            slots["indication"] = inds[0]  # default to the lead indication, flagged in the brief
        else:
            state["awaiting"] = "indication"
            state["indication_options"] = inds
            opts = "\n".join(f"  {i + 1}. {ind}" for i, ind in enumerate(inds))
            ta_note = (f"maps to **{slots['therapy_area']}**" if state.get("ta_from_catalog")
                       else f"is a **{slots['therapy_area']}** brand")
            return state, (
                f"**{slots['brand']}** {ta_note}. Which **indication** are you building this campaign for?\n{opts}\n\n"
                "Reply with a number or the indication name — I'll tailor the whole plan to it."
            ), "ask"

    if not slots["lifecycle_key"]:
        state["awaiting"] = "lifecycle_key"
        return state, (
            f"Thanks. Where is **{slots['brand']}** in its **lifecycle**? Just tell me one of: "
            "*launching*, *growing*, *mature*, or *facing loss of exclusivity*."
        ), "ask"

    if not state["budget_asked"]:
        state["awaiting"] = "budget"
        state["budget_asked"] = True
        return state, (
            "Last thing (optional): do you have a rough **total campaign budget** in mind? "
            "Give me a number (e.g. \"$2M\"), or say *skip* and I'll show the channel split as percentages."
        ), "ask"

    # All required slots captured -> kick off the run (after the reason gate below).
    state["awaiting"] = None
    state["phase"] = "running"
    # The brief itself is already visible above (import card / editable fields) -- don't echo
    # it back a second time, just confirm and kick off the run.
    reply = (
        "Perfect — brief locked in. I'm putting my agent to work now — watch it think through "
        "the market, competitors, positioning, channel mix and measurement on the right. This "
        "takes ~30–60 seconds while it pulls live data…"
    )
    return _reason_gate(state, reply, "run")
