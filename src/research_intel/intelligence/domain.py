from __future__ import annotations

import math
import re
from collections import Counter

from research_intel.intelligence.taxonomy import DOMAIN_DEFINITIONS
from research_intel.schemas import DomainClassification
from research_intel.utils import tokenize, unique_keep_order


STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "about",
    "shall",
    "will",
    "your",
    "have",
    "has",
    "are",
    "was",
    "were",
    "their",
    "more",
    "less",
    "than",
    "using",
    "use",
    "based",
    "across",
    "include",
    "includes",
}


class DomainClassifier:
    """Weighted taxonomy classifier with guardrails against incidental AI-term bias."""

    CANONICAL_NAMES = {
        "ai_ml": "AI_ML",
        "developer_tooling": "DEVELOPER_TOOLING",
        "competitive_intelligence": "COMPETITIVE_INTELLIGENCE",
        "market_research": "MARKET_RESEARCH",
        "partner_programs": "PARTNER_ECOSYSTEM",
        "legal": "LEGAL",
        "finance": "FINANCE",
        "healthcare": "HEALTHCARE",
        "general": "GENERAL_BUSINESS",
    }

    def classify(self, text: str) -> DomainClassification:
        lowered = f" {text.lower()} "
        tokens = tokenize(text)
        token_counts = Counter(tokens)
        total = max(1, len(tokens))
        scores: dict[str, float] = {}
        rationale: dict[str, list[str]] = {}

        for key, definition in DOMAIN_DEFINITIONS.items():
            if key == "general":
                continue
            score = 0.0
            reasons: list[str] = []
            for keyword in definition.keywords:
                keyword_lower = keyword.lower()
                if " " in keyword_lower:
                    count = lowered.count(f" {keyword_lower} ")
                    if count:
                        score += count * 4.0
                        reasons.append(keyword)
                else:
                    count = token_counts[keyword_lower]
                    if count:
                        score += count * 1.5
                        reasons.append(keyword)
            scores[key] = score / math.sqrt(total)
            rationale[key] = unique_keep_order(reasons)[:8]

        # If partner/channel terms dominate, incidental model/vendor names should not pull the
        # document back into AI/ML. This directly addresses the Intel Partner Program failure mode.
        business_signal = (
            scores.get("partner_programs", 0)
            + scores.get("competitive_intelligence", 0)
            + scores.get("market_research", 0)
        )
        negative_signals: list[str] = []
        incidental_ai_mention = (
            any(term in lowered for term in ("openai", "claude", "gemini", "anthropic"))
            and any(term in lowered for term in ("mention", "example", "trend", "messaging"))
            and any(
                term in lowered
                for term in ("partner", "channel", "reseller", "enablement", "comparison", "business")
            )
        )
        if business_signal > 0.65 and scores.get("ai_ml", 0) < business_signal * 0.85:
            scores["ai_ml"] *= 0.45
            rationale.setdefault("partner_programs", []).append("business objective dominates AI terms")
            negative_signals.append("Mentions of AI tools or RAG are not the core objective.")
        elif incidental_ai_mention and business_signal > 0.35:
            scores["ai_ml"] *= 0.35
            negative_signals.append("AI vendor mentions appear contextual rather than the requested deliverable.")

        if not scores or max(scores.values(), default=0) <= 0:
            selected = DOMAIN_DEFINITIONS["general"]
            return DomainClassification(
                domain="general",
                primary_domain="GENERAL_BUSINESS",
                confidence=0.35,
                hierarchy=list(selected.hierarchy),
                scores={"general": 0.35},
                rationale=["No strong domain-specific signal found."],
                reasoning_summary="No strong domain-specific signal found.",
            )

        selected_key = max(scores, key=scores.get)
        selected = DOMAIN_DEFINITIONS[selected_key]
        sorted_scores = sorted(scores.values(), reverse=True)
        top = sorted_scores[0]
        runner_up = sorted_scores[1] if len(sorted_scores) > 1 else 0
        confidence = min(0.95, max(0.4, 0.5 + (top - runner_up) / max(top, 0.1) * 0.45))
        normalized_scores = {
            DOMAIN_DEFINITIONS[key].label: round(value, 3) for key, value in scores.items()
        }
        secondary_domains = [
            self.CANONICAL_NAMES.get(key, key.upper())
            for key, value in sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
            if key != selected_key and value > 0 and value >= top * 0.35
        ][:4]
        if selected_key == "partner_programs":
            secondary_domains = [domain for domain in secondary_domains if domain != "AI_ML"]
            if scores.get("competitive_intelligence", 0) > 0 or any(
                signal in lowered for signal in ("comparison", "benchmark", "competitor", "positioning")
            ):
                secondary_domains.append("COMPETITIVE_INTELLIGENCE")
            if scores.get("market_research", 0) > 0 or any(
                signal in lowered
                for signal in ("audience matrix", "sentiment", "social listening", "search analytics")
            ):
                secondary_domains.append("MARKET_RESEARCH")
            secondary_domains = unique_keep_order(secondary_domains)[:4]
        selected_reasons = rationale.get(selected_key, [])[:8]
        reasoning_summary = (
            f"Classified as {selected.label} based on signals: {', '.join(selected_reasons)}."
            if selected_reasons
            else f"Classified as {selected.label} based on the highest weighted taxonomy score."
        )
        return DomainClassification(
            domain=selected.label,
            primary_domain=self.CANONICAL_NAMES.get(selected_key, selected_key.upper()),
            secondary_domains=secondary_domains,
            confidence=round(confidence, 3),
            hierarchy=list(selected.hierarchy),
            scores=normalized_scores,
            rationale=selected_reasons,
            reasoning_summary=reasoning_summary,
            negative_signals=negative_signals,
        )

    def key_for_label(self, label_or_key: str | None) -> str:
        if not label_or_key:
            return "general"
        normalized = re.sub(r"[^a-z0-9]+", "_", label_or_key.lower()).strip("_")
        if normalized in DOMAIN_DEFINITIONS:
            return normalized
        for key, definition in DOMAIN_DEFINITIONS.items():
            label_norm = re.sub(r"[^a-z0-9]+", "_", definition.label.lower()).strip("_")
            if normalized == label_norm:
                return key
        return "general"

    def routes_for(self, label_or_key: str | None) -> list[str]:
        key = self.key_for_label(label_or_key)
        return list(DOMAIN_DEFINITIONS.get(key, DOMAIN_DEFINITIONS["general"]).source_routes)

    def expansions_for(self, label_or_key: str | None) -> list[str]:
        key = self.key_for_label(label_or_key)
        return list(DOMAIN_DEFINITIONS.get(key, DOMAIN_DEFINITIONS["general"]).query_expansions)
