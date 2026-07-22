"""Market-signals connector implementations. Backend chosen via `OMNI_SIGNALS_BACKEND`
(env/`.env`): "public_health" (default) or "superloop".

`PublicHealthSignalsConnector` wraps the existing `strategy/external_evidence.py`
(reused, not rebuilt) — keyless public APIs (ClinicalTrials.gov, PubMed, openFDA)
that already return small, attributed, citeable datapoints. It is the default because
it is the only backend this repo can actually reach today.

`SuperloopSignalsConnector` is the seam the brief asks for ("the market signals
connector against the Superloop signals source") but is intentionally NOT implemented
against a guessed API contract: this repo has no prior Superloop integration, no
endpoint/auth documented anywhere in the codebase, and no credentials in `.env`.
Fabricating a request shape for a named-but-undocumented external system would produce
code that looks wired but silently fails or worse, misattributes data. Selecting it
raises immediately with what's needed to finish the job for real.
"""
from __future__ import annotations

import os

from strategy import external_evidence
from strategy.planning_v2.connectors.base import MarketSignalsConnector, SignalDatapoint
from strategy.planning_v2.connectors.obsidian import _load_dotenv

_load_dotenv()  # same loader as obsidian.py -- picks up SUPERLOOP_*/OMNI_SIGNALS_BACKEND from .env


class PublicHealthSignalsConnector(MarketSignalsConnector):
    """ClinicalTrials.gov / PubMed / openFDA, via `external_evidence.datapoints()`."""

    def query(self, *, therapy_area: str = "", brand: str = "") -> list[SignalDatapoint]:
        rows = external_evidence.datapoints(therapy_area=therapy_area, brand=brand)
        return [
            SignalDatapoint(
                label=r["label"], value=str(r["value"]), detail=r.get("detail", ""),
                source=r.get("source", ""), source_url=r.get("url", ""), as_of=r.get("as_of", ""),
            )
            for r in rows
        ]


class SuperloopSignalsConnector(MarketSignalsConnector):
    """Not yet configured. Needs, from whoever owns the Superloop account: base URL,
    auth scheme (API key / OAuth), and the query/response shape for a
    therapy-area-or-brand signal lookup. Once known, implement `query()` to call it and
    map rows into `SignalDatapoint` the same way `PublicHealthSignalsConnector` does."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = base_url or os.environ.get("SUPERLOOP_API_URL", "")
        self.api_key = api_key or os.environ.get("SUPERLOOP_API_KEY", "")

    def query(self, *, therapy_area: str = "", brand: str = "") -> list[SignalDatapoint]:
        raise NotImplementedError(
            "OMNI_SIGNALS_BACKEND=superloop selected but this connector has no API contract "
            "implemented yet — Superloop's endpoint/auth/query shape isn't documented anywhere "
            "in this repo. Provide the API details and implement query() here, or switch "
            "OMNI_SIGNALS_BACKEND to 'public_health' to use the working ClinicalTrials.gov/"
            "PubMed/openFDA backend."
        )


_BACKENDS = {
    "public_health": PublicHealthSignalsConnector,
    "superloop": SuperloopSignalsConnector,
}


def get_signals_connector(backend: str | None = None) -> MarketSignalsConnector:
    """Factory: `backend` explicit arg > `OMNI_SIGNALS_BACKEND` env/.env > "public_health"."""
    name = (backend or os.environ.get("OMNI_SIGNALS_BACKEND") or "public_health").strip().lower()
    cls = _BACKENDS.get(name)
    if cls is None:
        raise ValueError(f"Unknown OMNI_SIGNALS_BACKEND '{name}' — choose one of {sorted(_BACKENDS)}")
    return cls()
