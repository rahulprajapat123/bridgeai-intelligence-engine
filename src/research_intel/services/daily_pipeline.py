from __future__ import annotations

import asyncio
import re
import time
from datetime import UTC, datetime
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from dateutil import parser as date_parser
from sqlalchemy.orm import Session

from research_intel.config import Settings
from research_intel.ingestion.base import RawDocument
from research_intel.ingestion.daily_connectors import ClientConnector, build_daily_connectors, configuration_snapshot
from research_intel.intelligence_scope import relevance_score
from research_intel.models import (
    DailyAuditLog, DailyRawItem, DailySourceReference, DailySourceRun, DailySummary,
    IngestionBatch, now_utc,
)
from research_intel.utils import stable_id, text_hash, tokenize


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        return ""
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith("utm_") and k.lower() not in {"ref", "source"}])
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ""))


def clean_untrusted(text: str, limit: int) -> str:
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", text or "", flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def identifiers(document: RawDocument) -> dict:
    meta = document.metadata or {}
    url = document.source_url
    arxiv = re.search(r"arxiv\.org/(?:abs|pdf)/([^/?#]+)", url, re.I)
    github = re.search(r"github\.com/([^/]+/[^/?#]+)", url, re.I)
    return {k: v for k, v in {
        "doi": str(meta.get("doi") or "").lower().replace("https://doi.org/", ""),
        "arxiv_id": meta.get("arxiv_id") or (arxiv.group(1).replace(".pdf", "") if arxiv else ""),
        "github_repository": github.group(1).lower().removesuffix(".git") if github else "",
        "semantic_scholar_id": meta.get("paperId") or meta.get("semantic_scholar_id"),
        "openalex_id": meta.get("openalex_id") or meta.get("id"),
        "core_id": meta.get("core_id"),
    }.items() if v}


