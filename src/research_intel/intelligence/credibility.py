from __future__ import annotations

from datetime import date
from urllib.parse import urlparse

from research_intel.ingestion.base import RawDocument
from research_intel.schemas import ClaimCreate
from research_intel.utils import parse_year


TIER_1_HOSTS = (
    "arxiv.org",
    "semanticscholar.org",
    "openalex.org",
    "research.google",
    "deepmind.google",
    "anthropic.com",
    "ai.meta.com",
    "aclanthology.org",
)
TIER_2_HOSTS = (
    "langchain.com",
    "llamaindex.ai",
    "pinecone.io",
    "weaviate.io",
    "qdrant.tech",
    "huggingface.co",
    "github.com",
)
LOW_AUTHORITY_HOSTS = ("medium.com", "towardsdatascience.com", "substack.com")


class CredibilityScorer:
    def score(self, document: RawDocument, claims: list[ClaimCreate]) -> float:
        return self.score_with_breakdown(document, claims)["credibility_score"]

    def score_with_breakdown(self, document: RawDocument, claims: list[ClaimCreate]) -> dict:
        source = self._source_authority(document)
        evidence = self._evidence_strength(claims)
        transparency = self._method_transparency(document, claims)
        recency = self._recency_relevance(document)
        validation = self._external_validation(document)
        score = round(min(100, source + evidence + transparency + recency + validation), 2)
        return {
            "credibility_score": score,
            "source_authority": round(source, 2),
            "evidence_strength": round(evidence, 2),
            "methodological_transparency": round(transparency, 2),
            "recency_relevance": round(recency, 2),
            "external_validation": round(validation, 2),
            "rationale": self._rationale(score, document, claims),
        }

    def _rationale(self, score: float, document: RawDocument, claims: list[ClaimCreate]) -> str:
        if not claims:
            return "No supported claims were extracted; use only as background."
        if score >= 80:
            return "Strong source and evidence profile with enough structure for recommendations."
        if score >= 60:
            return "Usable with caveats; corroborate important claims with independent sources."
        return "Background-only source due to weak authority, evidence, or validation."

    def _source_authority(self, document: RawDocument) -> float:
        host = urlparse(document.source_url).netloc.lower()
        if any(tier in host for tier in TIER_1_HOSTS) or document.source_type == "academic":
            return 23
        if any(tier in host for tier in TIER_2_HOSTS) or document.source_type in {"industry", "code"}:
            return 14
        if document.source_type == "news":
            return 12
        if any(low in host for low in LOW_AUTHORITY_HOSTS):
            return 5
        if document.source_type == "vendor":
            return 7
        return 8

    def _evidence_strength(self, claims: list[ClaimCreate]) -> float:
        if not claims:
            return 0
        weights = {
            "experiment": 29,
            "benchmark": 27,
            "case_study": 18,
            "theoretical": 10,
            "anecdotal": 4,
        }
        values = [weights.get(claim.evidence_type, 5) * claim.confidence for claim in claims]
        return min(30, sum(values) / len(values))

    def _method_transparency(self, document: RawDocument, claims: list[ClaimCreate]) -> float:
        text = f"{document.title}\n{document.text}".lower()
        score = 0.0
        if any(term in text for term in ("dataset", "benchmark", "evaluation", "experiment")):
            score += 5
        if any(term in text for term in ("metric", "accuracy", "recall", "precision", "f1", "latency")):
            score += 4
        if any(term in text for term in ("code", "github", "reproducible", "appendix")):
            score += 3
        if any(claim.metrics for claim in claims):
            score += 3
        return min(15, score)

    def _recency_relevance(self, document: RawDocument) -> float:
        year = parse_year(document.publication_date or "") or document.metadata.get("year")
        current_year = date.today().year
        if not year:
            return 6
        age = current_year - int(year)
        if age <= 1:
            return 15
        if age <= 3:
            return 12
        if age <= 6:
            return 8
        return 4

    def _external_validation(self, document: RawDocument) -> float:
        citations = (
            document.metadata.get("citation_count")
            or document.metadata.get("cited_by_count")
            or document.metadata.get("citations")
            or 0
        )
        try:
            citation_count = int(citations)
        except (TypeError, ValueError):
            citation_count = 0
        if citation_count >= 100:
            return 15
        if citation_count >= 20:
            return 13
        if citation_count >= 5:
            return 10
        if document.source_type in {"industry", "news"}:
            return 7
        return 5


def usage_bucket(score: float) -> str:
    if score < 60:
        return "background_only"
    if score < 80:
        return "usable_with_caveats"
    return "strong_recommendation_candidate"
