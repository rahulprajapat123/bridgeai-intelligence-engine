from __future__ import annotations

import time
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy.orm import Session

from research_intel.config import Settings
from research_intel.intelligence.retrieval import RetrievalService
from research_intel.models import QueryLog
from research_intel.schemas import (
    EvidenceItem,
    ImplementationNotes,
    InsufficientEvidence,
    ProjectContext,
    ProjectContextInput,
    RecommendationContract,
    RecommendationCore,
    RecommendationResponse,
)
from research_intel.utils import stable_id


class RecommendationService:
    def __init__(self, settings: Settings, retrieval: RetrievalService) -> None:
        self.settings = settings
        self.retrieval = retrieval

    def recommend(
        self,
        session: Session,
        context_input: ProjectContextInput,
        *,
        top_k: int = 12,
        min_credibility: float = 60,
    ) -> RecommendationResponse:
        started = time.perf_counter()
        query_id = stable_id("query", datetime.now(UTC).isoformat(), str(context_input.model_dump()))
        missing = context_input.missing_fields()
        if missing:
            response = self._insufficient(
                query_id,
                started,
                reason="Project context is incomplete. Strict intake requires every core field.",
                missing_fields=missing,
            )
            self._log(session, query_id, context_input.model_dump(), response, started, "insufficient_evidence")
            return response

        try:
            context = ProjectContext(**context_input.model_dump())
        except ValidationError as exc:
            response = self._insufficient(
                query_id,
                started,
                reason=f"Project context failed validation: {exc.errors()[0]['msg']}",
            )
            self._log(session, query_id, context_input.model_dump(), response, started, "insufficient_evidence")
            return response

        query = self._query_from_context(context)
        claims = self.retrieval.search(
            session,
            query,
            domain=context.domain,
            top_k=top_k,
            min_credibility=min_credibility,
        )
        evidence_claims = [claim for claim in claims if claim.credibility_score >= min_credibility]
        if not evidence_claims:
            response = self._insufficient(
                query_id,
                started,
                reason="No evidence above the configured credibility threshold was found.",
                searched_query=query,
                top_evidence_count=len(claims),
            )
            self._log(session, query_id, context.model_dump(), response, started, "insufficient_evidence")
            return response

        try:
            contract = self._build_contract(context, evidence_claims)
        except ValidationError as exc:
            response = self._insufficient(
                query_id,
                started,
                reason=f"Recommendation schema could not be filled completely: {exc.errors()[0]['msg']}",
                searched_query=query,
                top_evidence_count=len(evidence_claims),
            )
            self._log(session, query_id, context.model_dump(), response, started, "insufficient_evidence")
            return response

        latency_ms = int((time.perf_counter() - started) * 1000)
        response = RecommendationResponse(
            status="ok",
            query_id=query_id,
            latency_ms=latency_ms,
            data=contract,
        )
        self._log(session, query_id, context.model_dump(), response, started, "ok")
        return response

    def _build_contract(self, context: ProjectContext, claims) -> RecommendationContract:
        primary = claims[0]
        apply_items = self._apply_recommendations(context, claims)
        avoid_items = self._avoid_recommendations(context, claims)
        if not apply_items:
            apply_items = [
                RecommendationCore(
                    technique=f"Use evidence-backed {context.domain} retrieval with validation gates",
                    why_it_works=primary.claim_text,
                    expected_benefit="Improves decision quality by grounding recommendations in cited sources.",
                    tradeoffs="Requires source hygiene, claim extraction, and periodic review.",
                )
            ]
        evidence = [
            EvidenceItem(
                source=claim.source,
                source_url=claim.source_url,
                title=claim.title,
                credibility_score=claim.credibility_score,
                key_findings=claim.claim_text,
                evidence_snippet=claim.evidence_summary or claim.claim_text[:240],
                evidence_location=claim.evidence_location,
                citation_count=None,
                date=claim.publication_date,
                claim_id=claim.claim_id,
            )
            for claim in claims[:8]
        ]
        average_credibility = sum(claim.credibility_score for claim in claims[:5]) / min(5, len(claims))
        confidence = "high" if average_credibility >= 80 else "medium" if average_credibility >= 60 else "low"
        tooling = self._tooling(context)
        return RecommendationContract(
            generated_at=datetime.now(UTC).isoformat(),
            system_version=self.settings.system_version,
            project_context=context.model_dump(),
            recommendation=apply_items[0],
            techniques_to_apply=apply_items,
            techniques_to_avoid=avoid_items,
            tooling_suggestions=tooling,
            explicit_tradeoffs=self._tradeoffs(context),
            evidence=evidence,
            implementation_notes=ImplementationNotes(
                complexity=self._complexity(context),
                tooling_options=tooling,
                gotchas=self._gotchas(context, claims),
            ),
            confidence_level=confidence,
        )

    def _apply_recommendations(self, context: ProjectContext, claims) -> list[RecommendationCore]:
        text = " ".join(claim.claim_text.lower() for claim in claims[:8])
        recommendations: list[RecommendationCore] = []
        if any(term in text for term in ("hybrid", "bm25", "sparse", "dense")) or context.problem_type in {
            "QA",
            "search",
        }:
            recommendations.append(
                RecommendationCore(
                    technique="Hybrid retrieval with metadata filters and evidence-weighted reranking",
                    why_it_works=self._cite_summary(claims, ("retrieval", "reranking", "evaluation")),
                    expected_benefit="Better recall than single-channel search while preserving precision through reranking.",
                    tradeoffs="Adds index complexity and needs tuning for latency-sensitive workloads.",
                )
            )
        if context.data_modality == "PDFs":
            recommendations.append(
                RecommendationCore(
                    technique="Document-aware chunking with section, page, and citation metadata",
                    why_it_works=self._cite_summary(claims, ("chunking", "source_quality", "retrieval")),
                    expected_benefit="Improves traceability from answer to source section and reduces unsupported synthesis.",
                    tradeoffs="Requires PDF parsing quality checks and fallback handling for bad extractions.",
                )
            )
        if context.domain.lower() in {"partner programs", "competitive intelligence", "market research"}:
            recommendations.append(
                RecommendationCore(
                    technique="Domain-aware source routing before retrieval",
                    why_it_works=self._cite_summary(claims, ("business_research", "source_quality")),
                    expected_benefit="Prevents unrelated AI/RAG resources from crowding out business research evidence.",
                    tradeoffs="Requires maintaining a source taxonomy and reviewing low-confidence routes.",
                )
            )
        if context.accuracy_cost_tradeoff == "accuracy_first":
            recommendations.append(
                RecommendationCore(
                    technique="Cross-encoder or LLM reranking on the top retrieval set",
                    why_it_works=self._cite_summary(claims, ("reranking", "evaluation")),
                    expected_benefit="Improves final evidence ordering for high-precision decisions.",
                    tradeoffs="Increases per-query cost and latency; apply after cheap first-stage retrieval.",
                )
            )
        return recommendations[:4]

    def _avoid_recommendations(self, context: ProjectContext, claims) -> list[RecommendationCore]:
        evidence = [claim for claim in claims if claim.limitations or "risk" in claim.claim_text.lower()]
        source = evidence[0] if evidence else claims[0]
        avoid = [
            RecommendationCore(
                technique="Pure keyword overlap or single dense retrieval without reranking",
                why_it_works=source.claim_text,
                expected_benefit="Avoids high-scoring but irrelevant evidence caused by isolated keyword matches.",
                tradeoffs="A hybrid/reranked pipeline is more complex than a single retriever.",
            )
        ]
        if context.domain.lower() not in {"ai/ml", "ai_ml"}:
            avoid.append(
                RecommendationCore(
                    technique="Defaulting every brief to AI/RAG source pools",
                    why_it_works="The retrieved evidence must match the classified domain, not incidental vendor or model names.",
                    expected_benefit="Improves relevance for business, market, legal, healthcare, and finance briefs.",
                    tradeoffs="Source routing must be audited as new domains are added.",
                )
            )
        return avoid[:2]

    def _cite_summary(self, claims, preferred_tags: tuple[str, ...]) -> str:
        for claim in claims:
            if set(preferred_tags) & set(claim.applicability_tags):
                return claim.claim_text
        return claims[0].claim_text

    def _tooling(self, context: ProjectContext) -> list[str]:
        tools = ["FastAPI", "Postgres/Neon", "SQLAlchemy", "OpenAlex", "Semantic Scholar"]
        if context.deployment_env == "GCP":
            tools.extend(["Cloud Scheduler", "Cloud Run", "BigQuery or Vertex AI RAG API adapter"])
        if context.accuracy_cost_tradeoff == "accuracy_first":
            tools.append("Cross-encoder reranker or OpenAI reranking prompt")
        if context.domain.lower() in {"partner programs", "competitive intelligence", "market research"}:
            tools.extend(["Serper/Exa/Tavily", "NewsAPI/GNews", "Firecrawl"])
        return list(dict.fromkeys(tools))

    def _tradeoffs(self, context: ProjectContext) -> list[str]:
        tradeoffs = [
            "Higher evidence quality requires stricter source filtering and more manual review early on.",
            "Reranking improves precision but adds latency and API cost.",
        ]
        if context.accuracy_cost_tradeoff == "cost_first":
            tradeoffs.append("Cost-first mode should lower top-k and prefer cached embeddings over LLM reranking.")
        if context.latency_constraint.startswith("<"):
            tradeoffs.append("Sub-second latency may require precomputed recommendations or smaller candidate pools.")
        return tradeoffs

    def _gotchas(self, context: ProjectContext, claims) -> list[str]:
        gotchas = [
            "Do not output recommendations below credibility score 60 except as background.",
            "Every recommendation must trace to a claim, source URL, and evidence snippet.",
        ]
        if context.data_modality == "PDFs":
            gotchas.append("PDF parsing failures should be queued for manual review instead of silently dropped.")
        if any(claim.credibility_score < 80 for claim in claims[:3]):
            gotchas.append("Top evidence is usable with caveats; keep confidence below high unless validated.")
        return gotchas

    def _complexity(self, context: ProjectContext) -> str:
        if context.accuracy_cost_tradeoff == "accuracy_first" or context.corpus_scale.lower().endswith("m"):
            return "high"
        if context.problem_type in {"agentic", "QA"}:
            return "medium"
        return "low"

    def _query_from_context(self, context: ProjectContext) -> str:
        constraints = " ".join(f"{key}:{value}" for key, value in context.extra_constraints.items())
        return (
            f"{context.domain} {context.problem_type} {context.data_modality} "
            f"{context.corpus_scale} {context.latency_constraint} "
            f"{context.accuracy_cost_tradeoff} {context.deployment_env} {constraints}"
        )

    def _insufficient(
        self,
        query_id: str,
        started: float,
        *,
        reason: str,
        missing_fields: list[str] | None = None,
        searched_query: str | None = None,
        top_evidence_count: int = 0,
    ) -> RecommendationResponse:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return RecommendationResponse(
            status="insufficient_evidence",
            query_id=query_id,
            latency_ms=latency_ms,
            data=InsufficientEvidence(
                generated_at=datetime.now(UTC).isoformat(),
                system_version=self.settings.system_version,
                reason=reason,
                missing_fields=missing_fields or [],
                searched_query=searched_query,
                top_evidence_count=top_evidence_count,
            ),
        )

    def _log(
        self,
        session: Session,
        query_id: str,
        context: dict,
        response: RecommendationResponse,
        started: float,
        status: str,
    ) -> None:
        latency_ms = int((time.perf_counter() - started) * 1000)
        session.merge(
            QueryLog(
                query_id=query_id,
                project_context=context,
                response=response.model_dump(mode="json"),
                latency_ms=latency_ms,
                status=status,
            )
        )
        session.commit()

