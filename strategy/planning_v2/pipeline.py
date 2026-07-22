"""Stage orchestration + Stage 7 (Handoff).

`PlanningRun` is the persisted state machine that walks a document through all
seven stages. One JSON file per run under `data/planning_v2_runs/<run_id>.json`
(same file-backed-under-DATA_DIR convention as the rest of this app — see
`strategy/paths.py`), so a run survives a server restart the same way every
other piece of app state does.

Stage flow:
  ingested -> extracted -> enriched -> gaps_analyzed -> awaiting_answers
  -> synthesized -> validated -> handed_off

`awaiting_answers` is where the pipeline pauses for the human: everything up
to gap analysis runs automatically, then `pending_questions()` exposes the
ranked question set for the UI (Phase 7) to render in the chat column.
Calling `finish()` before every question is answered or explicitly skipped
falls back to each unanswered question's `suggested_default` rather than
blocking forever — the brief's "ideally resolved in one round" is a target,
not a hard requirement to keep the pipeline usable.
"""
from __future__ import annotations

import json
import uuid
from typing import Literal

from pydantic import BaseModel, Field

from strategy.paths import data_path, ensure_data_dir
from strategy.planning_v2.compliance import ComplianceReport, validate as validate_compliance
from strategy.planning_v2.enrich import EnrichmentBundle, enrich
from strategy.planning_v2.extract import extract_strategic_context
from strategy.planning_v2.gap_analysis import analyze_gaps
from strategy.planning_v2.ingest import IngestedDocument, ingest_bytes
from strategy.planning_v2.models import BusinessRequirementsBrief, Gap, StrategicContext, TacticalPlan
from strategy.planning_v2.questions import QuestionSet, apply_answer, build_question_set

Stage = Literal[
    "ingested", "extracted", "enriched", "gaps_analyzed", "awaiting_answers",
    "synthesized", "validated", "handed_off",
]

_RUNS_DIR = "planning_v2_runs"


class PlanningRun(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    stage: Stage = "ingested"
    doc: IngestedDocument | None = None
    strategic_context: StrategicContext | None = None
    enrichment: EnrichmentBundle | None = None
    gaps: list[Gap] = Field(default_factory=list)
    tactical_plan: TacticalPlan | None = None
    brb: BusinessRequirementsBrief | None = None
    compliance: ComplianceReport | None = None

    def pending_questions(self) -> QuestionSet:
        return build_question_set(self.gaps)

    def save(self) -> None:
        ensure_data_dir()
        path = data_path(_RUNS_DIR, f"{self.id}.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def load(cls, run_id: str) -> "PlanningRun":
        path = data_path(_RUNS_DIR, f"{run_id}.json")
        if not path.exists():
            raise FileNotFoundError(f"No planning run '{run_id}'")
        return cls.model_validate_json(path.read_text(encoding="utf-8"))


def start_run(content: bytes, filename: str) -> PlanningRun:
    """Stages 1-4: ingest, extract, enrich, gap-analyze — then pause for answers."""
    doc = ingest_bytes(content, filename)
    run = PlanningRun(doc=doc, stage="ingested")

    sco = extract_strategic_context(doc)
    run.strategic_context = sco
    run.stage = "extracted"

    enriched_sco, bundle = enrich(sco)
    run.strategic_context = enriched_sco
    run.enrichment = bundle
    run.stage = "enriched"

    run.gaps = analyze_gaps(enriched_sco, bundle)
    run.stage = "gaps_analyzed"
    run.stage = "awaiting_answers"
    run.save()
    return run


def answer(run: PlanningRun, field: str, value: str) -> PlanningRun:
    run.gaps = apply_answer(run.gaps, field, value)
    run.save()
    return run


def finish_run(run: PlanningRun, *, accept_remaining_defaults: bool = True) -> PlanningRun:
    """Stages 5-6: fall back unanswered questions to their suggested_default (if allowed),
    then synthesize the Tactical Plan + BRB and run the compliance validator over it."""
    if accept_remaining_defaults:
        for g in list(run.gaps):
            if not g.inferable:
                run.gaps = apply_answer(run.gaps, g.field, g.suggested_default or "Accepted default.")

    unresolved = [g.field for g in run.gaps if not g.inferable]
    if unresolved:
        raise ValueError(f"Cannot finish run with unresolved gaps: {unresolved}")

    from strategy.planning_v2.synthesize import synthesize

    plan, brb = synthesize(run.strategic_context, run.enrichment, run.gaps)
    run.tactical_plan = plan
    run.brb = brb
    run.stage = "synthesized"

    run.compliance = validate_compliance(plan, run.strategic_context)
    run.stage = "validated"
    run.save()
    return run


def handoff(run: PlanningRun) -> dict:
    """Stage 7 — emit the BRB as the orchestration input. Refuses to hand off a plan
    that still has open compliance blockers; those must be resolved (by fixing the
    plan and re-validating) before this becomes another system's input."""
    if run.stage != "validated" or run.brb is None or run.compliance is None:
        raise ValueError("Run must be synthesized and validated before handoff.")
    if not run.compliance.passed:
        raise ValueError(
            f"Refusing handoff: {len(run.compliance.blockers)} unresolved compliance "
            f"blocker(s) — {[b.rule for b in run.compliance.blockers]}"
        )
    run.stage = "handed_off"
    run.save()
    return run.brb.model_dump(mode="json")
