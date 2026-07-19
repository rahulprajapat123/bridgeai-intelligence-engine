from types import SimpleNamespace

import httpx
import pytest

from research_intel.api.daily_routes import source_run_dict
from research_intel.config import Settings
from research_intel.ingestion.clients import StackExchangeClient, build_clients
from research_intel.ingestion.daily_connectors import ClientConnector, SourceBudget, build_daily_connectors


class DummyClient:
    name = "Dummy"
    route_name = "apify_reddit"
    source_type = "social"

    def enabled(self):
        return True


def test_daily_connector_uses_short_provider_specific_queries():
    connector = ClientConnector(DummyClient(), SourceBudget())
    query = connector._query(["an intentionally oversized topic expression"])
    assert query == "AI agents enterprise"


@pytest.mark.asyncio
async def test_stackexchange_social_connector_normalizes_community_results():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["site"] == "stackoverflow"
        return httpx.Response(200, json={"items": [{
            "title": "How to evaluate an AI sales forecasting pipeline?",
            "link": "https://stackoverflow.com/questions/123/example",
            "creation_date": 1_750_000_000,
            "score": 8,
            "view_count": 420,
            "answer_count": 3,
            "is_answered": True,
            "tags": ["machine-learning", "salesforce"],
        }]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        result = await StackExchangeClient(http, Settings()).fetch("AI sales", max_results=5)
    assert not result.error
    assert len(result.documents) == 1
    assert result.documents[0].source_type == "social"
    assert result.documents[0].metadata["engagement"]["views"] == 420


@pytest.mark.asyncio
async def test_daily_connector_registry_always_has_keyless_social_fallback():
    # Client construction performs no network calls.
    async with httpx.AsyncClient() as async_client:
        connectors = build_daily_connectors(async_client, Settings())
        social = {connector.route_name: connector for connector in connectors if connector.source_type == "social"}
        assert "stackexchange" in social
        assert social["stackexchange"].enabled


def test_source_health_distinguishes_no_results_and_rate_limits():
    base = dict(
        source_name="Example", source_type="social", completed_at=None,
        response_time_ms=100, items_returned=0, quota_consumed=1, retries=0,
        circuit_breaker_state="closed",
    )
    no_results = source_run_dict(SimpleNamespace(**base, status="no_results", error_message=None))
    assert no_results["error_kind"] is None
    assert "no items matched" in no_results["error"]

    limited = source_run_dict(SimpleNamespace(**base, status="unavailable", error_message="HTTP 429 rate limit exceeded"))
    assert limited["error_kind"] == "rate_limited"
    assert "rate limit" in limited["error"].lower()
