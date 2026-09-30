"""Segment SQL without a model (Camille had no fallback: it stopped with an error).

Deliberately literal: it only uses the dataset's own values (brand, speciality, state, consent
status and so on) that appear word for word in the request, plus a few clear numeric phrases
("decile 8 or higher", "engagement score above 10", "not engaged in the last 90 days"). It never
guesses, and its explanation lists exactly what it understood, so the count and the confirmation
that follow show what the segment really contains.
"""
from __future__ import annotations

import re

from .dataset import DMO

_STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA", "colorado": "CO",
    "connecticut": "CT", "delaware": "DE", "district of columbia": "DC", "florida": "FL", "georgia": "GA", "hawaii": "HI",
    "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY", "louisiana": "LA",
    "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
    "new mexico": "NM", "new york": "NY", "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC", "south dakota": "SD",
    "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}

# Text columns whose values are too short or generic to spot on their own ("Yes", "Rep"): read
# only through the phrases below.
_PHRASE_ONLY = {"rep_contact_allowed__c", "active_journey_flag__c", "preferred_channel__c"}
# Words near a value that say which of two columns sharing it is meant ("Opted In": email or SMS).
_COLUMN_CUES = {"email_consent_status__c": ("email",), "sms_consent_status__c": ("sms", "text message")}

_NUMERIC = [  # (column, how the request names it)
    ("decile__c", r"deciles?"),
    ("engagement_score__c", r"engagement scores?"),
    ("years_in_practice__c", r"years (?:in|of) practice"),
    ("trx_last_month__c", r"(?:trx|total prescriptions) (?:in )?(?:the )?last month"),
    ("nrx_last_month__c", r"(?:nrx|new prescriptions) (?:in )?(?:the )?last month"),
    ("rep_calls__c", r"rep calls"),
    ("web_visits__c", r"(?:web|website) visits"),
    ("email_opens__c", r"email opens"),
    ("email_clicks__c", r"email clicks"),
    ("channels_engaged__c", r"channels engaged"),
]
_N = r"(\d+(?:\.\d+)?)"
_COMPARATORS = [  # (pattern after the column's name, operator); the first that matches wins
    (rf"\s*(?:of\s+|is\s+)?(?:between|from)\s+{_N}\s*(?:and|to|-|–)\s*{_N}", "between"),
    (rf"\s*(?:of\s+|is\s+)?{_N}\s*(?:-|–|to)\s*{_N}", "between"),
    (rf"\s*(?:of\s+|is\s+)?(>=|<=|>|<|=)\s*{_N}", "symbol"),
    (rf"\s*(?:of\s+|is\s+)?(?:at least|min(?:imum)?(?: of)?|no less than)\s+{_N}", ">="),
    (rf"\s*(?:of\s+|is\s+)?(?:above|over|more than|greater than|higher than)\s+{_N}", ">"),
    (rf"\s*(?:of\s+|is\s+)?(?:at most|max(?:imum)?(?: of)?|no more than)\s+{_N}", "<="),
    (rf"\s*(?:of\s+|is\s+)?(?:below|under|less than|lower than|fewer than)\s+{_N}", "<"),
    (rf"\s*(?:of\s+|is\s+)?{_N}\s*(?:\+|or (?:more|higher|above|greater))", ">="),
    (rf"\s*(?:of\s+|is\s+)?{_N}\s*or (?:less|lower|fewer|below)", "<="),
    (rf"\s*(?:of\s+|is\s+|=\s*)?{_N}\b(?!\s*(?:%|days|months))", "="),
]


def _label(col: str) -> str:
    return col.removesuffix("__c").replace("_", " ")


def _q(v: str) -> str:
    return "'" + v.replace("'", "''") + "'"


def _num(v: str) -> str:
    return v.rstrip("0").rstrip(".") if "." in v else v


