from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI
from pydantic import ValidationError

from research_intel.config import Settings
from research_intel.ingestion.base import RawDocument
from research_intel.schemas import ClaimCreate
from research_intel.utils import sentence_split, unique_keep_order


METRIC_RE = re.compile(
    r"(?:(?:\+|\-)?\d+(?:\.\d+)?\s?%|\b\d+(?:\.\d+)?\s?(?:ms|s|x|points?|documents?|queries?)\b)",
    re.I,
)

APPLICABILITY_TERMS = {
    "retrieval": ("retrieval", "retrieve", "bm25", "dense", "hybrid", "sparse"),
    "chunking": ("chunk", "window", "segment"),
    "embedding": ("embedding", "vector", "dense representation"),
    "reranking": ("rerank", "cross-encoder", "re-rank"),
    "generation": ("generation", "prompt", "answer", "llm"),
    "evaluation": ("evaluation", "benchmark", "metric", "precision", "recall", "f1"),
    "business_research": ("competitive", "partner", "market", "sentiment", "benchmarking"),
    "source_quality": ("citation", "evidence", "source", "validated"),
    "healthcare": ("clinical", "patient", "provider", "triage", "diagnosis", "intake"),
}


class ClaimExtractor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: OpenAI | None = None
        if settings.openai_api_key:
            self._client = OpenAI(api_key=settings.openai_api_key)

    def extract(self, document: RawDocument) -> list[ClaimCreate]:
        if self._client and len(document.text) > 500:
            try:
                claims = self._extract_with_llm(document)
                if claims:
                    return claims
            except Exception:
                # The deterministic path keeps ingestion reliable and queues can be reviewed later.
                pass
        return self._extract_heuristic(document)

    def _extract_with_llm(self, document: RawDocument) -> list[ClaimCreate]:
        prompt = f"""
You are analyzing a research document about RAG systems or business research methods.
Extract empirical claims only. Return JSON with a top-level "claims" array.
For each claim provide:
claim_text, evidence_type [experiment|benchmark|case_study|theoretical|anecdotal],
evidence_location, evidence_summary, metrics array, conditions, limitations,
applicability_tags array, confidence number 0-1.
If a claim cannot be supported by evidence in the document, do not include it.

Title: {document.title}
Source: {document.source_url}
Text:
{document.text[:12000]}
"""
        assert self._client is not None
        response = self._client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.choices[0].message.content or "{}"
        payload = json.loads(content)
        output: list[ClaimCreate] = []
        for item in payload.get("claims", []):
            try:
                output.append(ClaimCreate(extraction_method="llm_auto", **item))
            except ValidationError:
                continue
        return output[:20]

    def _extract_heuristic(self, document: RawDocument) -> list[ClaimCreate]:
        claims: list[ClaimCreate] = []
        for index, sentence in enumerate(sentence_split(document.text)[:160]):
            lowered = sentence.lower()
            evidence_type = self._evidence_type(lowered)
            has_empirical_language = any(
                term in lowered
                for term in (
                    "improve",
                    "reduced",
                    "increased",
                    "outperform",
                    "benchmark",
                    "experiment",
                    "evaluation",
                    "found",
                    "show",
                    "reported",
                    "case study",
                    "recommended",
                    "best practice",
                    "risk",
                    "failure",
                )
            )
            metrics = METRIC_RE.findall(sentence)
            if not has_empirical_language and not metrics:
                continue
            tags = self._applicability_tags(lowered)
            if not tags:
                tags = [document.metadata.get("domain", "source_quality")]
            confidence = 0.45
            if evidence_type in {"experiment", "benchmark"}:
                confidence += 0.25
            if metrics:
                confidence += 0.15
            if any(term in lowered for term in ("may", "might", "suggest", "limited")):
                confidence -= 0.1
            claims.append(
                ClaimCreate(
                    claim_text=sentence[:700],
                    evidence_summary=self._summary(sentence, evidence_type, metrics),
                    evidence_type=evidence_type,
                    evidence_location=f"Sentence {index + 1}",
                    metrics=unique_keep_order(metrics),
                    conditions=self._conditions(sentence),
                    limitations=self._limitations(sentence),
                    applicability_tags=tags,
                    confidence=max(0.2, min(0.9, confidence)),
                    extraction_method="heuristic_auto",
                )
            )
        if claims:
            return claims[:20]
        return [
            ClaimCreate(
                claim_text=f"{document.title} provides background evidence relevant to {document.source_name}.",
                evidence_summary="No empirical sentence-level claim was found; item is retained for background only.",
                evidence_type="theoretical",
                evidence_location="Document summary",
                applicability_tags=[document.metadata.get("domain", "source_quality")],
                confidence=0.25,
                extraction_method="heuristic_auto",
            )
        ]

    def _evidence_type(self, lowered: str) -> str:
        if any(term in lowered for term in ("experiment", "ablation", "controlled")):
            return "experiment"
        if any(term in lowered for term in ("benchmark", "leaderboard", "evaluation")):
            return "benchmark"
        if "case study" in lowered or "customer" in lowered or "production" in lowered:
            return "case_study"
        if any(term in lowered for term in ("theory", "propose", "framework")):
            return "theoretical"
        return "anecdotal"

    def _applicability_tags(self, lowered: str) -> list[str]:
        tags: list[str] = []
        for tag, terms in APPLICABILITY_TERMS.items():
            if any(term in lowered for term in terms):
                tags.append(tag)
        return tags

    def _summary(self, sentence: str, evidence_type: str, metrics: list[str]) -> str:
        metric_text = f" Metrics mentioned: {', '.join(metrics)}." if metrics else ""
        return f"{evidence_type.replace('_', ' ').title()} evidence extracted from source text.{metric_text} {sentence[:220]}"

    def _conditions(self, sentence: str) -> str:
        match = re.search(r"\b(?:when|where|for|under|on)\b(.{0,160})", sentence, re.I)
        return match.group(0)[:180] if match else ""

    def _limitations(self, sentence: str) -> str:
        match = re.search(r"\b(?:however|but|except|limited|risk|failure|caveat)\b(.{0,180})", sentence, re.I)
        return match.group(0)[:200] if match else ""
