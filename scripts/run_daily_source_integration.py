"""Live Daily Intelligence connector integration test.

Runs every configured connector independently, persists usable results into one
PostgreSQL batch, and writes a machine-readable coverage report. This is not for CI.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import httpx

from research_intel.config import Settings
from research_intel.db import SessionLocal
from research_intel.ingestion.daily_connectors import ROUTE_TYPES, build_daily_connectors
from research_intel.models import DailySourceRun, IngestionBatch, now_utc
from research_intel.services.daily_pipeline import DailyIntelligencePipeline


async def main() -> None:
    selected_routes = {x.strip() for x in os.getenv("DAILY_TEST_ROUTES", "").split(",") if x.strip()}
    overrides = {
        route: {"enabled": True, "maximum_items_per_run": 5, "timeout_seconds": 30,
                "retry_count": 1, "backoff_seconds": 1}
        for route in ROUTE_TYPES
    }
    for route in ("apify_deep_crawler", "apify_playwright"):
        overrides[route].update({"timeout_seconds": 150, "retry_count": 0})
    settings = Settings(daily_source_budgets_json=json.dumps(overrides))
    session = SessionLocal()
    pipeline = DailyIntelligencePipeline(settings)
    batch = session.query(IngestionBatch).filter_by(created_by="source-integration-test", status="ingesting").order_by(IngestionBatch.created_at.desc()).first()
    if batch is None:
        batch = pipeline.create_batch(session, topics=settings.daily_topics, actor="source-integration-test")
        batch.status = "ingesting"; batch.started_at = now_utc(); session.commit()
    timeout = httpx.Timeout(35, connect=10)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers={"User-Agent": settings.user_agent}) as http:
            connectors = build_daily_connectors(http, settings)
            if selected_routes:
                connectors = [c for c in connectors if c.route_name in selected_routes]
            batch.total_sources = len(connectors); session.commit()
            completed_names = {r.source_name for r in session.query(DailySourceRun).filter_by(batch_id=batch.id)}
            enabled = [c for c in connectors if c.enabled and c.source_name not in completed_names]
            for connector in [c for c in connectors if not c.enabled]:
                if connector.source_name not in completed_names:
                    pipeline._record_source_run(session, batch.id, connector, "disabled", "Credential missing or source disabled", [], 0)
            tasks = [asyncio.create_task(pipeline._fetch(c, settings.daily_topics)) for c in enabled]
            for task in asyncio.as_completed(tasks):
                connector, docs, error, elapsed = await task
                status = "unavailable" if error else ("healthy" if docs else "no_results")
                pipeline._record_source_run(session, batch.id, connector, status, error, docs, elapsed)
                if docs:
                    pipeline._persist_and_dedupe(session, batch, docs, settings.daily_topics)
        pipeline._refresh_counts(session, batch)
        runs = session.query(DailySourceRun).filter_by(batch_id=batch.id).all()
        batch.successful_sources = sum(r.status == "healthy" for r in runs)
        batch.failed_sources = sum(r.status == "unavailable" for r in runs)
        batch.status = "summarizing"; session.commit()
        pipeline.summarize(session, batch)
        batch.status = "awaiting_review" if batch.unique_items else "failed"
        batch.completed_at = now_utc(); session.commit()
        report = {
            "batch_id": batch.id, "status": batch.status, "fetched": batch.total_raw_items,
            "unique": batch.unique_items, "duplicates": batch.duplicate_items,
            "sources": [{"source_name": r.source_name, "source_type": r.source_type,
                         "status": r.status, "items": r.items_returned,
                         "response_time_ms": r.response_time_ms,
                         "error": ("Source request failed" if r.error_message else None)} for r in runs],
        }
        Path("output").mkdir(exist_ok=True)
        Path("output/daily-source-integration-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
    finally:
        session.close()


if __name__ == "__main__":
    asyncio.run(main())
