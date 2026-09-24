"""Persona review engine -- runs a generated Brand Engagement Plan past a synthetic persona
and returns honest, in-character feedback on whether they'd engage and what's missing.

The review is deterministic and grounded in the plan itself, so it works offline and every
critique is defensible:

  * Channel fit -- the plan allocates budget across six channel buckets (rules.CHANNEL_TOUCHPOINTS:
    Reach / Owned digital / Events / Field / Peer / Patient-adjacent). Each persona's preferred /
    tolerated / avoided channels are mapped to those same buckets, giving a per-bucket affinity.
    Weighting the plan's % allocation by that affinity yields an engagement-likelihood score.
  * Message fit -- the plan's key messages are checked against the persona's decision drivers.
  * The gaps/asks are drawn from where the plan over-invests in a channel the persona avoids,
    under-invests in one they rely on, or fails to speak to what drives their decisions.

When the LLM is configured it adds a short in-character narrative on top; the structured
verdict never depends on it.
"""
from __future__ import annotations

import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

BUCKETS = ["Reach", "Owned digital", "Events", "Field", "Peer", "Patient-adjacent"]

# Ordered (substring -> bucket); first match wins, so specific phrases precede generic ones.
_CHANNEL_RULES = [
    ("point-of-care", "Patient-adjacent"), ("point of care", "Patient-adjacent"), ("ehr", "Patient-adjacent"),
    ("patient support", "Patient-adjacent"), ("patient-support", "Patient-adjacent"),
    ("nurse educator", "Patient-adjacent"), ("call-center", "Patient-adjacent"), ("call center", "Patient-adjacent"),
    ("pharmacy", "Patient-adjacent"), ("sms", "Patient-adjacent"), ("reminder", "Patient-adjacent"),
    ("copay", "Patient-adjacent"), ("support program", "Patient-adjacent"), ("onboarding", "Patient-adjacent"),
    ("msl", "Field"), ("medical affairs", "Field"), ("scientific exchange", "Field"),
    ("speaker", "Peer"), ("peer-to-peer", "Peer"), ("peer digital", "Peer"), ("peer communit", "Peer"),
    ("peer /", "Peer"), ("advisory", "Peer"), ("kol", "Peer"), ("dol", "Peer"),
    ("congress", "Events"), ("symposi", "Events"), ("webinar", "Events"), ("webcast", "Events"),
    ("virtual event", "Events"), ("conference", "Events"), ("scientific meeting", "Events"),
    ("in-person rep", "Field"), ("rep detail", "Field"), ("detailing", "Field"), ("rep or virtual", "Field"),
    ("brief rep", "Field"), ("sample", "Field"), ("leave-behind", "Field"), ("leave behind", "Field"),
    ("direct mail", "Field"), ("print", "Field"), ("phone", "Field"), ("virtual detail", "Field"),
    ("live virtual", "Field"), ("e-detail", "Field"), ("clm", "Field"), ("in person", "Field"), ("in-person", "Field"),
    ("programmatic", "Reach"), ("paid search", "Reach"), ("search", "Reach"), ("display", "Reach"),
    ("banner", "Reach"), ("paid social", "Reach"), ("press", "Reach"),
    ("social communit", "Patient-adjacent"), ("communit", "Peer"), ("social", "Reach"),
    ("guideline", "Peer"), ("society", "Peer"),
    ("permissioned email", "Owned digital"), ("email", "Owned digital"), ("newsletter", "Owned digital"),
    ("nurture", "Owned digital"), ("portal", "Owned digital"), ("website", "Owned digital"), ("web", "Owned digital"),
    ("mobile web", "Owned digital"), ("app", "Owned digital"), ("video", "Owned digital"),
]


def _bucket_for(phrase: str) -> str | None:
    t = (phrase or "").lower()
    for sub, bucket in _CHANNEL_RULES:
        if sub in t:
            return bucket
    return None


