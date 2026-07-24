"""Presentational brief summariser.

Condenses a captured brief field to an ultra-short, strategic, keyword-driven
gist (a hard ≤MAX_WORDS words) for *display* — the BriefCard artifact and studio
ask labels — so the UI stops echoing whole paragraphs from the uploaded deck. It
never mutates the stored full text: grounding, decision records and the plan body
still read the originals, and the UI keeps the full value behind "See more".

LLM-first (keyword compression via llm_decisioning) with an in-memory cache so a
given field text is only ever summarised once; a deterministic clip is the
fallback when Foundry is unavailable, so the app still shortens without an LLM.
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Hard ceiling for a display summary. This is a guardrail, not a target: nothing
# rendered into a brief row may exceed it, so the LLM path verifies its own output
# against it and repairs violations before the deterministic clip is ever reached.
MAX_WORDS = 15

# Strip a leading "Two-part strategic focus:", "Objective:", "Goal —", etc.
_LEADIN = re.compile(
    r"^(?:two[- ]part\s+)?(?:overall\s+|primary\s+|key\s+)?"
    r"(?:strategic\s+)?(?:focus|goal|objective|aim|approach|priority|priorities)\s*[:\-–]\s*",
    re.I,
)
# Inline ALL-CAPS section tags like "IDENTIFY: " / "ESTABLISH – " used in decks.
# Requires a ≥4-letter caps word AND a header-style separator (colon, or a
# space-padded dash) so compound terms like "NCI-designated" or trial names like
# "CLARITY-01" — caps glued to a word by a bare hyphen — are left intact.
_CAPS_TAG = re.compile(r"\b[A-Z]{4,}(?:\s*:\s+|\s+[–—-]\s+)")
_PARENS = re.compile(r"\s*\([^)]*\)")  # drop parenthetical asides for brevity
_DANGLING = re.compile(
    r"\s+(?:and|or|but|so|with|to|of|for|the|a|an|that|which|as|via|by|in|on|at|vs)$",
    re.I,
)
_TRAIL_PUNCT = re.compile(r"[\s,;:–\-/]+$")

# Long, free-text brief fields worth summarising (short factual slots are left alone).
LONG_KEYS = (
    "audience", "objective", "kpi", "preferred_channels",
    "existing_assets", "constraints", "reason",
)

_LLM_CACHE: dict[str, str] = {}


def _key(text: str, max_words: int) -> str:
    return hashlib.sha1(f"{max_words}|{text}".encode("utf-8")).hexdigest()


def summarize_value(text: str, max_words: int = MAX_WORDS) -> str:
    """Deterministic ≤max_words gist. Empty/short/"(not specified)" pass through."""
    s = " ".join(str(text or "").split())
    if not s or s == "(not specified)":
        return s
    s = _LEADIN.sub("", s)
    s = _CAPS_TAG.sub("", s)
    s = _PARENS.sub("", s)
    s = " ".join(s.split())
    words = s.split()
    if len(words) <= max_words:
        return s
    clipped = _TRAIL_PUNCT.sub("", " ".join(words[:max_words]))
    clipped = _DANGLING.sub("", clipped)
    return clipped.rstrip() + "…"


def _llm_summaries(fields: dict[str, str], max_words: int) -> dict[str, str]:
    """Keyword-compress each field via the LLM, memoised per field text."""
    result: dict[str, str] = {}
    missing: dict[str, str] = {}
    for key, text in fields.items():
        ck = _key(text, max_words)
        if ck in _LLM_CACHE:
            result[key] = _LLM_CACHE[ck]
        else:
            missing[key] = text
    if missing:
        got: dict[str, str] = {}
        try:
            import llm_decisioning  # lazy: avoids an import cycle (llm_decisioning imports us)
            # The batch call occasionally omits keys; retry the stragglers so every field
            # gets a keyword summary rather than silently falling back to a clip.
            pending = dict(missing)
            for _ in range(3):
                if not pending:
                    break
                res = llm_decisioning.summarize_brief_fields(pending, max_words) or {}
                got.update(res)
                pending = {k: v for k, v in pending.items() if k not in res}
        except Exception:  # noqa: BLE001 — never let summarisation break a response
            got = {}
        for key, text in missing.items():
            short = got.get(key)
            if isinstance(short, str) and short.strip():
                short = " ".join(short.split())
                # summarize_brief_fields already rejects and re-asks for over-length replies,
                # so this is the last line of defence rather than the usual path: clamp anything
                # that survived both LLM attempts so the ceiling holds unconditionally.
                if len(short.split()) > max_words:
                    short = summarize_value(short, max_words)
                _LLM_CACHE[_key(text, max_words)] = short
                result[key] = short
    return result


def summarize_slots(slots: dict, max_words: int = MAX_WORDS) -> dict:
    """Map of {field: short summary} for the long brief fields that actually shortened."""
    long_fields = {
        key: slots[key].strip()
        for key in LONG_KEYS
        if isinstance(slots.get(key), str) and slots[key].strip() and slots[key].strip() != "(not specified)"
    }
    if not long_fields:
        return {}
    llm = _llm_summaries(long_fields, max_words)
    out: dict[str, str] = {}
    for key, full in long_fields.items():
        short = llm.get(key) or summarize_value(full, max_words)
        if short and short != full:
            out[key] = short
    return out


def attach(slots: dict) -> None:
    """Attach `slots['brief_summary']` in place for any slots dict a response returns."""
    if not isinstance(slots, dict):
        return
    try:
        summary = summarize_slots(slots)
        if summary:
            slots["brief_summary"] = summary
    except Exception:  # noqa: BLE001 — display nicety must never break the caller
        pass
