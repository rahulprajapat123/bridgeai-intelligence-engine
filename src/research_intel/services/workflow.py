from __future__ import annotations

from datetime import UTC, datetime

from fastapi import UploadFile
from sqlalchemy.orm import Session

from research_intel.ingestion.base import RawDocument
from research_intel.models import UploadedBrief
from research_intel.schemas import (
    BriefUploadResponse,
    EvidenceItem,
    OnePageBrief,
    OnePageRecommendation,
    RecommendedToolOrMethod,
    TechnologyRecommendation,
    WorkflowAnalyzeResponse,
)
from research_intel.services.factory import AppServices
from research_intel.services.file_parser import BriefFileParser
from research_intel.utils import stable_id, text_hash, tokenize


TECHNOLOGY_KEYWORDS: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "Hybrid Search": ("Retrieval", "Use BM25/sparse plus dense retrieval when terminology and semantics both matter.", ("hybrid", "bm25", "sparse", "dense")),
    "Vector Database": ("Storage", "Use a vector index with metadata filters for scalable semantic retrieval.", ("vector", "embedding", "index", "metadata")),
    "Cross-Encoder Reranking": ("Ranking", "Rerank the top retrieval candidates when precision matters more than raw speed.", ("rerank", "cross-encoder", "precision")),
    "Document-Aware Chunking": ("Ingestion", "Preserve sections, pages, headings, and citations during chunking.", ("chunk", "pdf", "section", "page")),
    "Semantic Web Search": ("Source Discovery", "Route open-web discovery through semantic search APIs for domain-specific evidence.", ("exa", "tavily", "serper", "web", "semantic")),
    "GitHub Repository Intelligence": ("Developer Sources", "Track repositories, stars, topics, and README evidence for tooling recommendations.", ("github", "repository", "stars", "sdk")),
    "News Intelligence": ("Market Sources", "Use news APIs for current ecosystem, vendor, and market signal tracking.", ("news", "article", "market", "trend")),
    "Domain-Aware Routing": ("Brief Understanding", "Classify the brief before retrieval so source pools match the business or technical intent.", ("domain", "partner", "competitive", "market", "legal")),
}


