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
    if any(w in t for w in ["skip", "no budget", "not sure", "none", "later", "don't have", "dont have", "n/a", "na"]):
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


def new_state() -> dict:
    return {
        "slots": {"brand": "", "therapy_area": "", "indication": "", "lifecycle_key": "", "budget": 0.0, "maturity_notes": ""},
        "budget_asked": False,
        "awaiting": None,   # which slot we last asked for
        "phase": "collecting",  # collecting -> ready -> running -> done (-> clarify Q&A while done)
        "ta_from_catalog": False,   # therapy area was auto-mapped from a known brand
        "indication_options": [],   # the brand's indication choices we last offered
        "open_questions": [],   # toolkit 'needs alignment' groups, seeded after each run
        "clarify_idx": 0,
        "clarify_answers": {},
        "awaiting_clarify": None,
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


def opening_message() -> str:
    return (
        "Hi — I'm your campaign-planning agent. Tell me what you're working on: which **brand** "
        "are you planning a campaign for, what **therapy area / indication**, and roughly where the "
        "brand sits in its **lifecycle** (just launching, growing, mature, or facing loss of "
        "exclusivity)? A sentence is plenty — I'll take it from there and start the research."
    )


def _extract(message: str, state: dict) -> None:
    """Mutates state['slots'] with anything found in the message, context-aware on state['awaiting']."""
    slots = state["slots"]
    awaiting = state["awaiting"]

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

    # Budget (only when relevant, to avoid grabbing unrelated numbers)
    if awaiting == "budget" or "$" in message or "budget" in message.lower():
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
        from conversation_llm import llm_available, interpret_message_llm
        if llm_available():
            try:
                result = interpret_message_llm(message, state)
                _set_status("azure-foundry", True, "Claude (via Microsoft Foundry) answered this turn.")
                return result
            except Exception as e:  # noqa: BLE001 -- fall back to rules on any LLM/auth failure
                short = str(e).strip().splitlines()[0][:200]
                detail = f"Claude call failed ({short}); used the rule-based fallback for this turn."
                print(f"[conversation] Claude call failed, using rules ({e})")
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


def _interpret_clarify(message: str, state: dict) -> tuple[dict, str, str]:
    """Post-plan phase: record the user's answers to the toolkit's open-question groups
    verbatim (they also feed feasibility auto-answers on regeneration via maturity_notes),
    then offer to send the agents back in."""
    groups = state["open_questions"]
    idx = state.get("clarify_idx", 0)
    low = message.strip().lower().strip(".!?")

    if any(s in low for s in _SKIP_ALL):
        state["clarify_idx"] = len(groups)
        state["awaiting_clarify"] = None
        return state, ("No problem — the remaining items stay highlighted as **Needs alignment** in the plan. "
                       "Say *regenerate* any time to send the agents back in with what you've told me."), "ask"

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

    state["clarify_idx"] = idx + 1
    nxt = ask_clarify_group(state)
    if nxt:
        return state, "Captured — that goes into the plan. " + nxt, "ask"

    state["awaiting_clarify"] = None
    answered = sum(1 for v in state.get("clarify_answers", {}).values() if v != "(skipped)")
    return state, (
        f"That's everything — **{answered}** of {len(groups)} open-question groups answered. "
        "Say **regenerate** and I'll send the agents back in to fold your answers into the plan "
        "(the feasibility checklist and open-question flags will update)."
    ), "ask"


def _interpret_message_rules(message: str, state: dict) -> tuple[dict, str, str]:
    """Deterministic slot-filling dialog (no LLM). Used as the default and as the LLM fallback."""
    _extract(message, state)
    slots = state["slots"]
    deferred = _is_deferral(message)

    if not slots["brand"]:
        state["awaiting"] = "brand"
        if deferred:
            return state, ("That's your real product to name — I can't invent it. Which **brand or molecule** is "
                           "this campaign for? (e.g. the drug you're working on.)"), "ask"
        return state, "Which **brand or molecule** are we planning for?", "ask"

    if not slots["therapy_area"]:
        state["awaiting"] = "therapy_area"
        if deferred:
            return state, (f"I need the actual indication for **{slots['brand']}** — that's a real clinical fact, not "
                           "something to guess. Which **therapy area / indication** is this campaign for?"), "ask"
        return state, f"Got it — **{slots['brand']}**. And which **therapy area / indication** is this campaign for?", "ask"

    # Known brand -> offer its indications as choices (never an open question).
    cat = lookup_brand(slots["brand"])
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

    # All required slots captured -> kick off the run
    state["awaiting"] = None
    state["phase"] = "running"
    budget_line = f"\n• Budget: ${int(slots['budget']):,}" if slots["budget"] else "\n• Budget: (percentages only)"
    indication_line = f"\n• Indication: **{slots['indication']}**" if slots.get("indication") else ""
    reply = (
        "Perfect — here's the brief I've locked in:\n"
        f"• Brand: **{slots['brand']}**\n"
        f"• Therapy area: **{slots['therapy_area']}**"
        f"{indication_line}\n"
        f"• Lifecycle: **{slots['lifecycle_key']}**"
        f"{budget_line}\n\n"
        "I'm putting my research agents to work now — watch them think through the market, competitors, "
        "positioning, channel mix and measurement on the right. This takes ~30–60 seconds while they pull live data…"
    )
    return state, reply, "run"