def bucket_affinity(persona: dict) -> dict:
    """Per-bucket affinity in [-1, 1] derived from the persona's channel preferences."""
    aff = {b: 0.0 for b in BUCKETS}
    ch = persona.get("channels", {}) or {}
    for phrase in ch.get("preferred", []):
        b = _bucket_for(phrase)
        if b:
            aff[b] += 1.0
    for phrase in ch.get("tolerated", []):
        b = _bucket_for(phrase)
        if b:
            aff[b] += 0.3
    for phrase in ch.get("avoided", []):
        b = _bucket_for(phrase)
        if b:
            aff[b] -= 1.0
    return {b: max(-1.0, min(1.0, v)) for b, v in aff.items()}


def suggest_rebalance(personas: list[dict], current_mix: dict, alpha: float = 0.4) -> dict:
    """Nudge the channel mix toward what the given personas actually respond to, for the
    'apply feedback to plan' action. Blends the current allocation with an affinity-weighted
    target -- alpha caps how far it moves in one step (0.4 = a real but bounded nudge, not a
    rebuild), then renormalizes to 100%. Deterministic and explainable: every change names the
    persona(s) whose preference drove it.
    """
    if not personas:
        return {"new_mix": dict(current_mix), "changes": []}
    avg_aff = {b: sum(bucket_affinity(p)[b] for p in personas) / len(personas) for b in BUCKETS}
    # Map affinity [-1,1] -> non-negative desirability [0,2] so it can drive a normalized target share.
    desirability = {b: max(0.0, avg_aff[b] + 1.0) for b in BUCKETS}
    total_des = sum(desirability.values()) or 1.0
    target = {b: 100.0 * desirability[b] / total_des for b in BUCKETS}
    blended = {b: (1 - alpha) * current_mix.get(b, 0.0) + alpha * target[b] for b in BUCKETS}
    total_blend = sum(blended.values()) or 1.0
    scaled = {b: blended[b] * 100.0 / total_blend for b in BUCKETS}
    rounded = {b: int(round(v)) for b, v in scaled.items()}
    diff = 100 - sum(rounded.values())
    if diff:
        top = max(rounded, key=lambda b: rounded[b])
        rounded[top] += diff

    changes = []
    for b in BUCKETS:
        delta = rounded[b] - int(round(current_mix.get(b, 0.0)))
        if abs(delta) >= 1:
            if delta > 0:
                names = [p["name"] for p in personas if bucket_affinity(p)[b] >= 0.5]
            else:
                names = [p["name"] for p in personas if bucket_affinity(p)[b] <= -0.5]
            who = f" (per {', '.join(names[:2])})" if names else ""
            direction = "Increase" if delta > 0 else "Reduce"
            changes.append({
                "bucket": b, "from_pct": int(round(current_mix.get(b, 0.0))), "to_pct": rounded[b],
                "delta": delta,
                "note": f"{direction} {b} {abs(delta)} pt{'s' if abs(delta) != 1 else ''}{who}",
            })
    changes.sort(key=lambda c: -abs(c["delta"]))
    return {"new_mix": rounded, "changes": changes}


def _plan_mix(result: dict) -> dict:
    """Plan channel allocation as {bucket: pct}. Allocation keys are already the six buckets;
    anything unexpected is re-bucketed defensively."""
    alloc = (result.get("stage_5_budget") or {}).get("allocation") or {}
    mix = {b: 0.0 for b in BUCKETS}
    for k, v in alloc.items():
        pct = v.get("pct") if isinstance(v, dict) else v
        try:
            pct = float(pct or 0)
        except (TypeError, ValueError):
            continue
        bucket = k if k in BUCKETS else _bucket_for(k)
        if bucket:
            mix[bucket] += pct
    return mix


def _plan_message_text(result: dict) -> str:
    mf = result.get("stage_2_4_message_flow") or {}
    parts = []
    for km in mf.get("key_messages", []):
        parts.append(km.get("topic", ""))
        parts += km.get("supporting_messages", []) or []
    strat = result.get("stage_2_4_strategy") or {}
    ma = strat.get("messaging_architecture") or {}
    for v in ma.values():
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, list):
            parts += [str(x) for x in v]
    return " ".join(parts).lower()


_STOP = {"the", "a", "an", "of", "and", "or", "to", "in", "for", "with", "vs", "vs.", "your", "my",
         "real", "world", "over", "use", "ease", "her", "his", "their", "on", "by", "at"}


