from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import sessionmaker

from research_intel.config import Settings
from research_intel.ingestion.orchestrator import IngestionOrchestrator
from research_intel.services.daily_intelligence import DailyIntelligenceService

logger = logging.getLogger(__name__)


class IntelligenceScheduler:
    def __init__(
        self,
        settings: Settings,
        session_factory: sessionmaker,
        ingestion: IngestionOrchestrator,
        daily_intelligence: DailyIntelligenceService,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.ingestion = ingestion
        self.daily_intelligence = daily_intelligence
        self.scheduler = BackgroundScheduler(timezone="UTC")

    def start(self) -> None:
        if not self.settings.enable_background_scheduler:
            return
        self.scheduler.add_job(
            self._run_research_ingestion,
            trigger="cron",
            hour=self.settings.research_fetch_hour,
            id="research-ingestion",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self._run_developer_ingestion,
            trigger="cron",
            hour=self.settings.developer_fetch_hour,
            id="developer-ingestion",
            replace_existing=True,
        )
        if self.settings.enable_daily_email:
            self.scheduler.add_job(
                self._run_daily_intelligence,
                trigger="cron",
                hour=self.settings.daily_email_hour,
                id="daily-intelligence-email",
                replace_existing=True,
            )
        self.scheduler.start()
        logger.info("Background scheduler started.")

    def stop(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def _run_research_ingestion(self) -> None:
        async def runner() -> None:
            session = self.session_factory()
            try:
                for topic in self.settings.research_topics:
                    await self.ingestion.ingest_topic(
                        session,
                        topic=topic,
                        domain="AI/ML",
                        max_per_source=self.settings.max_papers_per_source,
                    )
            finally:
                session.close()

        try:
            asyncio.run(runner())
        except Exception:
            logger.exception("Scheduled research ingestion failed.")

    def _run_developer_ingestion(self) -> None:
        async def runner() -> None:
            session = self.session_factory()
            try:
                for topic in ("RAG developer tooling", "vector database SDK", "retrieval evaluation"):
                    await self.ingestion.ingest_topic(
                        session,
                        topic=topic,
                        domain="Developer Tooling",
                        max_per_source=self.settings.max_github_repos,
                    )
            finally:
                session.close()

        try:
            asyncio.run(runner())
        except Exception:
            logger.exception("Scheduled developer ingestion failed.")

    def _run_daily_intelligence(self) -> None:
        async def runner() -> None:
            session = self.session_factory()
            try:
                await self.daily_intelligence.generate(
                    session,
                    max_items=100,
                    send_email=True,
                    recipient=str(self.settings.daily_email_to) if self.settings.daily_email_to else None,
                )
            finally:
                session.close()

        try:
            asyncio.run(runner())
        except Exception:
            logger.exception("Scheduled daily intelligence report failed.")
