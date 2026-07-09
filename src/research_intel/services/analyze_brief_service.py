from __future__ import annotations

import asyncio
from typing import Any

import httpx
from fastapi import UploadFile

from research_intel.ingestion.base import FetchResult, RawDocument, SourcePolicy
from research_intel.ingestion.clients import build_clients
from research_intel.schemas import BriefAnalysis
from research_intel.services.evidence_ranker import EvidenceRanker, RankedEvidence
from research_intel.services.factory import AppServices
from research_intel.services.file_parser import BriefFileParser, UnsupportedBriefFile
from research_intel.services.implementation_planner import ImplementationPlanner
from research_intel.services.query_planner import QueryPlanner
from research_intel.services.source_router import SourceRouter
from research_intel.utils import sentence_split, unique_keep_order


class AnalyzeBriefService:
    def __init__(self, services: AppServices) -> None:
        self.services = services
        self.parser = BriefFileParser()
        self.query_planner = QueryPlanner()
        self.source_router = SourceRouter()
        self.ranker = EvidenceRanker(services.scorer)
        self.implementation_planner = ImplementationPlanner()
        self.policy = SourcePolicy()

    async def analyze(
        self,
        *,
        file: UploadFile | None,
        brief_text: str | None,
        domain_override: str | None,
        top_k: int,
        include_papers: bool,
        include_github: bool,
        include_blogs: bool,
        include_news: bool,
    ) -> dict[str, Any]:
        warnings: list[str] = []
        text, filename = await self._load_text(file, brief_text)
        if len(text.strip()) < 20:
            raise ValueError("Brief must contain at least 20 characters of readable text.")

        if not self.services.settings.openai_api_key:
            warnings.append("OpenAI API key not configured; using deterministic brief understanding and implementation planning.")

        analysis = self.services.brief.analyze(text)
        domain = (domain_override or analysis.primary_domain or analysis.domain.domain or "AI/ML").strip()
        routes = self.source_router.route_names(
            domain,
            include_papers=include_papers,
            include_github=include_github,
            include_blogs=include_blogs,
            include_news=include_news,
        )
        queries = self.query_planner.plan(text, analysis, domain, top_k)
        expanded_queries = self.query_planner.expand(queries, domain)

        self._add_configuration_warnings(
            warnings,
            routes=routes,
            include_github=include_github,
            include_news=include_news,
            analysis=analysis,
        )

        documents = await self._fetch_sources(
            routes=routes,
            queries=expanded_queries,
            domain=domain,
            top_k=top_k,
            warnings=warnings,
        )
        deduped = self._dedupe_documents(documents)
        ranked = self.ranker.rank(deduped, text, expanded_queries, domain)[:top_k]
        solution = self.implementation_planner.build(text, analysis, ranked, warnings)

        if not ranked:
            warnings.append("No sources found; generated an initial brief-based implementation plan.")

        return {
            "brief_understanding": self._brief_understanding(analysis, domain, expanded_queries),
            "solution": solution,
            "evidence": self._evidence_groups(ranked),
            "ranked_recommendations": self._ranked_recommendations(ranked, solution),
            "source_table": [self._source_item(item) for item in ranked],
            "warnings": unique_keep_order(warnings),
            "developer_details": {
                "filename": filename,
                "brief_length": len(text),
                "domain_override": domain_override,
                "resolved_domain": domain,
                "selected_routes": routes,
                "queries": queries,
                "expanded_queries": expanded_queries,
                "documents_before_dedupe": len(documents),
                "documents_after_dedupe": len(deduped),
                "ranking_method": "fallback_weighted_scoring",
                "ranking_stages": [
                    "Query Decomposition",
                    "Query Expansion",
                    "Domain-aware Source Routing",
                    "Hybrid Retrieval",
                    "Credibility Scoring",
                    "Domain Relevance Scoring",
                    "Fallback Weighted Re-Ranking",
                    "Final Recommendation Generation",
                ],
            },
        }

    async def _load_text(self, file: UploadFile | None, brief_text: str | None) -> tuple[str, str | None]:
        parts: list[str] = []
        filename = None
        if file is not None and file.filename:
            filename = file.filename
            content = await file.read()
            try:
                parsed = self.parser.parse(file.filename, content)
            except UnsupportedBriefFile:
                raise
            except Exception as exc:
                raise UnsupportedBriefFile(f"Could not read uploaded file: {exc}") from exc
            if parsed:
                parts.append(parsed)
        if brief_text and brief_text.strip():
            parts.append(brief_text.strip())
        if not parts:
            raise ValueError("Upload a brief file or paste brief text before analyzing.")
        return "\n\n".join(parts), filename

    def _add_configuration_warnings(
        self,
        warnings: list[str],
        *,
        routes: list[str],
        include_github: bool,
        include_news: bool,
        analysis: BriefAnalysis,
    ) -> None:
        settings = self.services.settings
        if include_github and "github" in routes and not settings.github_token:
            warnings.append("Source unavailable: GitHub — GITHUB_TOKEN missing; skipping GitHub to avoid rate-limit failures.")
        if include_news and not any(
            [
                settings.newsapi_key,
                settings.gnews_api_key,
                settings.guardian_api_key,
                settings.nytimes_api_key,
                settings.serpapi_api_key,
            ]
        ):
            warnings.append("Source unavailable: paid news APIs — no news API key configured; using free sources where available.")
        constraints = analysis.constraints or {}
        if any(
            constraints.get(key)
            for key in ("requires_brightedge_export", "requires_sprinklr_export", "requires_adbeat_export")
        ):
            warnings.append("Private source not configured.")

    async def _fetch_sources(
        self,
        *,
        routes: list[str],
        queries: list[str],
        domain: str,
        top_k: int,
        warnings: list[str],
    ) -> list[RawDocument]:
        timeout = httpx.Timeout(float(self.services.settings.request_timeout_seconds), connect=10.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as http:
            clients = {client.route_name: client for client in build_clients(http, self.services.settings)}
            documents: list[RawDocument] = []
            tasks = []
            for route in routes:
                client = clients.get(route)
                if client is None:
                    warnings.append(f"Source unavailable: {route} — connector not implemented.")
                    continue
                if route == "github" and not self.services.settings.github_token:
                    continue
                if not client.enabled():
                    warnings.append(f"Source unavailable: {client.name} — API key missing.")
                    continue
                query = self._query_for_route(route, queries)
                tasks.append(self._safe_fetch(client, query, top_k, domain))

            if tasks:
                for result in await asyncio.gather(*tasks):
                    if result.error:
                        warnings.append(f"Source unavailable: {result.source_name} — {result.error}")
                        continue
                    documents.extend(document for document in result.documents if self.policy.allowed(document))
            return documents

    async def _safe_fetch(self, client, query: str, top_k: int, domain: str) -> FetchResult:
        try:
            return await client.fetch(query, max_results=min(max(top_k, 3), 10), domain=domain)
        except Exception as exc:
            return FetchResult(source_name=client.name, error=str(exc))

    def _query_for_route(self, route: str, queries: list[str]) -> str:
        if route in {"github", "huggingface"}:
            return queries[min(1, len(queries) - 1)]
        if route in {"newsapi", "gnews", "google_news_rss", "serpapi_news", "guardian", "nytimes"}:
            return queries[min(2, len(queries) - 1)]
        return queries[0]

    def _dedupe_documents(self, documents: list[RawDocument]) -> list[RawDocument]:
        seen: set[str] = set()
        output: list[RawDocument] = []
        for document in documents:
            key = (document.source_url or document.title).strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            output.append(document)
        return output

    def _brief_understanding(self, analysis: BriefAnalysis, domain: str, queries: list[str]) -> dict[str, Any]:
        constraints = analysis.constraints or {}
        constraint_list = [
            f"{key.replace('_', ' ')}: {value}"
            for key, value in constraints.items()
            if value not in (False, None, "", [])
        ]
        return {
            "title": analysis.title,
            "summary": analysis.objective or analysis.intent,
            "objective": analysis.objective,
            "problem_statement": analysis.intent,
            "domain": domain,
            "subdomain": ", ".join(analysis.secondary_domains[:3]),
            "intent": analysis.intent,
            "target_audience": analysis.audience,
            "requirements": analysis.research_questions or analysis.deliverables,
            "constraints": constraint_list,
            "deliverables": analysis.deliverables,
            "inputs": analysis.inputs,
            "outputs": analysis.outputs,
            "risks": analysis.risks,
            "dependencies": analysis.dependencies,
            "success_criteria": self._success_criteria(analysis),
            "recommended_search_queries": queries[:10],
        }

    def _success_criteria(self, analysis: BriefAnalysis) -> list[str]:
        criteria = [
            "Recommendations cite traceable sources with URLs.",
            "Implementation plan is specific enough for manager review.",
            "Risks, assumptions, and missing source coverage are explicit.",
        ]
        if analysis.deliverables:
            criteria.append(f"Requested deliverables are covered: {', '.join(analysis.deliverables[:3])}.")
        return criteria

    def _evidence_groups(self, ranked: list[RankedEvidence]) -> dict[str, list[dict[str, Any]]]:
        groups = {
            "papers": [],
            "github_repositories": [],
            "blogs": [],
            "news": [],
            "industry_sources": [],
        }
        for item in ranked:
            source_type = item.document.source_type
            source_name = item.document.source_name.lower()
            rendered = self._source_item(item)
            if source_type == "academic":
                groups["papers"].append(rendered)
            elif source_type == "code" or "github" in source_name:
                groups["github_repositories"].append(rendered)
            elif source_type == "news":
                groups["news"].append(rendered)
            elif source_type == "web":
                groups["blogs"].append(rendered)
            else:
                groups["industry_sources"].append(rendered)
        return groups

    def _ranked_recommendations(self, ranked: list[RankedEvidence], solution: dict[str, Any]) -> list[dict[str, Any]]:
        recommendations = [
            {
                "recommendation": solution["recommended_approach"],
                "confidence_score": ranked[0].confidence_score if ranked else 45,
                "supporting_sources": [item.document.source_url for item in ranked[:5]],
                "reasoning": solution["why_this_approach"],
            }
        ]
        for step in solution.get("implementation_steps", [])[:5]:
            recommendations.append(
                {
                    "recommendation": step,
                    "confidence_score": ranked[0].confidence_score if ranked else 45,
                    "supporting_sources": [item.document.source_url for item in ranked[:3]],
                    "reasoning": "Included because it is necessary to operationalize the recommended approach.",
                }
            )
        return recommendations

    def _source_item(self, item: RankedEvidence) -> dict[str, Any]:
        document = item.document
        return {
            "title": document.title,
            "url": document.source_url,
            "source_type": document.source_type,
            "publisher": document.metadata.get("publisher") or document.source_name,
            "date": document.publication_date or "",
            "confidence_score": item.confidence_score,
            "citation_count": document.metadata.get("citation_count"),
            "evidence_snippet": self._snippet(document.text),
            "why_relevant": item.why_relevant,
        }

    def _snippet(self, text: str) -> str:
        sentences = sentence_split(text)
        if sentences:
            return sentences[0][:420]
        return text[:420]
