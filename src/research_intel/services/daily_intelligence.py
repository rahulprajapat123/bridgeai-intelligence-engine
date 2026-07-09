from __future__ import annotations

import asyncio
import math
from datetime import UTC, date, datetime
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session

from research_intel.config import Settings
from research_intel.ingestion.base import FetchResult, RawDocument, SourcePolicy
from research_intel.ingestion.clients import build_clients
from research_intel.intelligence.credibility import CredibilityScorer
from research_intel.models import DailyIntelligenceReport, now_utc
from research_intel.services.email_service import NewsletterEmailService
from research_intel.services.newsletter_builder import NewsletterBuilder
from research_intel.utils import parse_year, stable_id, tokenize, unique_keep_order


DEFAULT_TOPICS = [
    "AI in Marketing",
    "AI in Sales",
    "AI in Insights and Analytics",
    "Agentic AI",
    "LLMs",
    "RAG",
    "OpenAI",
    "Claude",
    "Gemini",
    "AI automation",
    "Market intelligence",
    "Customer experience analytics",
]

PRODUCT_UPDATE_QUERIES = [
    "OpenAI latest product updates marketing sales analytics",
    "Anthropic Claude latest updates enterprise AI",
    "Google Gemini latest updates business AI",
    "Microsoft AI blog latest marketing sales analytics",
    "Google Cloud AI blog latest analytics customer experience",
    "AWS AI blog latest generative AI automation",
    "HubSpot AI marketing blog latest updates",
    "Salesforce AI sales blog latest updates",
    "Google Analytics AI analytics updates",
    "Martech AI customer analytics latest updates",
]


