"""Intake field values, read into something the SOP rules can work with.

Ported from the reference project's `app/flow/inputs.py`, unchanged in shape.
That project reads `values` from a live intake form keyed by
`(section_id, field_id)` (e.g. `("generic", "1.1.6")` for Audience); this port
does not yet have that form in OmniOS, so `values` is supplied as a static
dict for now (see `demo_brief.py`) -- `FlowInputs` itself does not know or
care where its dict came from, so wiring a real OmniOS form up later is a
change to the caller, not to this file.

Two jobs. The first is naming: the SOP talks about "Touchpoint Name" and "Wait
Time (before next)", the record holds `touchpoints/1.3.10` and `1.3.11`, and
the mapping between them belongs in one place rather than scattered through
the rule modules.

The second is shape. The SOP wants N touchpoints per segment, each with its
own name, type, wait, resend rule, Fuse ID and Metadata ID. The intake schema
has one text field for each of those, plus a count. So the counts and the
lists are reconciled here: parse what was typed, pad up to the stated count,
and mark what is missing as TBD - which is what the SOP prescribes for an
unavailable value anyway ("else leave TBD"). Inventing touchpoints that were
never described would be worse than saying so.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field as dc_field

from strategy.flow_sop import sop
from strategy.flow_sop.model import BUILT_NOT_LIVE, HOLD, LIVE, NEW, field_ref

# --- where the SOP's names live in the record -----------------------------

F_BRANDED = ("generic", "1.1.5")
F_AUDIENCE = ("generic", "1.1.6")
F_ASSET_SCOPE = ("generic", "1.1.7")
F_CHANNELS = ("generic", "1.1.8")
F_NAME = ("generic", "1.1.9")
F_GOAL = ("generic", "1.1.10")
F_CODE = ("generic", "1.1.11")
F_TYPE = ("generic", "1.1.12")
F_SEGMENTS = ("generic", "1.1.13")
F_GOLIVE = ("generic", "1.1.19")
F_ENROLLMENT = ("generic", "1.4.1")

F_SOURCE_NAME = ("oms", "1.4.3")
F_QNA = ("oms", "1.4.4")
F_SOURCE_CODE = ("oms", "1.4.5")
F_METASHEET = ("cma", "1.4.6")

F_TP_NEXT_LOGIC = ("touchpoints", "1.3.8")
F_TP_TYPE = ("touchpoints", "1.3.9")
F_TP_NAME = ("touchpoints", "1.3.10")
F_TP_WAIT = ("touchpoints", "1.3.11")
F_TP_RESEND_NEEDED = ("touchpoints", "1.3.12")
F_TP_RESEND_RULE = ("touchpoints", "1.3.13")
F_TP_EXIT = ("touchpoints", "1.3.14")
F_TP_COUNT = ("touchpoints", "1.3.15")

F_EMAIL_COUNT = ("email", "1.6.1")
F_EMAIL_NAME = ("email", "1.6.3")
F_EMAIL_METADATA = ("email", "1.6.4")
F_EMAIL_FUSE = ("email", "1.6.5")
F_TOUCHPOINT_COUNT = ("email", "1.3.21")

F_AX_FUSE = ("automx", "1.9.1")
F_AX_SEGMENT = ("automx", "1.9.7")
F_AX_METADATA = ("automx", "1.9.13")

F_TECH_GOLIVE = ("mci", "1.5.2")
F_BIZ_GOLIVE = ("mci", "1.5.3")
F_ONB_GOLIVE = ("onboarding", "1.11.1")
F_OPTOUT = ("onboarding", "1.11.23")

# Go-live, most specific first. The SOP says "From campaign Go-Live Date"
# without saying which of the four the schema carries, so the order is stated
# here where it can be reviewed rather than buried in a lookup.
GOLIVE_FIELDS = [F_GOLIVE, F_ONB_GOLIVE, F_BIZ_GOLIVE, F_TECH_GOLIVE]

_YES = {"yes", "y", "true", "required"}
_DAY_WORDS = {"immediately": 0, "same day": 0, "same-day": 0, "day of": 0}


# --- parsing ---------------------------------------------------------------

def parse_list(raw: str | None) -> list[str]:
    """One text field holding several values, split into them.

    Separators are tried in order of how deliberate they are: a newline is
    unambiguous, a semicolon nearly so, a comma is a guess. Trying them in that
    order stops "Fall HCP push, wave 2" from becoming two touchpoints just
    because a later touchpoint was on its own line.
    """
    if not raw or not raw.strip():
        return []
    text = raw.strip()
    for sep in ("\n", ";", "|"):
        if sep in text:
            return [p.strip() for p in text.split(sep) if p.strip()]
    if "," in text:
        return [p.strip() for p in text.split(",") if p.strip()]
    return [text]


def parse_count(raw: str | None) -> int | None:
    """A stated count: "4", "4 emails", "Four" is not supported."""
    if not raw:
        return None
    m = re.search(r"\d+", str(raw))
    if not m:
        return None
    n = int(m.group())
    return n if 0 < n <= 50 else None


def parse_days(raw: str | None) -> int | None:
    """A wait expressed as whole days, or None if it cannot be read.

    Handles "2", "2 days", "Wait 2 Days", the ISO "P2D", and the words that
    mean zero. Anything else returns None, and the caller renders "Day TBD"
    rather than inventing a schedule the SA never agreed to.
    """
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if not text:
        return None
    if text in _DAY_WORDS:
        return _DAY_WORDS[text]
    iso = re.fullmatch(r"p(\d+)d", text)
    if iso:
        return int(iso.group(1))
    m = re.search(r"(\d+)\s*(day|d\b|week|w\b)?", text)
    if not m:
        return None
    n = int(m.group(1))
    if (m.group(2) or "").startswith("w"):
        n *= 7
    return n if 0 <= n <= 365 else None


def parse_date(raw: str | None) -> dt.date | None:
    """ISO first, then the US formats the sheets tend to carry."""
    if not raw or not str(raw).strip():
        return None
    text = str(raw).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d-%b-%Y", "%d %b %Y"):
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def is_yes(raw: str | None) -> bool:
    return bool(raw) and str(raw).strip().lower() in _YES


# --- the per-touchpoint view ----------------------------------------------

@dataclass
class Touchpoint:
    """One send in the journey, with what is known and what is not.

    `day` is cumulative across the journey: the SOP derives each block's Day X
    from the wait time before it plus everything preceding it.
    """
    index: int
    name: str | None = None
    type: str | None = None
    wait_days: int | None = None
    day: int | None = None
    fuse_id: str | None = None
    metadata_id: str | None = None
    resend_needed: bool = False
    resend_rule: str | None = None
    resend_day: int | None = None
    missing: list[str] = dc_field(default_factory=list)

    @property
    def display_name(self) -> str:
        return self.name or f"Touchpoint {self.index}"


# --- the whole reading -----------------------------------------------------

@dataclass
class FlowInputs:
    """Everything the SOP rules read, already resolved.

    `answers` are the clarifying questions a person has answered. They are a
    second source of truth alongside the record, and a narrow one: a question
    is only ever raised where a resolution order in the SOP has run out, so an
    answer fills a gap the record left rather than overriding anything it
    states. Where both exist the record wins, because the record is the thing
    under version control and approval.
    """
    values: dict
    today: dt.date
    on_hold: bool = False
    answers: dict = dc_field(default_factory=dict)

    def get(self, ref: tuple[str, str]) -> str | None:
        v = self.values.get(ref)
        return v.strip() if isinstance(v, str) and v.strip() else None

    def answer(self, qid: str) -> str | None:
        """What a person said, when the record did not say."""
        v = (self.answers or {}).get(qid)
        return v.strip() if isinstance(v, str) and v.strip() else None

    def cite(self, *refs: tuple[str, str]) -> list[str]:
        """Derivation references, for the fields that actually hold a value."""
        return [field_ref(*r) for r in refs if self.get(r)]

    def first(self, *refs: tuple[str, str]) -> tuple[str | None, list[str]]:
        """The first of several fields that carries a value, and its citation.

        The SOP names alternatives in several places - a Fuse ID sits in both
        the Email and the Automatrix section - and it wants whichever is
        populated, not a preference argued out in code.
        """
        for r in refs:
            v = self.get(r)
            if v:
                return v, [field_ref(*r)]
        return None, []

    # -- headline facts ----------------------------------------------------

    @property
    def audience(self) -> str | None:
        return (sop.normalise_audience(self.get(F_AUDIENCE))
                or sop.normalise_audience(self.answer("audience")))

    @property
    def is_hcp(self) -> bool:
        return self.audience == sop.HCP

    @property
    def campaign_type(self) -> str | None:
        return self.get(F_TYPE)

    @property
    def goal(self) -> str:
        return self.get(F_GOAL) or ""

    @property
    def golive(self) -> tuple[dt.date | None, list[str]]:
        for ref in GOLIVE_FIELDS:
            d = parse_date(self.get(ref))
            if d:
                return d, [field_ref(*ref)]
        # The SOP asks for a go-live when none is registered; a date given in
        # answer anchors Day 1 without being written back into the record,
        # which stays the SA's own edit to make.
        answered = parse_date(self.answer("golive_status"))
        return (answered, []) if answered else (None, [])

    @property
    def enrollment_sources(self) -> list[dict]:
        """The enrollment source box (SOP row 2) and the source pairs (row 3).

        Names, codes and QnA pairs are three parallel lists in three fields, so
        they are zipped positionally. Where one list is shorter the missing
        entries come back as None and the caller renders TBD - a source with no
        code is still a source worth showing.
        """
        names = parse_list(self.get(F_SOURCE_NAME))
        codes = parse_list(self.get(F_SOURCE_CODE))
        qna = parse_list(self.get(F_QNA))
        if not names and not codes:
            return []
        out = []
        for i in range(max(len(names), len(codes))):
            out.append({
                "name": names[i] if i < len(names) else None,
                "code": codes[i] if i < len(codes) else None,
                "qna": qna[i] if i < len(qna) else None,
            })
        return out

    @property
    def declared_segments(self) -> tuple[list[str], list[str]]:
        """Segment names the record already states, with their citation.

        SOP row 9's resolution order starts here; the campaign goal and the
        survey text are tried by the planner only when this comes back empty.
        """
        names = parse_list(self.get(F_SEGMENTS))
        if names:
            return names, self.cite(F_SEGMENTS)
        ax = self.get(F_AX_SEGMENT)
        if ax:
            return parse_list(ax), self.cite(F_AX_SEGMENT)
        answered = parse_list(self.answer("segment_names"))
        if answered:
            # No citation: a person said this, the record did not, and claiming
            # a derivation from a field that is still empty would put a
            # reference in the journey that cannot be traced.
            return answered, []
        return [], []

    # -- touchpoints -------------------------------------------------------

    def touchpoints(self) -> list[Touchpoint]:
        """The journey's sends, reconciled against the stated count.

        Parse the lists, take the longest as the real shape, and never emit
        fewer than the SA said there would be. Each field is resolved
        independently, so a campaign that named its touchpoints but not their
        types produces named blocks with the type marked TBD, rather than an
        all-or-nothing failure.
        """
        names = parse_list(self.get(F_TP_NAME)) or parse_list(self.get(F_EMAIL_NAME))
        types = parse_list(self.get(F_TP_TYPE))
        waits = parse_list(self.get(F_TP_WAIT))
        fuses = parse_list(self.get(F_EMAIL_FUSE)) or parse_list(self.get(F_AX_FUSE))
        metas = parse_list(self.get(F_EMAIL_METADATA)) or parse_list(self.get(F_AX_METADATA))
        resend_rules = (parse_list(self.get(F_TP_RESEND_RULE))
                        or parse_list(self.answer("resend_routing")))

        stated = (parse_count(self.get(F_TP_COUNT))
                  or parse_count(self.get(F_TOUCHPOINT_COUNT))
                  or parse_count(self.get(F_EMAIL_COUNT)))
        parsed = max(len(names), len(types), len(waits), len(fuses), len(metas))
        total = max(stated or 0, parsed)
        if total == 0:
            # Nothing at all was said about touchpoints. One block, wholly TBD,
            # so the journey still has a shape the SA can correct.
            total = 1

        resend_needed = is_yes(self.get(F_TP_RESEND_NEEDED))

        def pick(items: list[str], i: int) -> str | None:
            return items[i] if i < len(items) else None

        out: list[Touchpoint] = []
        day = 0
        for i in range(total):
            tp = Touchpoint(index=i + 1)
            tp.name = pick(names, i)
            tp.type = pick(types, i) or (types[0] if types else None)
            tp.fuse_id = pick(fuses, i)
            tp.metadata_id = pick(metas, i)
            tp.resend_needed = resend_needed
            tp.resend_rule = pick(resend_rules, i) or (resend_rules[0] if resend_rules else None)

            for key, value in (("name", tp.name), ("type", tp.type),
                               ("fuse_id", tp.fuse_id), ("metadata_id", tp.metadata_id)):
                if not value:
                    tp.missing.append(key)

            # Day X: the first send opens the journey; every later one is the
            # previous day plus the wait declared before it.
            wait_raw = pick(waits, i - 1) if i else None
            if i == 0:
                tp.day = 1
                day = 1
            else:
                wait = parse_days(wait_raw)
                if wait is None:
                    tp.day = None
                    tp.missing.append("day")
                else:
                    day += wait
                    tp.day = day
            tp.wait_days = parse_days(pick(waits, i))

            if tp.resend_needed:
                offset = parse_days(tp.resend_rule)
                if offset is None or tp.day is None:
                    tp.resend_day = None
                else:
                    tp.resend_day = tp.day + offset
            out.append(tp)
        return out

    def touchpoint_citations(self) -> list[str]:
        """Every field the touchpoint blocks were read from."""
        return self.cite(F_TP_NAME, F_TP_TYPE, F_TP_WAIT, F_TP_RESEND_NEEDED,
                         F_TP_RESEND_RULE, F_EMAIL_NAME, F_EMAIL_FUSE,
                         F_EMAIL_METADATA, F_AX_FUSE, F_AX_METADATA)

    # -- legend ------------------------------------------------------------

    def golive_status(self) -> tuple[str, dt.date | None, list[str]]:
        """The legend state for this campaign's sends (SOP row 10).

        A go-live that has passed reads as live in production; one still ahead
        reads as new. Neither is asserted - the SOP explicitly says to prompt
        the SA to confirm the status or amend the date, which clarify.py does.
        """
        if self.on_hold:
            return HOLD, None, []
        date, cite = self.golive
        if date is None:
            return BUILT_NOT_LIVE, None, []
        return (LIVE if date <= self.today else NEW), date, cite


def read(values: dict, *, today: dt.date | None = None,
         on_hold: bool = False, answers: dict | None = None) -> FlowInputs:
    """Build the reading for one campaign."""
    return FlowInputs(values=values, today=today or dt.date.today(),
                      on_hold=on_hold, answers=answers or {})
