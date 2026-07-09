from __future__ import annotations

import math
from datetime import date

from sqlalchemy.orm import Session, joinedload

from research_intel.intelligence.embeddings import EmbeddingService, cosine_similarity
from research_intel.models import Claim
from research_intel.schemas import RetrievedClaim
from research_intel.utils import date_to_iso, tokenize


class RetrievalService:
    def __init__(self, embeddings: EmbeddingService) -> None:
        self.embeddings = embeddings

    def search(
        self,
        session: Session,
        query: str,
        *,
        domain: str | None = None,
        top_k: int = 10,
        min_credibility: float = 0,
    ) -> list[RetrievedClaim]:
        query_embedding = self.embeddings.embed(query)
        query_terms = set(tokenize(query))
        domain_terms = set(tokenize(domain or ""))
        candidates = (
            session.query(Claim)
            .options(joinedload(Claim.research_item))
            .join(Claim.research_item)
            .filter(Claim.research_item.has())
            .all()
        )
        ranked: list[tuple[float, Claim]] = []
        for claim in candidates:
            item = claim.research_item
            if item.credibility_score < min_credibility:
                continue
            semantic = cosine_similarity(query_embedding, claim.embedding or [])
            lexical = self._lexical_score(query_terms, claim)
            credibility = item.credibility_score / 100
            domain_match = self._domain_score(domain_terms, item.domain_tags or [], claim.applicability_tags or [])
            recency = self._recency_score(item.publication_date)
            cross_encoder = self._heuristic_rerank(query_terms, claim)
            deliverable_match = self._deliverable_score(query_terms, claim)
            source_diversity = self._source_diversity_score(item.source_type)
            score = (
                0.30 * semantic
                + 0.20 * cross_encoder
                + 0.15 * domain_match
                + 0.15 * credibility
                + 0.10 * deliverable_match
                + 0.05 * recency
                + 0.05 * source_diversity
            )
            if lexical == 0 and domain_match == 0 and semantic < 0.2:
                score *= 0.35
            ranked.append((score, claim))
        ranked.sort(key=lambda pair: pair[0], reverse=True)
        return [self._to_schema(claim, score) for score, claim in ranked[:top_k]]

    def _lexical_score(self, query_terms: set[str], claim: Claim) -> float:
        if not query_terms:
            return 0
        claim_terms = set(tokenize(f"{claim.claim_text} {' '.join(claim.applicability_tags or [])}"))
        overlap = len(query_terms & claim_terms)
        return min(1.0, overlap / math.sqrt(len(query_terms)))

    def _domain_score(self, domain_terms: set[str], item_tags: list[str], claim_tags: list[str]) -> float:
        tags = set(tokenize(" ".join(item_tags + claim_tags)))
        if not domain_terms:
            return 0.4 if tags else 0
        if not tags:
            return 0
        return min(1.0, len(domain_terms & tags) / max(1, len(domain_terms)))

    def _recency_score(self, publication_date) -> float:
        if publication_date is None:
            return 0.35
        age = max(0, date.today().year - publication_date.year)
        if age <= 1:
            return 1
        if age <= 3:
            return 0.75
        if age <= 6:
            return 0.45
        return 0.2

    def _heuristic_rerank(self, query_terms: set[str], claim: Claim) -> float:
        text = claim.claim_text.lower()
        score = 0.0
        if claim.evidence_type in {"experiment", "benchmark"}:
            score += 0.35
        if claim.metrics:
            score += 0.2
        if any(tag in query_terms for tag in (claim.applicability_tags or [])):
            score += 0.2
        if any(term in text for term in ("avoid", "failure", "risk", "limitation")):
            score += 0.1
        if self._lexical_score(query_terms, claim) > 0:
            score += 0.25
        return min(1.0, score)

    def _deliverable_score(self, query_terms: set[str], claim: Claim) -> float:
        deliverable_terms = {
            "report",
            "dashboard",
            "ppt",
            "presentation",
            "comparison",
            "matrix",
            "benchmark",
            "recommendation",
            "implementation",
        }
        if not query_terms & deliverable_terms:
            return 0.35
        text = set(tokenize(f"{claim.claim_text} {claim.evidence_summary}"))
        return min(1.0, len((query_terms & deliverable_terms) & text) / 2)

    def _source_diversity_score(self, source_type: str) -> float:
        weights = {
            "academic": 0.9,
            "news": 0.8,
            "code": 0.75,
            "industry": 0.7,
            "vendor": 0.55,
            "blog": 0.45,
            "web": 0.6,
        }
        return weights.get(source_type, 0.5)

    def _to_schema(self, claim: Claim, score: float) -> RetrievedClaim:
        item = claim.research_item
        return RetrievedClaim(
            claim_id=claim.claim_id,
            claim_text=claim.claim_text,
            evidence_type=claim.evidence_type,
            evidence_summary=claim.evidence_summary,
            source=item.source_name,
            source_url=item.source_url,
            title=item.title,
            credibility_score=item.credibility_score,
            confidence=claim.confidence,
            relevance_score=round(score * 100, 2),
            applicability_tags=claim.applicability_tags or [],
            evidence_location=claim.evidence_location,
            metrics=claim.metrics or [],
            limitations=claim.limitations or "",
            publication_date=date_to_iso(item.publication_date),
        )
