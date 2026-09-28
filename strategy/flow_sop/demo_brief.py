"""The static brief this port generates against, for now.

Ported verbatim from the reference project's `scripts/demo_flow_planner.py`
(the FULL brief it demos with) -- same campaign, same field values, same
field ids. Per this port's scope (see `__init__.py`), OmniOS does not yet
have the intake form these field ids belong to, so the generator is fed this
fixed brief rather than live campaign data; swapping that in later is a
change to whatever calls `values_for()`, not to the SOP rule modules.
"""
from __future__ import annotations

# Each row is (section, field id, value) -- the shape strategy.flow_sop.inputs
# reads. The field ids are the reference project's own (app/seed/
# form_schema.json there); the comments beside them name what the reference
# project's form called them.
_FULL = [
    # --- who and what -----------------------------------------------------
    ("generic", "1.1.9", "Leqvio Fall Push"),          # Campaign Name
    ("generic", "1.1.11", "20241888"),                 # Campaign code, 8 digits
    ("generic", "1.1.12", "Cadenced"),                 # Campaign Type: Model based |
                                                        #   Ad Hoc | Cadenced |
                                                        #   Real-time | Real-time & Cadenced
    ("generic", "1.1.10", "Drive awareness and sample requests"),   # Campaign Goal
    ("generic", "1.1.19", "2026-01-15"),               # Estimated GOLIVE Date

    # Segments. One journey lane is generated per name.
    ("generic", "1.1.13", "Cardiology Naive\nNephrology Experienced"),

    # --- the sends --------------------------------------------------------
    # These four lists line up positionally: the first name goes with the first
    # type, the first Fuse ID and the first Metadata ID. A shorter list is
    # padded with TBD rather than dropped.
    ("touchpoints", "1.3.10", "Get the Facts\nDosing Guide\nSample Request"),  # Touchpoint Name
    ("touchpoints", "1.3.9", "Email\nEmail\nEmail"),   # Touch Point Type
    ("email", "1.6.5", "FA-11234478\nFA-11234479\nFA-11234480"),               # FUSE ID
    ("email", "1.6.4", "M-1001A\nM-1002A\nM-1003A"),   # Email Metadata ID

    # Waits sit *between* sends, so there is one fewer than there are sends.
    # "2 days\n5 days" over three sends gives Day 1, Day 3, Day 8.
    ("touchpoints", "1.3.11", "2 days\n5 days"),       # Wait Time (before next)

    ("touchpoints", "1.3.12", "Yes"),                  # Resend Needed?  Yes | No
    ("touchpoints", "1.3.13", "4 days"),               # Resend Rule
    ("touchpoints", "1.3.14", "Goal met - sample requested"),   # Exit Rule After Send

    # --- suppressions the record supplies (HCP) ---------------------------
    ("dc", "1.8.6", "Cardiology; Nephrology"),         # Specialty Inclusions
    ("dc", "1.8.7", "Oncology"),                       # Specialty Exclusions

    # --- DTC only ---------------------------------------------------------
    # The enrollment sources behind the right-hand pane and the source codes in
    # the qualification block. Ignored on an HCP run, where the SOP says the
    # pane is left empty.
    ("oms", "1.4.3", "VANRAFIA\nIPTACOPAN"),           # Source Name
    ("oms", "1.4.5", "20242025\n20221888"),            # Campaign Source Code
    ("oms", "1.4.4", "Q: Currently treated? A: Yes\nQ: Diagnosed? A: Yes"),    # Survey Q&A pairs
]


def values_for(audience: str = "HCP") -> dict:
    """The FULL brief as a `strategy.flow_sop.inputs`-shaped values dict.

    `audience` is HCP or DTC -- the one field the reference project's own demo
    script sets separately (`--audience`), since it is what the SOP forks the
    whole diagram on.
    """
    values: dict[tuple[str, str], str] = {("generic", "1.1.6"): audience}
    for section, field_id, value in _FULL:
        values[(section, field_id)] = value
    return values
