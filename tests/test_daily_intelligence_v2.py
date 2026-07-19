from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pypdf import PdfReader
from io import BytesIO
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from research_intel.config import Settings
from research_intel.ingestion.base import FetchResult, RawDocument
from research_intel.ingestion.daily_connectors import ClientConnector, SourceBudget, budgets_from_settings
from research_intel.intelligence_scope import (
    DEFAULT_DAILY_TOPICS, is_in_intelligence_scope, query_for_route, relevance_score,
)
from research_intel.models import Base, DailyIntelligenceReport, DailyRawItem, DailySummary, IngestionBatch
from research_intel.services.daily_pdf import build_comprehensive_pdf, build_daily_pdf
from research_intel.services.daily_pipeline import DailyIntelligencePipeline, canonical_url, clean_untrusted
from research_intel.api.daily_routes import BulkReview, bulk_review, submit
from research_intel.api.signal_filter_routes import (
    BatchFilterRequest, EditorialBriefRequest, create_editorial_brief,
    export_editorial_brief_pdf, export_filtered_pdf, filter_batch, get_editorial_brief,
)


@pytest.fixture()
def daily_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


def test_budget_configuration_is_provider_specific():
    settings = Settings(database_connection_string="sqlite:///:memory:", daily_source_budgets_json='{"arxiv":{"requests_per_minute":2,"maximum_items_per_run":77},"github":{"maximum_items_per_run":12}}')
    budgets = budgets_from_settings(settings)
    assert budgets["arxiv"].requests_per_minute == 2
    assert budgets["arxiv"].maximum_items_per_run == 77
    assert budgets["github"].maximum_items_per_run == 12


def test_commercial_scope_does_not_require_ai_in_headline():
    text = "Salesforce expands revenue intelligence, pipeline forecasting, and sales enablement"
    assert is_in_intelligence_scope(text)
    assert relevance_score(text) >= 40
    assert "revenue operations" in DEFAULT_DAILY_TOPICS
    assert "customer lifetime value" in DEFAULT_DAILY_TOPICS
    assert "platform engineering" in DEFAULT_DAILY_TOPICS


def test_connectors_are_distributed_across_topic_families():
    assert "sales enablement" in query_for_route("newsapi", [])
    assert "product marketing" in query_for_route("gnews", [])
    assert "customer analytics" in query_for_route("google_news_rss", [])
    assert query_for_route("newsapi", []) != query_for_route("gnews", [])


def test_normalization_sanitizes_and_canonicalizes():
    assert canonical_url("HTTPS://Example.com/a/?utm_source=x&ref=y&q=ok#fragment") == "https://example.com/a?q=ok"
    assert clean_untrusted("<script>ignore()</script><p>Useful evidence</p>", 100) == "Useful evidence"


@pytest.mark.asyncio
async def test_connector_retries_without_leaking_provider_logic():
    class Flaky:
        name = "Flaky"; route_name = "arxiv"; source_type = "academic"
        calls = 0
        def enabled(self): return True
        async def fetch(self, query, *, max_results, domain=None):
            self.calls += 1
            if self.calls == 1: return FetchResult(source_name=self.name, error="temporary")
            return FetchResult(source_name=self.name, documents=[RawDocument("Paper", "https://arxiv.org/abs/1", "academic", self.name, "Evidence")])
    connector = ClientConnector(Flaky(), SourceBudget(retry_count=1, backoff_seconds=0, requests_per_minute=1000))
    docs = await connector.fetch(["AI"], None, 10)
    assert docs[0].title == "Paper"
    assert connector.last_retries == 1


