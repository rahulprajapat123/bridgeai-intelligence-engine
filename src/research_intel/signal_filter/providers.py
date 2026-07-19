from __future__ import annotations

from typing import Protocol

from .models import SignalItem, SignalScores


class EmbeddingProvider(Protocol):
    model_version: str
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class IntelligenceProvider(Protocol):
    model_version: str
    async def extract(self, item: SignalItem) -> SignalItem: ...
    async def score_and_generate(self, item: SignalItem) -> tuple[SignalScores, dict[str, str]]: ...
    async def regenerate_field(self, item: SignalItem, field: str, failure_reason: str, forbidden_phrases: list[str]) -> str: ...


class HistoricalRepository(Protocol):
    async def find_recent_items(self, days: int, domain: str | None = None) -> list[SignalItem]: ...
    async def save_run(self, result: object) -> None: ...