def _keywords(phrases: list[str]) -> list[str]:
    words = set()
    for p in phrases:
        for w in re.findall(r"[a-z0-9\-]{4,}", (p or "").lower()):
            if w not in _STOP:
                words.add(w)
    return list(words)


def _sentiment(score: int) -> str:
    if score >= 72:
        return "enthusiastic"
    if score >= 55:
        return "interested"
    if score >= 38:
        return "skeptical"
    return "resistant"


def _pct(mix: dict, bucket: str) -> int:
    return int(round(mix.get(bucket, 0)))


def review(persona: dict, result: dict, use_llm: bool = True) -> dict:
    """Score a plan for one persona and return structured, voiced feedback."""
    aff = bucket_affinity(persona)
    mix = _plan_mix(result)
    ch = persona.get("channels", {}) or {}

    # Engagement likelihood: % allocation weighted by bucket affinity, mapped to 0-100.
    signed = sum(mix[b] * aff[b] for b in BUCKETS)          # [-100, 100]
    score = 50 + 0.45 * signed

    resonates, gaps = [], []

    # Channels the persona relies on but the plan barely funds.
    for b in BUCKETS:
        if aff[b] >= 0.7 and mix[b] < 8:
            score -= 7
            pref = _example(ch.get("preferred", []), b) or b.lower()
            gaps.append(f"I barely see **{b}** in the plan ({_pct(mix, b)}%), but that's my main way in — {pref}.")
    # Channels the persona avoids but the plan over-funds.
    for b in BUCKETS:
        if aff[b] <= -0.6 and mix[b] >= 12:
            avoided = _example(ch.get("avoided", []), b) or b.lower()
            gaps.append(f"You've put **{_pct(mix, b)}%** into **{b}** — that's exactly where I tune out ({avoided}).")
    # Channels that land well.
    for b in BUCKETS:
        if aff[b] >= 0.5 and mix[b] >= 10:
            resonates.append(f"The **{_pct(mix, b)}%** in **{b}** fits how I actually engage.")

    # Message fit vs the persona's decision drivers.
    plan_text = _plan_message_text(result)
    drivers = persona.get("decision_drivers", []) or []
    driver_hits = [d for d in drivers if any(w in plan_text for w in _keywords([d]))]
    if drivers and not driver_hits:
        score -= 6
        gaps.append("The messaging doesn't yet speak to what drives my decisions — "
                    + ", ".join(drivers[:3]) + ".")
    elif driver_hits:
        resonates.append("The plan touches what I decide on: " + ", ".join(driver_hits[:2]) + ".")

    # A characterful watch-out from the persona's frustrations.
    if persona.get("frustrations"):
        gaps.append("And honestly — " + persona["frustrations"][0].rstrip(".").lower() + ".")

    score = int(max(4, min(97, round(score))))
    sentiment = _sentiment(score)

    channel_reactions = []
    for b in BUCKETS:
        if mix[b] >= 5:
            r = "love it" if aff[b] >= 0.5 else ("wasted on me" if aff[b] <= -0.5 else "fine")
            channel_reactions.append({"bucket": b, "pct": _pct(mix, b), "affinity": round(aff[b], 2), "reaction": r})
    channel_reactions.sort(key=lambda x: -x["pct"])

    asks = list(persona.get("what_earns_engagement", []) or [])
    rebalance = _rebalance_hint(aff, mix, ch)
    if rebalance:
        asks.insert(0, rebalance)

    verdict = _verdict(persona, sentiment, score, gaps)
    result_obj = {
        "persona_id": persona.get("id"),
        "persona_name": persona.get("name"),
        "audience_type": persona.get("audience_type"),
        "segment_name": persona.get("segment_name"),
        "who": persona.get("specialty") or persona.get("condition") or "",
        "engagement_likelihood": score,
        "sentiment": sentiment,
        "verdict": verdict,
        "quote": persona.get("voice_sample", ""),
        "resonates": resonates[:4],
        "gaps": gaps[:5],
        "asks": asks[:5],
        "channel_reactions": channel_reactions,
        "narrative": "",
        "narrative_source": "deterministic",
    }
    result_obj["narrative"] = _fallback_narrative(persona, result_obj)
    if use_llm:
        llm = _llm_narrative(persona, result, result_obj)
        if llm:
            result_obj["narrative"] = llm
            result_obj["narrative_source"] = "llm"
    return result_obj


