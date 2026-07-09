from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlparse

from research_intel.ingestion.base import RawDocument
from research_intel.intelligence.credibility import CredibilityScorer
from research_intel.utils import parse_year, tokenize


@dataclass(slots=True)
class RankedEvidence:
    document: RawDocument
    confidence_score: float
    relevance_score: float
    usefulness_score: float
    why_relevant: str


class EvidenceRanker:
    def __init__(self, scorer: CredibilityScorer) -> None:
        self.scorer = scorer

    def rank(self, documents: list[RawDocument], brief_text: str, queries: list[str], domain: str) -> list[RankedEvidence]:
        brief_terms = set(tokenize(" ".join([brief_text, *queries, domain])))
        ranked = [self._score(document, brief_terms, domain) for document in documents]
        ranked.sort(key=lambda item: item.confidence_score, reverse=True)
        return ranked

    def _score(self, document: RawDocument, brief_terms: set[str], domain: str) -> RankedEvidence:
        text = f"{document.title} {document.text}".lower()
        doc_terms = set(tokenize(text))
        overlap = len(brief_terms & doc_terms)
        keyword_relevance = min(35.0, overlap * 2.2)
        domain_relevance = 15.0 if domain.lower() in text else 8.0
        source_authority = self.scorer.score_with_breakdown(document, [])["source_authority"]
        freshness = self._freshness(document)
        citations = self._citation_score(document)
        github_signal = self._github_score(document)
        usefulness = self._usefulness(text)
        confidence = min(
            100.0,
            keyword_relevance
            + domain_relevance
            + source_authority
            + freshness
            + citations
            + github_signal
            + usefulness,
        )
        why = self._why_relevant(document, overlap, usefulness, source_authority)
        return RankedEvidence(
            document=document,
            confidence_score=round(confidence, 2),
            relevance_score=round(keyword_relevance + domain_relevance, 2),
            usefulness_score=round(usefulness, 2),
            why_relevant=why,
        )

    def _freshness(self, document: RawDocument) -> float:
        year = parse_year(document.publication_date or "") or document.metadata.get("year")
        if not year:
            return 5.0
        age = max(0, date.today().year - int(year))
        if age <= 1:
            return 10.0
        if age <= 3:
            return 8.0
        if age <= 6:
            return 5.0
        return 2.0

    def _citation_score(self, document: RawDocument) -> float:
        raw = document.metadata.get("citation_count") or document.metadata.get("cited_by_count") or 0
        try:
            count = max(0, int(raw))
        except (TypeError, ValueError):
            count = 0
        return min(10.0, math.log10(count + 1) * 4)

    def _github_score(self, document: RawDocument) -> float:
        if "github.com" not in urlparse(document.source_url).netloc.lower():
            return 0.0
        raw = document.metadata.get("stars") or document.metadata.get("citation_count") or 0
        try:
            stars = max(0, int(raw))
        except (TypeError, ValueError):
            stars = 0
        return min(12.0, math.log10(stars + 1) * 4)

    def _usefulness(self, text: str) -> float:
        signals = (
            "implementation",
            "architecture",
            "api",
            "workflow",
            "benchmark",
            "case study",
            "evaluation",
            "cost",
            "risk",
            "guide",
            "repository",
            "documentation",
        )
        return min(14.0, sum(2.0 for signal in signals if signal in text))

    def _why_relevant(self, document: RawDocument, overlap: int, usefulness: float, authority: float) -> str:
        parts = [f"Matches {overlap} brief/search terms"]
        if usefulness >= 6:
            parts.append("contains practical implementation signals")
        if authority >= 14:
            parts.append("comes from a comparatively authoritative source")
        if document.metadata.get("stars"):
            parts.append(f"has {document.metadata['stars']} GitHub stars")
        if document.metadata.get("citation_count"):
            parts.append(f"has {document.metadata['citation_count']} citations or equivalent validation")
        return "; ".join(parts) + "."