def build(query: str, prof: dict) -> dict:
    """{segmentName, segmentDescription, sql, explanation, understood}."""
    text = query or ""
    taken = [False] * len(text)

    def claim(start: int, end: int) -> bool:
        if any(taken[start:end]):
            return False
        for i in range(start, end):
            taken[i] = True
        return True

    text_hits: dict[str, list[tuple[int, str]]] = {}  # column -> [(position in the request, value)]
    numeric: list[tuple[int, str, str, str]] = []  # (position, column, sql, words)

    def add_text(col: str, value: str, pos: int) -> None:
        vals = text_hits.setdefault(col, [])
        if value not in (v for _, v in vals):
            vals.append((pos, value))

    cols = {c["name"]: c for c in prof["columns"]}
    values_of = {n: list(c.get("values") or []) for n, c in cols.items() if c["kind"] == "text"}

    # Phrase-only columns first, so "active journey" isn't read as the HCP status "Active".
    if values_of.get("active_journey_flag__c"):
        for m in re.finditer(r"\b(not\s+(?:currently\s+)?in|in|outside)\s+(?:an?\s+)?active\s+journeys?\b", text, re.I):
            if claim(m.start(), m.end()):
                add_text("active_journey_flag__c", "Yes" if m.group(1).lower() == "in" else "No", m.start())
    if values_of.get("rep_contact_allowed__c"):
        # Negation only right before the phrase ("no rep contact", "don't allow rep contact").
        for m in re.finditer(r"\b(?:no|not|without|disallow\w*|don'?t|do not)\s+(?:(?:allow|permit)\w*\s+)?rep[- ]contact\b", text, re.I):
            if claim(m.start(), m.end()):
                add_text("rep_contact_allowed__c", "No", m.start())
        for m in re.finditer(r"\brep[- ]contact\s+(?:is\s+)?(not\s+allowed|not\s+permitted|allowed|permitted)\b", text, re.I):
            if claim(m.start(), m.end()):
                add_text("rep_contact_allowed__c", "No" if m.group(1).lower().startswith("not") else "Yes", m.start())
        for m in re.finditer(r"\ballow(?:s|ing)?\s+rep[- ]contact\b", text, re.I):
            if claim(m.start(), m.end()):
                add_text("rep_contact_allowed__c", "Yes", m.start())
    channels = {v.lower(): v for v in values_of.get("preferred_channel__c", []) if v.lower() != "none"}
    if channels:
        alt = "|".join(re.escape(k) for k in sorted(channels, key=len, reverse=True))
        for m in re.finditer(rf"\bprefer(?:s|red|ring)?(?:\s+channel)?(?:\s+is)?\s+(?:the\s+)?({alt})\b", text, re.I):
            if claim(m.start(), m.end()):
                add_text("preferred_channel__c", channels[m.group(1).lower()], m.start())

    # Recency, in days (months are counted as 30 days, and the explanation says so).
    for m in re.finditer(r"\b(not|no|haven'?t|hasn'?t)\b[^.\n]{0,30}?\b(?:engaged|engagement|contacted|reached)\b[^.\n]{0,15}?\b(?:in|for|within)\s+(?:the\s+)?(?:(?:last|past)\s+)?(\d+)\s+(days?|months?)", text, re.I):
        if claim(m.start(), m.end()):
            days = int(m.group(2)) * (30 if m.group(3).lower().startswith("month") else 1)
            numeric.append((m.start(), "days_since_last_engagement__c", f"{DMO}.days_since_last_engagement__c > {days}", f"no engagement in the last {days} days"))
    for m in re.finditer(r"\b(?:engaged|contacted)\b[^.\n]{0,15}?\b(?:in|within)\s+(?:the\s+)?(?:(?:last|past)\s+)?(\d+)\s+(days?|months?)", text, re.I):
        if claim(m.start(), m.end()):
            days = int(m.group(1)) * (30 if m.group(2).lower().startswith("month") else 1)
            numeric.append((m.start(), "days_since_last_engagement__c", f"{DMO}.days_since_last_engagement__c <= {days}", f"engaged in the last {days} days"))
    for m in re.finditer(r"\btop\s+(?:(\d+)\s+)?deciles?\b", text, re.I):
        if claim(m.start(), m.end()):
            n = min(10, max(1, int(m.group(1) or 1)))
            if n == 1:
                numeric.append((m.start(), "decile__c", f"{DMO}.decile__c = 10", "decile 10"))
            else:
                numeric.append((m.start(), "decile__c", f"{DMO}.decile__c >= {11 - n}", f"decile {11 - n} or higher"))

    # Numeric phrases.
    for col, name in _NUMERIC:
        if col not in cols:
            continue
        for m in re.finditer(rf"\b{name}\b", text, re.I):
            rest = text[m.end():]
            for pat, op in _COMPARATORS:
                cm = re.match(pat, rest, re.I)
                if not cm:
                    continue
                end = m.end() + cm.end()
                if not claim(m.start(), end):
                    break
                if op == "between":
                    lo, hi = sorted((float(cm.group(1)), float(cm.group(2))))
                    lo_s, hi_s = _num(str(lo)), _num(str(hi))
                    numeric.append((m.start(), col, f"{DMO}.{col} BETWEEN {lo_s} AND {hi_s}", f"{_label(col)} between {lo_s} and {hi_s}"))
                else:
                    real_op, n = (cm.group(1), cm.group(2)) if op == "symbol" else (op, cm.group(1))
                    numeric.append((m.start(), col, f"{DMO}.{col} {real_op} {_num(n)}", f"{_label(col)} {real_op} {_num(n)}"))
                break

    # States: two-letter codes written in capitals, or full names.
    states = set(values_of.get("state__c", []))
    if states:
        for m in re.finditer(r"\b[A-Z]{2}\b", text):
            if m.group(0) in states and claim(m.start(), m.end()):
                add_text("state__c", m.group(0), m.start())
        for name in sorted(_STATES, key=len, reverse=True):
            code = _STATES[name]
            for m in re.finditer(rf"\b{re.escape(name)}\b", text, re.I):
                if code in states and claim(m.start(), m.end()):
                    add_text("state__c", code, m.start())

    # Every other text value, longest first, as a whole phrase.
    owners: dict[str, list[str]] = {}
    for col, vals in values_of.items():
        if col in _PHRASE_ONLY or col == "state__c":
            continue
        for v in vals:
            if len(v) > 3:
                owners.setdefault(v, []).append(col)
    for v in sorted(owners, key=len, reverse=True):
        for m in re.finditer(rf"(?<![A-Za-z0-9]){re.escape(v)}(?![A-Za-z0-9])", text, re.I):
            if not claim(m.start(), m.end()):
                continue
            col = owners[v][0]
            if len(owners[v]) > 1:
                before = text[max(0, m.start() - 60):m.start()].lower()
                col = next((c for c in owners[v] if any(cue in before for cue in _COLUMN_CUES.get(c, ()))), col)
            add_text(col, v, m.start())

    where: list[str] = []
    understood: list[str] = []
    for c in prof["columns"]:
        vals = [v for _, v in sorted(text_hits.get(c["name"], []))]
        if vals:
            where.append(f"{DMO}.{c['name']} = {_q(vals[0])}" if len(vals) == 1
                         else f"{DMO}.{c['name']} IN ({', '.join(_q(v) for v in vals)})")
            understood.append(f"{_label(c['name'])}: {', '.join(vals)}")
    for _, _, cond, words in sorted(numeric):
        where.append(cond)
        understood.append(words)

    sql = f"SELECT {DMO}.hcp_id__c, {DMO}.KQ_hcp_id__c FROM {DMO}" + (" WHERE " + " AND ".join(where) if where else "")
    if understood:
        name = ("HCPs · " + ", ".join(understood))[:80].rstrip(" ,·")
        description = "HCPs where " + "; ".join(understood) + "."
        explanation = ("Built by rules (the AI model wasn't available), from the parts of your request that match the "
                       "dataset exactly: " + "; ".join(understood) + ". Anything else in the request was not applied.")
    else:
        name = "All HCPs"
        description = "Every HCP in the dataset (no criteria could be matched)."
        explanation = ("Built by rules (the AI model wasn't available), and none of your request matched the dataset's "
                       "values or numeric fields exactly, so this selects every HCP. Rephrase it with the values listed "
                       "in the Dataset tab, or try again when the AI model is available.")
    return {"segmentName": name, "segmentDescription": description, "sql": sql, "explanation": explanation,
            "understood": understood}