def _example(phrases: list[str], bucket: str) -> str:
    for p in phrases:
        if _bucket_for(p) == bucket:
            return p.lower()
    return ""


def _rebalance_hint(aff: dict, mix: dict, ch: dict) -> str:
    """Suggest moving budget from the persona's most over-funded avoided bucket to their most
    under-funded preferred bucket."""
    worst = max(BUCKETS, key=lambda b: (mix[b] if aff[b] <= -0.6 else -1))
    best = max(BUCKETS, key=lambda b: (aff[b] if mix[b] < 12 else -2))
    if aff[worst] <= -0.6 and mix[worst] >= 12 and aff[best] >= 0.6:
        return f"Shift budget out of {worst} and into {best} — that's the trade that would actually reach me."
    if aff[best] >= 0.7 and mix[best] < 8:
        return f"Put real weight behind {best}; right now it's an afterthought for someone like me."
    return ""


def _verdict(persona: dict, sentiment: str, score: int, gaps: list[str]) -> str:
    name = persona.get("name", "This persona")
    lead = {
        "enthusiastic": "This plan is built for how I engage — I'd lean in.",
        "interested": "There's a real foundation here, but it's not quite reaching me yet.",
        "skeptical": "As written, this plan would mostly pass me by.",
        "resistant": "Honestly, this plan is aimed away from me — I'd disengage.",
    }[sentiment]
    fix = f" The biggest fix: {gaps[0].replace('**', '')}" if gaps else ""
    return f"{lead} (engagement likelihood ~{score}%).{fix}"


def _fallback_narrative(persona: dict, r: dict) -> str:
    bits = [r["verdict"]]
    if r["resonates"]:
        bits.append("What works for me: " + r["resonates"][0].replace("**", ""))
    if r["asks"]:
        bits.append("To win me over: " + r["asks"][0])
    return " ".join(bits)


def _llm_narrative(persona: dict, result: dict, r: dict) -> str | None:
    """Optional: an in-character narrative from the persona. Falls back to None on any failure."""
    try:
        import conversation_llm
        if not conversation_llm.llm_available():
            return None
        client = conversation_llm._get_client()
        mix = _plan_mix(result)
        mix_txt = ", ".join(f"{b} {int(round(p))}%" for b, p in mix.items() if p >= 3)
        brand = result.get("brand", "the brand")
        sys_prompt = (
            f"You are {persona.get('name')}, a {persona.get('audience_type','')} — "
            f"{persona.get('tagline','')}. Background: {persona.get('bio','')} "
            f"Your tone is {persona.get('tone','')}. You are reviewing a pharma omnichannel "
            f"campaign plan that is trying to reach YOU. Be honest and specific, in the first "
            f"person, in your own voice. 2-3 sentences: what you like, what's missing for you, and "
            f"the one thing that would make you engage. Do not be a pushover; do not invent facts."
        )
        user = (
            f"Plan for {brand}. Channel budget split: {mix_txt or 'n/a'}. "
            f"Computed engagement likelihood for you: {r['engagement_likelihood']}%. "
            f"Detected gaps: {'; '.join(g.replace('**','') for g in r['gaps'][:3]) or 'none'}. "
            f"Your channel preferences — prefer: {', '.join((persona.get('channels') or {}).get('preferred', [])[:3])}; "
            f"avoid: {', '.join((persona.get('channels') or {}).get('avoided', [])[:3])}. "
            f"React in character."
        )
        resp = client.messages.create(
            model=conversation_llm.MODEL, max_tokens=260, system=sys_prompt,
            messages=[{"role": "user", "content": user}],
        )
        text = next((b.text for b in resp.content if b.type == "text"), "").strip()
        return text or None
    except Exception:  # noqa: BLE001 -- narrative is enrichment only
        return None


def review_many(personas: list[dict], result: dict, use_llm: bool = True) -> list[dict]:
    return [review(p, result, use_llm=use_llm) for p in personas]
