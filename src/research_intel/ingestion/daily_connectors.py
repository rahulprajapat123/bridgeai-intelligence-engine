from __future__ import annotations

import asyncio
import json
import random
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Protocol

import httpx

from research_intel.config import Settings
from research_intel.ingestion.base import RawDocument
from research_intel.ingestion.clients import build_clients
from research_intel.intelligence_scope import query_for_route


SOURCE_TYPES = {"academic", "code", "news", "blog", "web", "social"}
ROUTE_TYPES = {
    "arxiv": "academic", "semantic_scholar": "academic", "openalex": "academic",
    "paperswithcode": "academic", "core": "academic", "github": "code",
    "huggingface": "code", "npm": "code", "pypi": "code", "newsapi": "news",
    "gnews": "news", "google_news_rss": "news", "serpapi_news": "news",
    "guardian": "news", "nytimes": "news", "hackernews": "news", "gdelt": "news",
    "producthunt": "news", "apify_news": "news", "google_trends": "news",
    "devto": "blog", "rss": "blog",
    "towardsdatascience": "blog", "kdnuggets": "blog", "importai": "blog",
    "serper": "web", "exa": "web", "tavily": "web", "jina": "web", "you": "web",
    "firecrawl": "web", "apify": "web", "apify_google": "web",
    "apify_reddit": "social", "apify_reddit_fast": "social", "stackexchange": "social",
    "apify_business_leads": "news",
    "apify_deep_crawler": "web", "apify_playwright": "web",
}


@dataclass(slots=True)
class SourceBudget:
    enabled: bool = True
    requests_per_minute: int = 30
    requests_per_day: int = 1000
    maximum_items_per_run: int = 25
    page_size: int = 25
    maximum_pages_per_run: int = 1
    timeout_seconds: float = 20
    retry_count: int = 1
    backoff_seconds: float = 1
    concurrency: int = 1
    priority: int = 1
    supports_incremental_fetch: bool = False
    supports_full_text: bool = False
    requires_api_key: bool = False
    licence_or_access_policy: str = "metadata_and_links_only"


class SourceConnector(Protocol):
    source_name: str
    source_type: str
    route_name: str
    budget: SourceBudget

    async def fetch(self, topics: list[str], since: datetime | None, limit: int) -> list[RawDocument]: ...


class TokenBucket:
    def __init__(self, per_minute: int) -> None:
        self.capacity = max(1, per_minute)
        self.tokens = float(self.capacity)
        self.rate = self.capacity / 60
        self.updated = time.monotonic()
        self.lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self.lock:
            now = time.monotonic()
            self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rate)
            self.updated = now
            if self.tokens < 1:
                await asyncio.sleep((1 - self.tokens) / self.rate)
                self.tokens = 0
            else:
                self.tokens -= 1