class DailyIntelligenceService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.email = NewsletterEmailService(settings)
        self.builder = NewsletterBuilder()
        self.scorer = CredibilityScorer()
        self.policy = SourcePolicy()

    async def generate(
        self,
        session: Session,
        *,
        max_items: int = 20,
        send_email: bool = False,
        recipient: str | None = None,
        topics: list[str] | None = None,
    ) -> tuple[str, bool, dict]:
        selected_topics = topics or DEFAULT_TOPICS
        warnings: list[str] = []
        queries = self._queries(selected_topics)
        documents = await self._fetch_latest(queries, max_items=max_items, warnings=warnings)
        ranked = self._rank(self._dedupe(documents), selected_topics)[:max_items]
        report = self.builder.build(topics=selected_topics, ranked_items=ranked, max_items=max_items)
        if not ranked:
            warnings.append("No sources found; newsletter draft was not generated from external evidence.")
        if not self.settings.openai_api_key:
            warnings.append("OpenAI API key not configured; used deterministic extractive summaries instead of LLM summarization.")

        email_to = recipient or (str(self.settings.daily_email_to) if self.settings.daily_email_to else None)
        email_status = (
            await self.email.send(
                to=email_to,
                subject="AI Daily Intelligence Report",
                body=report["newsletter_draft"] or report["executive_summary"],
            )
            if send_email
            else {
                "sent": False,
                "provider": (self.settings.email_provider or "resend").lower(),
                "message": "Email not requested.",
            }
        )

        report.update(
            {
                "email_status": email_status,
                "warnings": unique_keep_order(warnings),
                "developer_details": {
                    "generated_at": datetime.now(UTC).isoformat(),
                    "topics": selected_topics,
                    "queries": queries,
                    "documents_before_dedupe": len(documents),
                    "documents_after_dedupe": len(self._dedupe(documents)),
                    "ranked_items": len(ranked),
                    "ranking_method": "recency_authority_business_relevance_weighted_scoring",
                    "sources_attempted": self._source_names_attempted(),
                },
            }
        )

        report_id = stable_id("daily-report", datetime.now(UTC).isoformat(), ",".join(selected_topics))
        session.add(
            DailyIntelligenceReport(
                report_id=report_id,
                sent_at=now_utc() if email_status["sent"] else None,
                recipient=email_to,
                topics=selected_topics,
                recipients=[email_to] if email_to else [],
                status="sent" if email_status["sent"] else "generated",
                report=report,
            )
        )
        session.commit()
        return report_id, bool(email_status["sent"]), report

    def _queries(self, topics: list[str]) -> list[str]:
        base = [
            "latest AI marketing automation updates",
            "AI in sales enablement latest tools",
            "customer insights analytics AI trends",
            "agentic AI enterprise use cases",
            "RAG LLM application latest research",
            "AI analytics engine marketing sales insights",
            "AI market intelligence tools latest news",
            "AI customer experience analytics trends",
        ]
        for topic in topics:
            base.append(f"{topic} latest news product updates business implications")
            base.append(f"{topic} latest research tools GitHub repositories")
        base.extend(PRODUCT_UPDATE_QUERIES)
        return unique_keep_order(base)[:24]

    async def _fetch_latest(self, queries: list[str], *, max_items: int, warnings: list[str]) -> list[RawDocument]:
        timeout = httpx.Timeout(float(self.settings.request_timeout_seconds), connect=10.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as http:
            clients = [client for client in build_clients(http, self.settings) if client.route_name in self._preferred_routes()]
            tasks = []
            for client in clients:
                if client.route_name == "github" and not self.settings.github_token:
                    warnings.append("Source unavailable: GitHub — GITHUB_TOKEN missing; skipping GitHub to avoid rate-limit failures.")
                    continue
                if not client.enabled():
                    warnings.append(f"Source unavailable: {client.name} — API key missing.")
                    continue
                query = self._query_for_client(client.route_name, queries)
                tasks.append(self._safe_fetch(client, query, max_items))
            documents: list[RawDocument] = []
            if tasks:
                for result in await asyncio.gather(*tasks):
                    if result.error:
                        warnings.append(f"Source unavailable: {result.source_name} — {result.error}")
                        continue
                    documents.extend(document for document in result.documents if self.policy.allowed(document))
            return documents

    async def _safe_fetch(self, client, query: str, max_items: int) -> FetchResult:
        try:
            return await asyncio.wait_for(
                client.fetch(query, max_results=min(max_items, 10), domain="Daily Intelligence"),
                timeout=min(float(self.settings.request_timeout_seconds) + 5.0, 25.0),
            )
        except TimeoutError:
            return FetchResult(source_name=client.name, error="Source timeout.")
        except Exception as exc:
            return FetchResult(source_name=client.name, error=str(exc))

    def _preferred_routes(self) -> set[str]:
        return {
            "gnews",
            "newsapi",
            "guardian",
            "nytimes",
            "google_news_rss",
            "serpapi_news",
            "semantic_scholar",
            "openalex",
            "arxiv",
            "github",
            "exa",
            "tavily",
            "serper",
            "firecrawl",
            "apify",
            "huggingface",
        }

    def _query_for_client(self, route_name: str, queries: list[str]) -> str:
        if route_name in {"semantic_scholar", "openalex", "arxiv"}:
            return "RAG LLM application latest research agentic AI analytics"
        if route_name == "github":
            return "AI marketing sales analytics automation RAG LLM"
        if route_name in {"exa", "tavily", "serper", "firecrawl", "apify"}:
            return "latest AI marketing sales analytics OpenAI Claude Gemini product updates"
        return queries[0]

    def _dedupe(self, documents: list[RawDocument]) -> list[RawDocument]:
        seen: set[str] = set()
        output: list[RawDocument] = []
        for document in documents:
            key = (document.source_url or document.title).strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            output.append(document)
        return output

    def _rank(self, documents: list[RawDocument], topics: list[str]) -> list[dict]:
        topic_terms = set(tokenize(" ".join([*topics, *PRODUCT_UPDATE_QUERIES])))
        items = [self._item(document, topic_terms) for document in documents]
        items.sort(key=lambda item: item["confidence_score"], reverse=True)
        return items

    def _item(self, document: RawDocument, topic_terms: set[str]) -> dict:
        text = f"{document.title} {document.text}".strip()
        lowered = text.lower()
        doc_terms = set(tokenize(text))
        relevance = min(32.0, len(topic_terms & doc_terms) * 2.4)
        authority = self.scorer.score_with_breakdown(document, [])["source_authority"]
        recency = self._recency(document)
        business = self._business_score(lowered)
        validation = self._validation(document)
        confidence = round(min(100.0, relevance + authority + recency + business + validation), 2)
        category = self._category(lowered, document.source_type)
        return {
            "title": document.title,
            "summary": self._summary(document),
            "why_it_matters": self._why_it_matters(category, document),
            "business_relevance": self._business_relevance(category),
            "source": document.metadata.get("publisher") or document.source_name,
            "url": document.source_url,
            "date": document.publication_date or "",
            "confidence_score": confidence,
            "category": category,
            "source_type": document.source_type,
        }

    def _recency(self, document: RawDocument) -> float:
        year = parse_year(document.publication_date or "") or document.metadata.get("year")
        if not year:
            return 6.0
        age = max(0, date.today().year - int(year))
        if age <= 1:
            return 18.0
        if age <= 2:
            return 14.0
        if age <= 4:
            return 9.0
        return 4.0

    def _validation(self, document: RawDocument) -> float:
        raw = document.metadata.get("citation_count") or document.metadata.get("stars") or 0
        try:
            value = max(0, int(raw))
        except (TypeError, ValueError):
            value = 0
        if value == 0:
            return 4.0 if document.source_type in {"news", "web"} else 2.0
        return min(12.0, math.log10(value + 1) * 4)

    def _business_score(self, text: str) -> float:
        signals = (
            "marketing",
            "sales",
            "customer",
            "analytics",
            "insights",
            "business",
            "automation",
            "market intelligence",
            "product update",
            "enterprise",
            "workflow",
            "revenue",
            "martech",
            "crm",
        )
        hype_penalty = 6.0 if any(term in text for term in ("revolutionary", "game changer", "will replace")) else 0.0
        return max(0.0, min(24.0, sum(2.2 for signal in signals if signal in text) - hype_penalty))

    def _category(self, text: str, source_type: str) -> str:
        if source_type == "academic":
            return "Important Papers"
        if source_type == "code" or "github.com" in text:
            return "GitHub Repositories"
        if any(term in text for term in ("marketing", "martech", "campaign")):
            return "Marketing AI"
        if any(term in text for term in ("sales", "crm", "revenue")):
            return "Sales AI"
        if any(term in text for term in ("analytics", "insights", "business intelligence", "market intelligence")):
            return "Insights / Analytics"
        if any(term in text for term in ("agentic", "llm", "rag", "openai", "claude", "gemini")):
            return "Agentic AI, LLM and RAG"
        return "Top Developments"

    def _summary(self, document: RawDocument) -> str:
        text = " ".join((document.text or document.title).split())
        return text[:360]

    def _why_it_matters(self, category: str, document: RawDocument) -> str:
        if category == "Marketing AI":
            return "May affect campaign automation, content operations, personalization, or martech roadmap decisions."
        if category == "Sales AI":
            return "May affect sales enablement, CRM workflows, revenue operations, or buyer engagement strategy."
        if category == "Insights / Analytics":
            return "May affect how teams generate, explain, and operationalize customer or market insights."
        if category == "Agentic AI, LLM and RAG":
            return "May change architecture choices for AI workflows, knowledge retrieval, automation, or governance."
        if category == "GitHub Repositories":
            return "Developer adoption and repository activity can indicate implementation maturity or tooling risk."
        if category == "Important Papers":
            return "Research evidence can strengthen or challenge claims used in client recommendations."
        return "Relevant signal for client-facing AI strategy and newsletter coverage."

    def _business_relevance(self, category: str) -> str:
        mapping = {
            "Marketing AI": "Useful for marketing leaders evaluating AI-enabled campaign planning, personalization, and analytics.",
            "Sales AI": "Useful for sales and revenue leaders tracking AI-enabled productivity, enablement, and pipeline workflows.",
            "Insights / Analytics": "Useful for insights and analytics leaders modernizing research, BI, and decision support.",
            "Agentic AI, LLM and RAG": "Useful for teams deciding where AI agents, LLM apps, and retrieval systems are mature enough to deploy.",
            "GitHub Repositories": "Useful for technical due diligence and assessing whether tools are implementation-ready.",
            "Important Papers": "Useful for grounding business recommendations in credible technical evidence.",
        }
        return mapping.get(category, "Useful for monitoring AI developments with clear client-newsletter value.")

    def _source_names_attempted(self) -> list[str]:
        return sorted(self._preferred_routes())
