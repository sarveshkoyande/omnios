"""Stage 3 — Enrich.

Queries the knowledge-graph and market-signals connectors and returns an
`EnrichmentBundle` of everything pulled in, each item already carrying its own
attribution (a `KGResult`'s note/link, a `SignalDatapoint`'s source/URL/as_of) —
that typed attribution *is* how this stage satisfies the brief's "attributing
everything pulled in" requirement, rather than a separate bookkeeping step.

The bundle is deliberately NOT crammed into `StrategicContext`'s fixed fields:
most of what a market signal or a knowledge-graph hit resolves belongs to the
*tactical* plan (e.g. a channel-affinity benchmark answers a targeting-matrix
question, not a brand/market fact), so stage 4 (gap analysis) needs the raw
bundle to check against every Tactical Plan field, not just the handful of
Strategic Context fields. This module does add a conservative, directly-on-
topic subset into `StrategicContext.references`/`provenance` too, so an SCO
serialized on its own still shows its supporting evidence.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from strategy.planning_v2.connectors.base import (
    KGResult,
    KnowledgeGraphConnector,
    MarketSignalsConnector,
    SignalDatapoint,
)
from strategy.planning_v2.connectors.obsidian import get_kg_connector
from strategy.planning_v2.connectors.signals import get_signals_connector
from strategy.planning_v2.models import ProvenanceRef, StrategicContext


class EnrichmentBundle(BaseModel):
    """Everything pulled in from stage 3, kept available for stage 4 (gap
    analysis) to check any Tactical Plan field against, and for stage 6
    (synthesize) to ground the tactical plan in."""

    kg_hits: list[KGResult] = Field(default_factory=list)
    signal_hits: list[SignalDatapoint] = Field(default_factory=list)


def _kg_queries(sco: StrategicContext) -> list[str]:
    queries = []
    disease = sco.market_landscape.disease or sco.brand.indication
    if disease:
        queries.append(f"{disease} omnichannel channel affinity engagement benchmarks HCP")
        queries.append(f"{disease} patient audience segments unbranded content rules")
    for csf in sco.critical_success_factors:
        if csf.key_insight:
            queries.append(csf.key_insight)
    return queries[:6]  # cap: this is a handful of targeted lookups, not open-ended search


def enrich(
    sco: StrategicContext,
    *,
    kg_connector: KnowledgeGraphConnector | None = None,
    signals_connector: MarketSignalsConnector | None = None,
) -> tuple[StrategicContext, EnrichmentBundle]:
    kg = kg_connector or get_kg_connector()
    signals = signals_connector or get_signals_connector()

    kg_hits: list[KGResult] = []
    for q in _kg_queries(sco):
        try:
            kg_hits.extend(kg.query(q, top_k=3))
        except Exception as exc:  # noqa: BLE001 - enrichment is best-effort, never blocks the pipeline
            print(f"[planning_v2.enrich] KG query failed ({q!r}): {exc}")

    try:
        signal_hits = signals.query(
            therapy_area=sco.market_landscape.disease or sco.brand.indication,
            brand=sco.brand.name,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[planning_v2.enrich] signals query failed: {exc}")
        signal_hits = []

    sco = sco.model_copy(deep=True)
    for dp in signal_hits:
        citation = f"{dp.label}: {dp.detail or dp.value} ({dp.source}, {dp.as_of})".strip()
        if citation not in sco.references:
            sco.references.append(citation)
        sco.provenance.setdefault("references", []).append(
            ProvenanceRef(source_type="market_signals", source_id=dp.source_url or dp.source, detail=dp.detail)
        )

    for hit in kg_hits[:5]:  # only the top handful go into the SCO's own references list
        citation = f"Process knowledge: {hit.note_title}"
        if citation not in sco.references:
            sco.references.append(citation)
        sco.provenance.setdefault("references", []).append(
            ProvenanceRef(source_type="knowledge_graph", source_id=hit.link or hit.note_title, detail=hit.snippet[:200])
        )

    return sco, EnrichmentBundle(kg_hits=kg_hits, signal_hits=signal_hits)