class WorkflowService:
    def __init__(self, services: AppServices) -> None:
        self.services = services
        self.parser = BriefFileParser()

    async def upload_brief(self, session: Session, file: UploadFile) -> BriefUploadResponse:
        content = await file.read()
        text = self.parser.parse(file.filename or "brief.txt", content)
        if len(text.strip()) < 20:
            raise ValueError("Uploaded brief did not contain enough readable text.")
        analysis = self.services.brief.analyze(text)
        brief_id = stable_id("brief", file.filename or "", text_hash(text), datetime.now(UTC).isoformat())
        session.add(
            UploadedBrief(
                brief_id=brief_id,
                filename=file.filename or "uploaded-brief",
                content_type=file.content_type or "",
                text_hash=text_hash(text),
                extracted_text=text,
                analysis=analysis.model_dump(mode="json"),
                metadata_json={"size_bytes": len(content)},
            )
        )
        session.commit()
        return BriefUploadResponse(
            brief_id=brief_id,
            filename=file.filename or "uploaded-brief",
            content_type=file.content_type or "",
            text_length=len(text),
            analysis=analysis,
        )

    async def analyze_workflow(
        self,
        session: Session,
        *,
        brief_id: str | None,
        text: str | None,
        auto_fetch: bool,
        max_per_source: int,
        top_k: int,
        min_credibility: float = 60,
    ) -> WorkflowAnalyzeResponse:
        source_text = text
        loaded_brief_id = brief_id
        if brief_id:
            brief = session.get(UploadedBrief, brief_id)
            if brief is None:
                raise ValueError("Brief ID was not found.")
            source_text = brief.extracted_text
        assert source_text is not None
        analysis = self.services.brief.analyze(source_text)
        topic = " ".join(analysis.query_decomposition[:3] or analysis.keywords[:8] or [analysis.intent])
        fetched = None
        if auto_fetch:
            # Limit to 5 items per source to prevent connection timeouts
            limited_max = min(max_per_source, 5)
            fetched = await self.services.ingestion.ingest_topic(
                session,
                topic=topic,
                domain=analysis.domain.domain,
                max_per_source=limited_max,
            )

        query = " ".join(analysis.query_decomposition + analysis.keywords + [analysis.intent])
        claims = self.services.retrieval.search(
            session,
            query,
            domain=analysis.domain.domain,
            top_k=top_k,
            min_credibility=min_credibility,
        )
        citations = [
            EvidenceItem(
                source=claim.source,
                source_url=claim.source_url,
                title=claim.title,
                credibility_score=claim.credibility_score,
                key_findings=claim.claim_text,
                evidence_snippet=claim.evidence_summary or claim.claim_text[:240],
                evidence_location=claim.evidence_location,
                date=claim.publication_date,
                claim_id=claim.claim_id,
            )
            for claim in claims
        ]
        recommendations = self._technology_recommendations(source_text, analysis.domain.domain, claims)
        one_page = self._one_page_brief(source_text, analysis, recommendations, citations)
        return WorkflowAnalyzeResponse(
            brief_id=loaded_brief_id,
            analysis=analysis,
            fetched_sources=fetched,
            recommendations=recommendations,
            citations=citations,
            one_page_brief=one_page,
            insufficient_evidence=not bool(citations) or not bool(recommendations),
        )

    def _technology_recommendations(
        self,
        brief_text: str,
        domain: str,
        claims,
    ) -> list[TechnologyRecommendation]:
        text_terms = set(tokenize(f"{brief_text} {domain}"))
        claim_text = " ".join(claim.claim_text for claim in claims).lower()
        output: list[TechnologyRecommendation] = []
        for technology, (category, guidance, keywords) in TECHNOLOGY_KEYWORDS.items():
            keyword_hits = len(text_terms & set(keywords))
            evidence_hits = sum(1 for keyword in keywords if keyword in claim_text)
            if keyword_hits == 0 and evidence_hits == 0:
                continue
            relevant_claims = [
                claim
                for claim in claims
                if any(keyword in claim.claim_text.lower() for keyword in keywords)
            ][:3]
            evidence = [
                EvidenceItem(
                    source=claim.source,
                    source_url=claim.source_url,
                    title=claim.title,
                    credibility_score=claim.credibility_score,
                    key_findings=claim.claim_text,
                    evidence_snippet=claim.evidence_summary or claim.claim_text[:240],
                    evidence_location=claim.evidence_location,
                    date=claim.publication_date,
                    claim_id=claim.claim_id,
                )
                for claim in relevant_claims
            ]
            if not evidence:
                continue
            score = min(1.0, 0.18 * keyword_hits + 0.16 * evidence_hits + 0.12)
            output.append(
                TechnologyRecommendation(
                    technology_name=technology,
                    category=category,
                    relevance_score=round(score, 3),
                    supporting_evidence=evidence,
                    source_links=[item.source_url for item in evidence],
                    implementation_guidance=guidance,
                )
            )

        if not output and claims:
            top = claims[0]
            output.append(
                TechnologyRecommendation(
                    technology_name="Evidence-Backed Retrieval Workflow",
                    category="Research Intelligence",
                    relevance_score=min(1.0, top.relevance_score / 100),
                    supporting_evidence=[
                        EvidenceItem(
                            source=top.source,
                            source_url=top.source_url,
                            title=top.title,
                            credibility_score=top.credibility_score,
                            key_findings=top.claim_text,
                            evidence_snippet=top.evidence_summary or top.claim_text[:240],
                            evidence_location=top.evidence_location,
                            date=top.publication_date,
                            claim_id=top.claim_id,
                        )
                    ],
                    source_links=[top.source_url],
                    implementation_guidance="Use the retrieved evidence as the first ranked source set, then validate citations before implementation.",
                )
            )
        output.sort(key=lambda item: item.relevance_score, reverse=True)
        return output[:8]

    def _one_page_brief(
        self,
        brief_text: str,
        analysis,
        recommendations: list[TechnologyRecommendation],
        citations: list[EvidenceItem],
    ) -> OnePageBrief:
        insufficient = []
        if not citations:
            insufficient.append("No retrieved claims met the credibility threshold.")
        if not recommendations:
            insufficient.append("No recommendation has traceable supporting evidence.")

        top_recommendations = [
            OnePageRecommendation(
                point=item.technology_name,
                why_it_matters=item.implementation_guidance,
                supporting_evidence=[evidence.key_findings for evidence in item.supporting_evidence[:2]],
                citations=[evidence.source_url for evidence in item.supporting_evidence[:3]],
                confidence=self._confidence(item.supporting_evidence),
            )
            for item in recommendations[:5]
            if item.supporting_evidence
        ]
        tools_or_methods = [
            RecommendedToolOrMethod(
                name=item.technology_name,
                category=item.category,
                fit_reason=item.implementation_guidance,
                tradeoffs="Validate against the cited evidence and mark vendor-only claims as caveated.",
                citations=[evidence.source_url for evidence in item.supporting_evidence[:3]],
            )
            for item in recommendations[:5]
            if item.supporting_evidence
        ]
        next_steps = [
            "Review the cited source set for conflicts and outdated claims.",
            "Validate assumptions, dependencies, and unavailable client data before final delivery.",
        ]
        if analysis.source_route_plan:
            next_steps.insert(0, f"Run the highest-priority route: {analysis.source_route_plan[0].query}")
        return OnePageBrief(
            generated_at=datetime.now(UTC).isoformat(),
            brief_summary=analysis.objective or brief_text[:300],
            domain=analysis.primary_domain,
            client_need=analysis.intent,
            top_recommendations=top_recommendations,
            recommended_tools_or_methods=tools_or_methods,
            risks_and_limitations=analysis.risks[:6],
            dependencies=analysis.dependencies[:6],
            suggested_next_steps=next_steps,
            insufficient_evidence_items=insufficient,
        )

    def _confidence(self, evidence: list[EvidenceItem]) -> str:
        if not evidence:
            return "low"
        avg = sum(item.credibility_score for item in evidence) / len(evidence)
        if avg >= 80 and len(evidence) >= 2:
            return "high"
        if avg >= 60:
            return "medium"
        return "low"


def raw_document_from_brief(filename: str, text: str, domain: str) -> RawDocument:
    return RawDocument(
        title=filename,
        source_url=f"uploaded://{stable_id('brief-doc', filename, text_hash(text))}",
        source_type="web",
        source_name="Uploaded Brief",
        text=text,
        metadata={"domain": domain},
    )
