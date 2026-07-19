"""Adapters connecting existing services to signal filter protocols."""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from research_intel.intelligence.embeddings import EmbeddingService
from research_intel.models import HistoricalSignal, now_utc
from research_intel.signal_filter.models import (
    CriterionScore,
    SignalItem,
    SignalScores,
    SourceType,
)
from research_intel.signal_filter.providers import (
    EmbeddingProvider,
    HistoricalRepository,
    IntelligenceProvider,
)

if TYPE_CHECKING:
    from research_intel.config import Settings
    from research_intel.signal_filter.models import FilterRunResult


class EmbeddingServiceAdapter:
    """Adapts existing EmbeddingService to filter's EmbeddingProvider protocol."""

    def __init__(self, service: EmbeddingService):
        self.service = service
        self.model_version = (
            "text-embedding-3-small" if service._client else f"hash-{service.dimension}"
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Batch embed texts using the underlying service."""
        if not texts:
            return []
        # Use the batch_embed method for efficiency
        return self.service.batch_embed(texts)


class DatabaseHistoricalRepository:
    """Database-backed historical repository for novelty scoring."""

    def __init__(self, session: Session):
        self.session = session

    async def find_recent_items(
        self, days: int, domain: str | None = None
    ) -> list[SignalItem]:
        """Find recent historical items for novelty comparison."""
        cutoff = datetime.now(UTC) - timedelta(days=days)

        query = self.session.query(HistoricalSignal).filter(
            HistoricalSignal.published_at >= cutoff
        )

        if domain:
            query = query.filter(HistoricalSignal.domain == domain)

        results = query.order_by(HistoricalSignal.published_at.desc()).limit(1000).all()

        # Convert to SignalItems
        items = []
        for row in results:
            item = SignalItem(
                item_id=row.item_id,
                title=row.title,
                body="",
                metadata={
                    "source_url": "",
                    "source_type": row.source_type or "other",
                    "domain": row.domain,
                    "published_at": row.published_at,
                    "retrieved_at": row.created_at,
                },
            )
            item.content_fingerprint = row.content_fingerprint
            item.normalized_text = row.normalized_text
            items.append(item)

        return items

    async def save_run(self, result: FilterRunResult) -> None:
        """Save accepted items to historical storage."""
        from uuid import uuid4

        for item in result.items:
            if item.status in ("accepted", "qualified_but_cut_for_volume"):
                signal = HistoricalSignal(
                    id=str(uuid4()),
                    batch_id=result.run_id,
                    item_id=item.item_id,
                    content_fingerprint=item.content_fingerprint,
                    title=item.title,
                    normalized_text=item.normalized_text or "",
                    source_type=(
                        item.metadata.source_type.value
                        if hasattr(item.metadata.source_type, "value")
                        else str(item.metadata.source_type)
                    ),
                    published_at=item.metadata.published_at,
                    domain=item.metadata.domain,
                    created_at=now_utc(),
                )
                self.session.add(signal)

        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise


class OpenAIIntelligenceAdapter:
    """OpenAI-based intelligence provider for scoring and generation."""

    def __init__(self, settings: Settings):
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model_version = "gpt-4o-mini"

    async def extract(self, item: SignalItem) -> SignalItem:
        """Extract claims and metadata (simplified for now)."""
        # Basic claim extraction from sentences with factual content
        from research_intel.signal_filter.models import ExtractedClaim

        sentences = re.split(r"(?<=[.!?])\s+", item.body)
        item.claims = [
            ExtractedClaim(
                claim_id=f"{item.item_id}-c{i}",
                claim_text=s,
                evidence_text=s,
                confidence=0.60,
                claim_type="factual",
                verifiability="unknown",
                support_status="supported",
            )
            for i, s in enumerate(sentences[:5], 1)
            if len(s) > 30
            and re.search(
                r"\d|\b(announced|released|reported|increased|decreased|launched)\b",
                s,
                re.I,
            )
        ]

        return item

    async def score_and_generate(
        self, item: SignalItem
    ) -> tuple[SignalScores, dict[str, str]]:
        """Score item and generate output fields using OpenAI."""
        prompt = f"""Score this content on 5 criteria (0-5 scale) and generate concise summaries:

Title: {item.title}
Body: {item.body[:1500]}

Return JSON with this exact structure:
{{
  "scores": {{
    "business_relevance": {{"score": 0-5, "confidence": 0.0-1.0, "rationale": "Brief reason", "evidence": ["key quote"]}},
    "actionability": {{"score": 0-5, "confidence": 0.0-1.0, "rationale": "Brief reason", "evidence": ["key quote"]}},
    "novelty": {{"score": 0-5, "confidence": 0.0-1.0, "rationale": "Brief reason", "evidence": ["key quote"]}},
    "credibility": {{"score": 0-5, "confidence": 0.0-1.0, "rationale": "Brief reason", "evidence": ["key quote"]}},
    "momentum": {{"score": 0-5, "confidence": 0.0-1.0, "rationale": "Brief reason", "evidence": ["key quote"]}}
  }},
  "why_it_matters": "2-3 specific sentences explaining concrete business impact",
  "the_move": "1-2 actionable sentences with specific next steps",
  "recommended_action": "1 clear sentence with what to do"
}}

Criteria definitions:
- business_relevance: Has concrete workflow, product, or revenue implications (not just interesting)
- actionability: Has clear, specific next steps teams can take
- novelty: Not widely known yet; represents new information or shift
- credibility: From authoritative sources with verifiable evidence
- momentum: Showing traction, adoption, or increasing attention"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model_version,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.3,
            )

            data = json.loads(response.choices[0].message.content)

            # Build SignalScores
            scores_data = data["scores"]
            scores = SignalScores(
                business_relevance=CriterionScore(**scores_data["business_relevance"]),
                actionability=CriterionScore(**scores_data["actionability"]),
                novelty=CriterionScore(**scores_data["novelty"]),
                credibility=CriterionScore(**scores_data["credibility"]),
                momentum=CriterionScore(**scores_data["momentum"]),
            )

            generated = {
                "why_it_matters": data.get("why_it_matters", ""),
                "the_move": data.get("the_move", ""),
                "recommended_action": data.get("recommended_action", ""),
            }

            return scores, generated

        except Exception as e:
            # Fallback to heuristic scoring
            from research_intel.signal_filter.models import CriterionScore

            text = item.normalized_text or ""
            evidence = (
                item.claims[0].evidence_text if item.claims else item.title[:200]
            )

            concrete = sum(
                term in text
                for term in (
                    "launch",
                    "release",
                    "cost",
                    "customer",
                    "workflow",
                    "benchmark",
                    "revenue",
                    "adoption",
                    "security",
                )
            )
            authority = (
                2
                + bool(item.metadata.author)
                + bool(item.canonical_url)
                + bool(item.claims)
            )

            def c(score, rationale, conf=0.58):
                return CriterionScore(
                    score=min(5, score),
                    confidence=conf,
                    rationale=f"{rationale} (Fallback: {str(e)[:50]})",
                    evidence=[evidence] if evidence else [],
                )

            scores = SignalScores(
                business_relevance=c(
                    2 + min(3, concrete), "Business/workflow terms found."
                ),
                actionability=c(2 + min(3, concrete), "Concrete change signals found."),
                novelty=c(
                    3 if item.event_cluster_id else 2, "Event clustering applied."
                ),
                credibility=c(authority, "Metadata and evidence assessed."),
                momentum=c(1, "Limited momentum data.", 0.30),
            )

            generated = {
                "why_it_matters": f"{item.title} represents a development in the AI space.",
                "the_move": "Monitor this development and assess potential impact.",
                "recommended_action": "Review and evaluate for relevance to your context.",
            }

            return scores, generated

    async def regenerate_field(
        self,
        item: SignalItem,
        field: str,
        failure_reason: str,
        forbidden_phrases: list[str],
    ) -> str:
        """Regenerate a specific field that failed QA."""
        prompt = f"""Regenerate the '{field}' field for this content.

Previous attempt was rejected: {failure_reason}
AVOID these generic phrases: {', '.join(forbidden_phrases[:5])}

Title: {item.title}
Body: {item.body[:1000]}

Requirements:
- Be specific and concrete (no generic statements)
- Include actionable details
- 2-3 sentences maximum
- Focus on practical business implications

Return ONLY the new {field} text, nothing else."""

        try:
            response = await self.client.chat.completions.create(
                model=self.model_version,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.5,
            )

            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"Unable to regenerate: {str(e)[:100]}"
