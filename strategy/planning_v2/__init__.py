"""Strategic-to-Tactical Planning Engine (OmniOS v2).

Seven-stage pipeline: ingest -> extract -> enrich -> gap analysis -> pointed
questions -> synthesize -> handoff. See DESIGN_BRIEF.md at the repo root for
the full spec this package implements against.

Phase 1 (this file's siblings `models.py`) defines the four objects that are
the contract between every stage:
  - StrategicContext   (output of extract + enrich)
  - TacticalPlan       (output of synthesize)
  - Gap                (output of gap analysis; input to the question engine)
  - BusinessRequirementsBrief  (output of synthesize; the handoff artifact)
"""