class DailyIntelligencePipeline:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create_batch(self, session: Session, *, topics: list[str] | None, actor: str) -> IngestionBatch:
        batch_id = stable_id("daily-batch", datetime.now(UTC).isoformat(), actor)
        batch = IngestionBatch(id=batch_id, created_by=actor, configuration_snapshot={"topics": topics or self.settings.daily_topics})
        session.add(batch)
        session.commit()
        return batch

    async def run(self, session: Session, batch_id: str, topics: list[str] | None = None) -> None:
        batch = session.get(IngestionBatch, batch_id)
        if not batch:
            return
        selected_topics = topics or batch.configuration_snapshot.get("topics") or self.settings.daily_topics
        timeout = httpx.Timeout(self.settings.request_timeout_seconds, connect=10)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers={"User-Agent": self.settings.user_agent}) as http:
            connectors = build_daily_connectors(http, self.settings)
            batch.status, batch.started_at, batch.total_sources = "ingesting", now_utc(), len(connectors)
            batch.configuration_snapshot = {"topics": selected_topics, "sources": configuration_snapshot(connectors)}
            session.commit()
            enabled = [c for c in connectors if c.enabled]
            disabled = [c for c in connectors if not c.enabled]
            for connector in disabled:
                self._record_source_run(session, batch_id, connector, "disabled", "Source disabled or credential missing", [], 0)
            # Official/category sources run independently. General web providers use a primary/fallback chain.
            web = [c for c in enabled if c.source_type == "web"]
            direct = [c for c in enabled if c.source_type != "web"]
            documents: list[RawDocument] = []
            failures = 0
            tasks = [asyncio.create_task(self._fetch(connector, selected_topics)) for connector in direct]
            for completed in asyncio.as_completed(tasks):
                connector, docs, error, elapsed = await completed
                status = "unavailable" if error else ("healthy" if docs else "no_results")
                self._record_source_run(session, batch_id, connector, status, error, docs, elapsed)
                documents.extend(docs)
                failures += bool(error)
                if docs:
                    self._persist_and_dedupe(session, batch, docs, selected_topics)
            if web:
                web_order = {"serper": 0, "exa": 1, "tavily": 2, "you": 3, "jina": 4, "apify_google": 5, "apify": 6}
                ordered = sorted(web, key=lambda c: (web_order.get(c.route_name, 5), c.budget.priority))
                for connector in ordered:
                    connector, docs, error, elapsed = await self._fetch(connector, selected_topics)
                    status = "unavailable" if error else ("healthy" if docs else "no_results")
                    self._record_source_run(session, batch_id, connector, status, error, docs, elapsed)
                    documents.extend(docs)
                    failures += bool(error)
                    if docs:
                        self._persist_and_dedupe(session, batch, docs, selected_topics)
                    if not error and len(docs) >= min(5, connector.budget.maximum_items_per_run):
                        break
            batch.successful_sources = session.query(DailySourceRun).filter_by(batch_id=batch_id, status="healthy").count()
            batch.failed_sources = failures
            self._refresh_counts(session, batch)
            batch.status = "summarizing"
            session.commit()
            self.summarize(session, batch)
            batch.status = "awaiting_review" if batch.unique_items else ("partially_completed" if batch.successful_sources else "failed")
            batch.completed_at = now_utc()
            session.commit()

    async def _fetch(self, connector: ClientConnector, topics: list[str]):
        started = time.perf_counter()
        try:
            docs = await connector.fetch(topics, None, connector.budget.maximum_items_per_run)
            return connector, docs, None, int((time.perf_counter() - started) * 1000)
        except Exception as exc:
            return connector, [], str(exc)[:500], int((time.perf_counter() - started) * 1000)

    def _record_source_run(self, session, batch_id, connector, status, error, docs, elapsed):
        session.add(DailySourceRun(
            id=stable_id("source-run", batch_id, connector.route_name), batch_id=batch_id,
            source_name=connector.source_name, source_type=connector.source_type, status=status,
            completed_at=now_utc(), response_time_ms=elapsed, items_returned=len(docs),
            quota_consumed=1 if status != "disabled" else 0, retries=connector.last_retries,
            error_message=error, circuit_breaker_state="open" if connector.circuit_open_until > time.monotonic() else "closed",
        ))
        session.commit()

    def _persist_and_dedupe(self, session: Session, batch: IngestionBatch, documents: list[RawDocument], topics: list[str]) -> None:
        canonical: list[DailyRawItem] = session.query(DailyRawItem).filter_by(batch_id=batch.id, duplicate_of=None).all()
        duplicates = 0
        for doc in documents:
            url = canonical_url(doc.source_url)
            if not url:
                continue
            cleaned = clean_untrusted(doc.text, self.settings.daily_max_content_chars)
            digest = text_hash(cleaned or doc.title)
            ids = identifiers(doc)
            duplicate = self._find_duplicate(canonical, url, digest, ids, doc.title, doc.publication_date)
            item_id = stable_id("daily-item", batch.id, doc.source_name, doc.source_url)
            published = None
            try:
                published = date_parser.parse(doc.publication_date).astimezone(UTC) if doc.publication_date else None
            except (ValueError, TypeError, OverflowError):
                pass
            scoped_relevance = relevance_score(f"{doc.title} {cleaned[:3000]}")
            item = DailyRawItem(
                id=item_id, batch_id=batch.id, source_type=doc.source_type, source_name=doc.source_name,
                external_id=next(iter(ids.values()), None), title=doc.title[:1000], url=doc.source_url,
                canonical_url=url, author=", ".join(str(author) for author in doc.authors[:10] if author), published_at=published,
                original_response={"normalized_document": {"title": doc.title, "url": doc.source_url, "metadata": doc.metadata}},
                raw_content=(doc.text or "")[:self.settings.daily_max_content_chars], cleaned_content=cleaned,
                abstract=cleaned[:3000] if doc.source_type == "academic" else "", description=cleaned[:3000],
                metadata_json={**(doc.metadata or {}), "identifiers": ids}, relevance_score=scoped_relevance,
                credibility_score=self._credibility(doc.source_type, doc.source_name), content_hash=digest,
                duplicate_of=duplicate.id if duplicate else None, processing_status="duplicate" if duplicate else "unprocessed",
            )
            session.add(item)
            if duplicate:
                duplicates += 1
            else:
                canonical.append(item)
            reference_target = duplicate.id if duplicate else item.id
            session.add(DailySourceReference(
                batch_id=batch.id, item_id=reference_target, source_name=doc.source_name,
                external_id=str(next(iter(ids.values()), item_id)), url=doc.source_url, identifiers_json=ids,
            ))
        self._refresh_counts(session, batch)
        session.commit()

    def _refresh_counts(self, session: Session, batch: IngestionBatch) -> None:
        session.flush()
        batch.total_raw_items = session.query(DailyRawItem).filter_by(batch_id=batch.id).count()
        batch.unique_items = session.query(DailyRawItem).filter_by(batch_id=batch.id, duplicate_of=None).count()
        batch.duplicate_items = session.query(DailyRawItem).filter(DailyRawItem.batch_id == batch.id, DailyRawItem.duplicate_of.is_not(None)).count()

    def _find_duplicate(self, items, url, digest, ids, title, publication_date):
        normalized_title = " ".join(tokenize(title))
        for item in items:
            existing_ids = item.metadata_json.get("identifiers", {})
            if url == item.canonical_url or digest == item.content_hash:
                return item
            if any(ids.get(k) and ids.get(k) == existing_ids.get(k) for k in ("doi", "arxiv_id", "github_repository")):
                return item
            similarity = SequenceMatcher(None, normalized_title, " ".join(tokenize(item.title))).ratio()
            if similarity >= .93:
                return item
        return None

    def _credibility(self, source_type: str, source_name: str) -> float:
        base = {"academic": 88, "code": 72, "news": 75, "blog": 62, "web": 55, "social": 42}[source_type]
        return float(base)

    def summarize(self, session: Session, batch: IngestionBatch) -> None:
        items = session.query(DailyRawItem).filter_by(batch_id=batch.id, duplicate_of=None, processing_status="unprocessed").all()
        grouped: dict[str, list[DailyRawItem]] = {}
        for item in items:
            text = item.cleaned_content or item.title
            concise = text[:500]
            citation = {"item_id": item.id, "source_url": item.url, "source_name": item.source_name,
                        "publication_date": item.published_at.isoformat() if item.published_at else None,
                        "source_text_span": text[:300], "page_number": item.metadata_json.get("page_number"),
                        "section_title": item.metadata_json.get("section_title")}
            structured = self._structured(item, concise, citation)
            summary = DailySummary(
                id=stable_id("summary", item.id), batch_id=batch.id, item_id=item.id,
                source_type=item.source_type, source_name=item.source_name, summary_level="item",
                summary_text=concise, structured_summary_json=structured, citations_json=[citation],
            )
            session.add(summary)
            item.processing_status = "processed"
            grouped.setdefault(item.source_type, []).append(item)
        session.flush()
        for source_type, group in grouped.items():
            citations = [{"item_id": i.id, "source_url": i.url, "source_name": i.source_name} for i in group]
            session.add(DailySummary(
                id=stable_id("source-summary", batch.id, source_type), batch_id=batch.id, source_type=source_type,
                summary_level="source_type", summary_text=f"{len(group)} unique {source_type} items collected for review.",
                structured_summary_json={"item_count": len(group), "top_items": [i.title for i in group[:10]]}, citations_json=citations,
            ))
        session.add(DailySummary(
            id=stable_id("batch-summary", batch.id), batch_id=batch.id, source_type="all", summary_level="batch",
            summary_text=f"Working intelligence summary across {len(items)} unique items and {len(grouped)} source types.",
            structured_summary_json={"source_type_counts": {k: len(v) for k, v in grouped.items()}},
            citations_json=[{"item_id": i.id, "source_url": i.url, "source_name": i.source_name} for i in items],
        ))
        batch.summarized_items = len(items)
        session.commit()

    def _structured(self, item, concise, citation):
        base = {"concise_summary": concise, "key_findings": [concise[:240]], "why_it_matters": "Relevant to the configured Daily Intelligence scope.",
                "business_relevance": "Candidate evidence for enterprise AI strategy and implementation decisions.",
                "technologies": [], "industries": [], "topics": [], "important_numbers": re.findall(r"\b\d+(?:\.\d+)?%?\b", concise)[:10],
                "evidence_points": [{"claim": concise[:240], "citation": citation}], "limitations": ["Summary is limited to available source content."],
                "source_quality_notes": f"Credibility score: {item.credibility_score}", "suggested_use": "Human review required before reuse.",
                "confidence_score": min(1, (item.relevance_score + item.credibility_score) / 200)}
        extras = {
            "academic": {"research_problem": "", "methodology": "", "dataset": "", "experiments": "", "main_results": concise, "practical_application": "", "code_repository": "", "benchmark_information": ""},
            "code": {"repository_or_package_name": item.title, "purpose": concise, "programming_language": item.metadata_json.get("language", ""), "installation_method": "", "latest_release": "", "activity_status": "unknown", "licence": item.licence, "stars_or_downloads": item.metadata_json.get("stars", ""), "documentation_quality": "not assessed", "business_use_case": ""},
            "news": {"development": concise, "affected_company": "", "market_impact": "", "product_or_technology": "", "announcement_type": "", "supporting_claims": [citation]},
            "blog": {"development": concise, "affected_company": "", "market_impact": "", "product_or_technology": "", "announcement_type": "analysis", "supporting_claims": [citation]},
            "social": {"discussion_theme": item.title, "sentiment": "not assessed", "engagement": item.metadata_json.get("engagement") or {k: item.metadata_json.get(k) for k in ("score", "num_comments", "comments", "views", "view_count", "answers", "answer_count") if item.metadata_json.get(k) is not None}, "repeated_questions": [], "user_pain_points": [], "emerging_signals": [], "credibility_warning": "Social content is unverified and requires corroboration."},
        }
        base.update(extras.get(item.source_type, {}))
        return base