def test_deduplication_summary_review_snapshot_and_pdf(daily_session):
    settings = Settings(database_connection_string="sqlite:///:memory:")
    pipeline = DailyIntelligencePipeline(settings)
    batch = pipeline.create_batch(daily_session, topics=["AI agents"], actor="tester")
    docs = [
        RawDocument("Agent Paper", "https://arxiv.org/abs/2401.00001?utm_source=x", "academic", "arXiv", "AI agents improve workflow automation by 20%.", publication_date="2026-01-01", metadata={"doi":"10.1/test"}),
        RawDocument("Agent Paper", "https://doi.org/10.1/test", "academic", "OpenAlex", "AI agents improve workflow automation by 20%.", publication_date="2026-01-01", metadata={"doi":"10.1/test"}),
    ]
    pipeline._persist_and_dedupe(daily_session, batch, docs, ["AI agents"])
    assert batch.total_raw_items == 2 and batch.unique_items == 1 and batch.duplicate_items == 1
    pipeline.summarize(daily_session, batch)
    item = daily_session.query(DailyRawItem).filter_by(batch_id=batch.id, duplicate_of=None).one()
    summary = daily_session.query(DailySummary).filter_by(item_id=item.id).one()
    assert summary.citations_json[0]["source_url"] == item.url
    original = summary.summary_text
    summary.edited_summary_text = "Reviewer-verified summary."; summary.status = "approved"; item.review_status = "edited"
    daily_session.commit()
    assert summary.summary_text == original
    submitted = submit(batch.id, daily_session, "tester")
    assert submitted["status"] == "approved"
    assert submitted["downstream_contract"]["items"][0]["review_status"] == "edited"
    pdf = build_daily_pdf(daily_session, batch)
    assert pdf.startswith(b"%PDF")
    assert "Reviewer-verified" in "".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf)).pages)


def test_comprehensive_pdf_includes_batch_and_legacy_database_data(daily_session):
    pipeline = DailyIntelligencePipeline(Settings(database_connection_string="sqlite:///:memory:"))
    batch = pipeline.create_batch(daily_session, topics=["RAG"], actor="tester")
    pipeline._persist_and_dedupe(daily_session, batch, [RawDocument("RAG & AI", "https://example.com/rag?a=1&b=2", "web", "Example & Co", "Database-backed evidence.")], ["RAG"])
    daily_session.add(DailyIntelligenceReport(report_id="legacy-report", topics=["AI"], report={"executive_summary": "Legacy database summary", "top_developments": [{"title": "Earlier finding", "summary": "Retained evidence", "source": "Archive", "url": "https://example.com/old"}]}))
    daily_session.commit()

    pdf = build_comprehensive_pdf(daily_session)
    text = "".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf)).pages)
    assert pdf.startswith(b"%PDF")
    assert "RAG & AI" in text
    assert "Legacy database summary" in text
    assert "Source Integration Coverage" in text


def test_comprehensive_pdf_is_populated_with_empty_database(daily_session):
    pdf = build_comprehensive_pdf(daily_session)
    text = "".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf)).pages)
    assert len(pdf) > 1000
    assert "No ingestion batches are currently stored" in text


def test_bulk_review_is_atomic_and_skips_missing_ids(daily_session):
    batch = IngestionBatch(id="bulk-batch", status="awaiting_review", review_locked=False)
    item = DailyRawItem(
        id="bulk-item", batch_id=batch.id, source_type="news", source_name="Example",
        title="AI sales automation", url="https://example.com/ai-sales",
        canonical_url="https://example.com/ai-sales", content_hash="bulk-hash",
    )
    summary = DailySummary(
        id="bulk-summary", batch_id=batch.id, item_id=item.id, source_type="news",
        source_name="Example", summary_level="item", summary_text="Informative summary.",
    )
    daily_session.add_all([batch, item, summary]); daily_session.commit()
    result = bulk_review(
        BulkReview(summary_ids=[summary.id, "missing-summary"], action="approve"),
        daily_session, "tester",
    )
    assert result["updated_count"] == 1
    assert result["missing"] == ["missing-summary"]
    assert item.review_status == "approved"