class ClientConnector:
    def __init__(self, client, budget: SourceBudget) -> None:
        self.client = client
        self.source_name = client.name
        self.route_name = client.route_name
        self.source_type = ROUTE_TYPES.get(client.route_name, client.source_type)
        self.budget = budget
        self.bucket = TokenBucket(budget.requests_per_minute)
        self.failures = 0
        self.circuit_open_until = 0.0
        self.last_retries = 0

    @property
    def enabled(self) -> bool:
        return self.budget.enabled and self.client.enabled()

    async def fetch(self, topics: list[str], since: datetime | None, limit: int) -> list[RawDocument]:
        if time.monotonic() < self.circuit_open_until:
            raise RuntimeError("circuit breaker is open")
        query = self._query(topics)
        allowed = min(limit, self.budget.maximum_items_per_run)
        last_error = "source failed"
        for attempt in range(self.budget.retry_count + 1):
            self.last_retries = attempt
            await self.bucket.acquire()
            try:
                result = await asyncio.wait_for(
                    self.client.fetch(query, max_results=allowed, domain="Daily Intelligence"),
                    timeout=self.budget.timeout_seconds,
                )
                if result.error:
                    raise RuntimeError(result.error)
                self.failures = 0
                docs = result.documents[:allowed]
                for doc in docs:
                    doc.source_type = self.source_type
                return docs
            except Exception as exc:
                last_error = str(exc)
                self.failures += 1
                if self.failures >= 3:
                    self.circuit_open_until = time.monotonic() + 60
                permanent = any(marker in last_error.lower() for marker in ("400 bad request", "requires package name", "authentication", "forbidden", "no results found"))
                if attempt < self.budget.retry_count and not permanent:
                    await asyncio.sleep(self.budget.backoff_seconds * (2**attempt) + random.uniform(0, .5))
                elif permanent:
                    break
        raise RuntimeError(last_error)

    def _query(self, topics: list[str]) -> str:
        """Use provider-compatible queries instead of one oversized Boolean expression."""
        strategies = {
            "npm": "ai agents",
            "pypi": "openai",
            "gnews": "artificial intelligence",
            "core": "artificial intelligence",
            "paperswithcode": "language models",
            "gdelt": "artificial intelligence",
            "hackernews": "AI",
            "producthunt": "AI",
            "devto": "ai",
            "rss": "AI",
            "towardsdatascience": "artificial intelligence",
            "kdnuggets": "AI",
            "importai": "AI",
            "semantic_scholar": "artificial intelligence",
            "apify_reddit": "AI agents enterprise",
            "apify_reddit_fast": "AI agents enterprise automation",
            "stackexchange": "AI automation",
            "google_trends": "artificial intelligence",
            "apify_business_leads": "technology",
        }
        if self.route_name in strategies:
            return strategies[self.route_name]
        return query_for_route(self.route_name, topics)


def budgets_from_settings(settings: Settings) -> dict[str, SourceBudget]:
    try:
        overrides = json.loads(settings.daily_source_budgets_json or "{}")
    except json.JSONDecodeError:
        overrides = {}
    output = {}
    for route in ROUTE_TYPES:
        values = overrides.get(route, {})
        output[route] = SourceBudget(**{k: v for k, v in values.items() if k in SourceBudget.__dataclass_fields__})
    # Browser/actor fallbacks are deliberately conservative unless explicitly overridden.
    for route in ("apify", "apify_google", "apify_deep_crawler", "apify_playwright"):
        if route not in overrides:
            output[route].timeout_seconds = 25
            output[route].retry_count = 0
            output[route].priority = 5
    # RSS-based sources need longer timeouts
    for route in ("kdnuggets", "importai", "towardsdatascience", "devto", "rss"):
        if route not in overrides:
            output[route].timeout_seconds = 30
    # Academic APIs with rate limits need longer timeouts and lower concurrency
    for route in ("semantic_scholar", "paperswithcode"):
        if route not in overrides:
            output[route].timeout_seconds = 50
            output[route].retry_count = 2  # Allow retries for transient errors
    # Semantic Scholar specifically needs very conservative settings due to strict 1 req/sec limit
    if "semantic_scholar" not in overrides:
        output["semantic_scholar"].requests_per_minute = 40  # 40/60 = 0.66 per second (well under 1/sec)
        output["semantic_scholar"].maximum_items_per_run = 10  # Limit items to reduce total time
        output["semantic_scholar"].priority = 3  # Lower priority (higher number = lower priority)
    if "stackexchange" not in overrides:
        output["stackexchange"].requests_per_minute = 10
        output["stackexchange"].maximum_items_per_run = 15
        output["stackexchange"].retry_count = 1
    return output


def configuration_snapshot(connectors: list[ClientConnector]) -> dict:
    return {c.route_name: {"source_name": c.source_name, "source_type": c.source_type, **asdict(c.budget)} for c in connectors}


def build_daily_connectors(http: httpx.AsyncClient, settings: Settings) -> list[ClientConnector]:
    budgets = budgets_from_settings(settings)
    return [ClientConnector(client, budgets[client.route_name]) for client in build_clients(http, settings) if client.route_name in budgets]
