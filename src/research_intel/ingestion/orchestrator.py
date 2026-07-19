from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Iterable

import httpx
from dateutil import parser as date_parser
from sqlalchemy.orm import Session

from research_intel.config import Settings
from research_intel.ingestion.base import FetchResult, RawDocument, SourcePolicy
from research_intel.ingestion.clients import build_clients
from research_intel.intelligence.credibility import CredibilityScorer, usage_bucket
from research_intel.intelligence.domain import DomainClassifier
from research_intel.intelligence.embeddings import EmbeddingService
from research_intel.intelligence.extraction import ClaimExtractor
from research_intel.models import Claim, IngestionRun, ManualReviewQueue, ResearchItem, SourceHealth, now_utc
from research_intel.schemas import IngestResponse
from research_intel.services.document_parser import DocumentParserService
from research_intel.services.research_analyzer import ResearchPaperAnalyzer
from research_intel.utils import stable_id, text_hash


class IngestionOrchestrator:
    def __init__(
        self,
        settings: Settings,
        extractor: ClaimExtractor,
        scorer: CredibilityScorer,
        embeddings: EmbeddingService,
        classifier: DomainClassifier | None = None,
        document_parser: DocumentParserService | None = None,
        research_analyzer: ResearchPaperAnalyzer | None = None,
    ) -> None:
        self.settings = settings
        self.extractor = extractor
        self.scorer = scorer
        self.embeddings = embeddings
        self.classifier = classifier or DomainClassifier()
        self.policy = SourcePolicy()
        self.document_parser = document_parser or DocumentParserService(settings)
        self.research_analyzer = research_analyzer or ResearchPaperAnalyzer(settings)

    async def ingest_topic(
        self,
        session: Session,
        *,
        topic: str,
        domain: str | None = None,
        max_per_source: int | None = None,
        dry_run: bool = False,
    ) -> IngestResponse:
        domain_key = self.classifier.key_for_label(domain) if domain else self.classifier.key_for_label(None)
        routes = set(self.classifier.routes_for(domain_key if domain else self.classifier.classify(topic).domain))
        run_id = stable_id("ingestion", topic, now_utc().isoformat())
        run = IngestionRun(run_id=run_id, topic=topic, domain=domain or domain_key)
        if not dry_run:
            session.add(run)
            session.commit()

        timeout = httpx.Timeout(self.settings.request_timeout_seconds)
        headers = {"User-Agent": self.settings.user_agent}
        async with httpx.AsyncClient(timeout=timeout, headers=headers, follow_redirects=True) as http:
            clients = [
                client
                for client in build_clients(http, self.settings)
                if client.enabled() and (client.route_name in routes or not routes)
            ]
            if not clients:
                run.status = "failed"
                run.errors = ["No enabled source clients for this domain. Check API keys or routing."]
                if not dry_run:
                    run.finished_at = now_utc()
                    session.commit()
                return self._response(run)
            limit = max_per_source or self._default_limit(domain_key)
            results = await asyncio.gather(
                *(client.fetch(topic, max_results=limit, domain=domain or domain_key) for client in clients)
            )
            enriched_results: list[FetchResult] = []
            for result in results:
                if result.error or not result.documents:
                    enriched_results.append(result)
                    continue
                documents = await self.document_parser.enrich_documents(http, self._dedupe(result.documents))
                enriched_results.append(
                    FetchResult(
                        source_name=result.source_name,
                        documents=documents,
                        error=result.error,
                    )
                )
            results = enriched_results

        for result in results:
            self._record_source_health(session, result, dry_run=dry_run)
            if result.error:
                run.errors = run.errors or []
                run.errors.append(f"{result.source_name}: {result.error}")
                continue
            for document in self._dedupe(result.documents):
                run.documents_seen += 1
                if not self.policy.allowed(document):
                    continue
                inserted, claim_count = self._persist_document(
                    session, document, domain or domain_key, dry_run=dry_run
                )
                if inserted:
                    run.documents_inserted += 1
                    run.claims_inserted += claim_count
        run.status = "completed_with_errors" if run.errors else "completed"
        run.finished_at = now_utc()
        if not dry_run:
            session.commit()
        return self._response(run)

    def _persist_document(
        self,
        session: Session,
        document: RawDocument,
        domain: str,
        *,
        dry_run: bool,
    ) -> tuple[bool, int]:
        raw_hash = text_hash(document.text or document.title)
        existing = session.query(ResearchItem).filter_by(source_url=document.source_url).one_or_none()
        if existing and existing.raw_text_hash == raw_hash:
            return False, 0
        claims = self.extractor.extract(document)
        credibility_breakdown = self.scorer.score_with_breakdown(document, claims)
        credibility = credibility_breakdown["credibility_score"]
        research_id = stable_id("research", document.source_url)
        if dry_run:
            return True, len(claims)

        item = existing or ResearchItem(research_id=research_id, source_url=document.source_url)
        item.source_type = document.source_type
        item.source_name = document.source_name
        item.publisher = document.metadata.get("publisher") or document.source_name
        item.ingestion_date = now_utc()
        item.credibility_score = credibility
        item.credibility_breakdown = credibility_breakdown
        item.raw_text_hash = raw_hash
        item.title = document.title[:1000]
        item.authors = document.authors[:25]
        item.publication_date = self._parse_date(document.publication_date)
        item.domain_tags = [domain, document.metadata.get("domain", "")]
        
        # Perform comprehensive AI analysis for academic papers
        base_metadata = {**document.metadata, "usage_bucket": usage_bucket(credibility)}
        if document.source_type == "academic":
            analysis = self.research_analyzer.analyze(document)
            if analysis:
                item.metadata_json = self.research_analyzer.enrich_metadata(base_metadata, analysis)
            else:
                item.metadata_json = base_metadata
        else:
            item.metadata_json = base_metadata
        
        item.raw_text = document.text[:30000]
        item.cleaned_text = " ".join((document.text or "").split())[:30000]
        item.parse_status = "parsed" if document.text else "parse_failed"
        
        # Retry merge operation if connection fails
        max_retries = 3
        for attempt in range(max_retries):
            try:
                session.merge(item)
                session.flush()
                break
            except Exception as e:
                session.rollback()
                if attempt < max_retries - 1 and "connection" in str(e).lower():
                    import time
                    time.sleep(2 ** attempt)
                    continue
                else:
                    raise

        if existing:
            for claim in list(existing.claims):
                session.delete(claim)
            session.flush()

        for claim in claims:
            claim_id = stable_id("claim", research_id, claim.claim_text)
            embedding = self.embeddings.embed(
                f"{claim.claim_text} {claim.evidence_summary} {' '.join(claim.applicability_tags)}"
            )
            session.merge(
                Claim(
                    claim_id=claim_id,
                    research_id=research_id,
                    claim_text=claim.claim_text,
                    evidence_summary=claim.evidence_summary,
                    evidence_type=claim.evidence_type,
                    evidence_location=claim.evidence_location,
                    metrics=claim.metrics,
                    conditions=claim.conditions,
                    limitations=claim.limitations,
                    applicability_tags=claim.applicability_tags,
                    domain_tags=[domain],
                    confidence=claim.confidence,
                    extraction_method=claim.extraction_method,
                    embedding=embedding,
                    citation_url=document.source_url,
                    source_quote=(claim.evidence_summary or claim.claim_text)[:500],
                    metadata_json={"usage_bucket": usage_bucket(credibility)},
                )
            )
        if credibility < 60:
            session.merge(
                ManualReviewQueue(
                    review_id=stable_id("review", research_id, "low-credibility"),
                    item_type="research_item",
                    item_id=research_id,
                    reason="Credibility score below recommendation threshold.",
                    payload={"credibility_score": credibility, "source_url": document.source_url},
                )
            )
        
        # Retry commit operation if connection fails
        for attempt in range(max_retries):
            try:
                session.commit()
                break
            except Exception as e:
                session.rollback()
                if attempt < max_retries - 1 and "connection" in str(e).lower():
                    import time
                    time.sleep(2 ** attempt)
                    continue
                else:
                    raise
        
        return True, len(claims)

    def _record_source_health(self, session: Session, result: FetchResult, *, dry_run: bool) -> None:
        if dry_run:
            return
        health = session.query(SourceHealth).filter_by(source_name=result.source_name).one_or_none()
        if not health:
            health = SourceHealth(source_name=result.source_name)
        health.success_count = health.success_count or 0
        health.failure_count = health.failure_count or 0
        health.last_checked_at = now_utc()
        if result.error:
            health.failure_count += 1
            health.last_error = result.error[:1000]
        else:
            health.success_count += 1
            health.last_success_at = now_utc()
            health.last_error = None
        session.merge(health)
        session.commit()

    def _default_limit(self, domain_key: str) -> int:
        if domain_key in {"ai_ml", "legal", "healthcare"}:
            return self.settings.max_papers_per_source
        if domain_key in {"developer_tooling"}:
            return self.settings.max_github_repos
        return self.settings.max_news_articles_per_source

    def _response(self, run: IngestionRun) -> IngestResponse:
        return IngestResponse(
            run_id=run.run_id,
            status=run.status,
            topic=run.topic,
            domain=run.domain,
            documents_seen=run.documents_seen,
            documents_inserted=run.documents_inserted,
            claims_inserted=run.claims_inserted,
            errors=run.errors or [],
        )

    def _dedupe(self, documents: Iterable[RawDocument]) -> list[RawDocument]:
        seen: set[str] = set()
        output: list[RawDocument] = []
        for document in documents:
            if not document.source_url or document.source_url in seen:
                continue
            output.append(document)
            seen.add(document.source_url)
        return output

    def _parse_date(self, value: str | None):
        if not value:
            return None
        try:
            parsed = date_parser.parse(value)
            return parsed.date()
        except (ValueError, TypeError, OverflowError):
            return None