@pytest.mark.asyncio
async def test_approved_batch_filters_and_exports_pdf(daily_session, monkeypatch):
    batch = IngestionBatch(id="filter-batch", status="approved", review_locked=True)
    item = DailyRawItem(
        id="filter-item", batch_id=batch.id, source_type="news", source_name="Example News",
        title="Acme launches secure workflow automation", url="https://example.com/launch",
        canonical_url="https://example.com/launch", content_hash="abc123",
        cleaned_content="Acme launched secure workflow automation for enterprise customers.",
        relevance_score=90, credibility_score=90, review_status="approved",
    )
    summary = DailySummary(
        id="filter-summary", batch_id=batch.id, item_id=item.id, source_type="news",
        source_name=item.source_name, summary_level="item",
        summary_text="Acme launched secure workflow automation for enterprise customers.",
        edited_summary_text="Acme launched secure workflow automation for enterprise customers and reduced review time by 30%.",
        status="approved",
    )
    fallback_batch = IngestionBatch(id="fallback-batch", status="approved", review_locked=True)
    fallback_rows = []
    fallback_topics = [
        ("Revenue operations forecasting", "Revenue operations leaders improved pipeline forecasting accuracy using stage conversion analysis."),
        ("Customer retention playbook", "Customer success teams reduced churn through health scores, renewal planning, and usage analytics."),
        ("Demand generation benchmarks", "Marketing teams compared campaign analytics, lead generation efficiency, and conversion optimization."),
        ("Sales enablement transformation", "Enterprise sales managers redesigned consultative selling and account based selling workflows."),
        ("Product-led growth strategy", "Product managers measured feature adoption, customer lifetime value, and expansion revenue."),
    ]
    for index, (fallback_title, fallback_body) in enumerate(fallback_topics):
        fallback_item = DailyRawItem(
            id=f"fallback-item-{index}", batch_id=fallback_batch.id, source_type="blog",
            source_name="Revenue Blog", title=fallback_title,
            url=f"https://example.com/revenue-{index}", canonical_url=f"https://example.com/revenue-{index}",
            content_hash=f"fallback-hash-{index}", relevance_score=80,
            credibility_score=70, review_status="approved",
        )
        fallback_summary = DailySummary(
            id=f"fallback-summary-{index}", batch_id=fallback_batch.id,
            item_id=fallback_item.id, source_type="blog", source_name="Revenue Blog",
            summary_level="item",
            summary_text=fallback_body,
            status="approved",
        )
        fallback_rows.extend([fallback_item, fallback_summary])
    daily_session.add_all([batch, item, summary, fallback_batch, *fallback_rows]); daily_session.commit()

    import research_intel.db as db_module
    import research_intel.config as config_module
    real_settings = config_module.Settings
    monkeypatch.setattr(db_module, "SessionLocal", lambda: daily_session)
    monkeypatch.setattr(config_module, "Settings", lambda: real_settings(
        database_connection_string="sqlite:///:memory:", openai_api_key=""
    ))

    result = await filter_batch(BatchFilterRequest(
        batch_id=batch.id, novelty_threshold=0, relevance_threshold=0,
        max_items=20, enable_clustering=True, enable_qa=True,
    ))
    assert result["run_id"]
    assert result["summary"]["output_items"] == 6
    primary_result = next(row for row in result["filtered_items"] if row["item_id"] == item.id)
    assert primary_result["url"] == item.url
    assert primary_result["section"] == "News"
    news_section = next(section for section in result["sections"] if section["section"] == "News")
    assert news_section["count"] == 1
    assert news_section["minimum"] == 5
    assert news_section["maximum"] == 20
    assert news_section["shortage"] == 4
    blog_section = next(section for section in result["sections"] if section["section"] == "Blogs")
    assert blog_section["count"] == 5
    assert blog_section["shortage"] == 0
    assert result["summary"]["fallback_items_used"] == 5

    response = await export_filtered_pdf(result["run_id"])
    pdf = b"".join([chunk async for chunk in response.body_iterator])
    assert response.media_type == "application/pdf"
    assert pdf.startswith(b"%PDF")
    text = "".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf)).pages)
    assert "News\n1 filtered signals" in text
    assert "Acme launches secure workflow automation" in text

    brief = await create_editorial_brief(
        result["run_id"], EditorialBriefRequest(use_ai=False)
    )
    assert brief["item_count"] == 6
    assert brief["subject_line"]
    assert len(brief["this_week_in_brief"].split(". ")) >= 4
    primary_brief = next(row for row in brief["items"] if row["item_id"] == item.id)
    assert set(primary_brief) >= {
        "headline", "what_happened", "why_it_matters", "the_move", "function", "source"
    }
    assert primary_brief["source"]["url"] == item.url
    assert get_editorial_brief(result["run_id"])["run_id"] == result["run_id"]

    editorial_response = await export_editorial_brief_pdf(result["run_id"])
    editorial_pdf = b"".join([chunk async for chunk in editorial_response.body_iterator])
    assert editorial_response.media_type == "application/pdf"
    assert editorial_pdf.startswith(b"%PDF")
    editorial_text = "".join(
        page.extract_text() or "" for page in PdfReader(BytesIO(editorial_pdf)).pages
    )
    assert "Editorial Ready Brief" in editorial_text
    assert "This Week in Brief" in editorial_text
    assert "News" in editorial_text
    assert "Acme launches secure workflow automation" in editorial_text
