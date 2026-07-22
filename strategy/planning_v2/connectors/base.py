"""Swappable connector interfaces for stage 3 (Enrich).

Both interfaces are deliberately narrow (one `query` method each) so a new backend is
just a new class implementing the ABC — `enrich.py` and everything downstream only ever
talks to the interface, never to cognee/requests/a vault path directly.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field


class KGResult(BaseModel):
    """One relevant note (or note fragment) returned by a knowledge-graph query."""

    note_title: str
    link: str = ""  # file path, vault URI, or web link — whatever the backend can offer
    snippet: str
    score: float | None = None


class KnowledgeGraphConnector(ABC):
    """Query in, relevant notes and links out. Implementations: `VaultPathConnector`,
    `CogneeGraphConnector`, `ObsidianRestApiConnector`, `McpObsidianConnector` (see
    `obsidian.py`)."""

    @abstractmethod
    def query(self, text: str, top_k: int = 5) -> list[KGResult]:
        ...


class SignalDatapoint(BaseModel):
    """One quantitative or factual market-signal datapoint."""

    label: str
    value: str
    detail: str = ""
    source: str = ""
    source_url: str = ""
    as_of: str = ""


class MarketSignalsConnector(ABC):
    """Query in, attributed datapoints out. Implementations: `PublicHealthSignalsConnector`
    (working default), `SuperloopSignalsConnector` (not yet configured — see `signals.py`)."""

    @abstractmethod
    def query(self, *, therapy_area: str = "", brand: str = "") -> list[SignalDatapoint]:
        ...
