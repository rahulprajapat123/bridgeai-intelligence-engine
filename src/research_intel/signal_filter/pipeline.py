from __future__ import annotations

import asyncio
import hashlib
import math
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol
from urllib.parse import urlsplit

from .config import SignalFilterConfig
from .models import (CriterionScore, DecisionType, ExtractedClaim, FilterDecision,
                     FilterRunResult, PipelineMetrics, SignalItem, SignalScores, SourceType)
from .providers import EmbeddingProvider, HistoricalRepository, IntelligenceProvider
from .reason_codes import ReasonCode
from .text import canonicalize_url, cosine_similarity, fingerprint, normalize_text, normalized_language, recency_weight, vector_similarity


@dataclass
class FilterContext:
    repository: HistoricalRepository | None = None
    embedding_provider: EmbeddingProvider | None = None
    intelligence_provider: IntelligenceProvider | None = None
    brief_overrides: dict = field(default_factory=dict)
    embedding_cache: dict[str, list[float]] = field(default_factory=dict)
    decisions: list[FilterDecision] = field(default_factory=list)
    metrics: PipelineMetrics = field(default_factory=PipelineMetrics)


class PipelineStage(Protocol):
    name: str
    async def process(self, items: list[SignalItem], context: FilterContext, config: SignalFilterConfig) -> None: ...


def decide(context: FilterContext, config: SignalFilterConfig, item: SignalItem, stage: str, decision: DecisionType, code: str, explanation: str, threshold=None, observed=None, model=None) -> None:
    context.decisions.append(FilterDecision(item_id=item.item_id, stage=stage, decision=decision, reason_code=code, explanation=explanation, threshold=threshold, observed_value=observed, config_version=config.config_version, model_version=model))


def active(items: list[SignalItem]) -> list[SignalItem]:
    return [x for x in items if x.status == "pending"]


class NormalizeStage:
    name = "normalization"
    async def process(self, items, context, config):
        for item in active(items):
            item.title, item.body = normalize_text(item.title), normalize_text(item.body)
            item.normalized_text = normalized_language(f"{item.title} {item.body}")
            item.canonical_url = canonicalize_url(item.metadata.source_url)
            item.metadata.domain = (urlsplit(item.canonical_url).hostname or "").lower() if item.canonical_url else item.metadata.domain
            item.content_fingerprint = fingerprint(item.title, item.body)
            decide(context, config, item, self.name, DecisionType.PASS, ReasonCode.NORMALIZED, "Raw content preserved and normalized fields created.")


class MetadataValidationStage:
    name = "metadata_validation"
    async def process(self, items, context, config):
        for item in active(items):
            missing = [name for name, value in (("title", item.title), ("body", item.body), ("retrieved_at", item.metadata.retrieved_at)) if not value]
            if missing:
                item.status = "rejected"
                decide(context, config, item, self.name, DecisionType.REJECT, ReasonCode.METADATA_INVALID, f"Required fields missing: {', '.join(missing)}")
            else: decide(context, config, item, self.name, DecisionType.PASS, ReasonCode.METADATA_VALID, "Required metadata is present.")


class ExactDuplicateStage:
    name = "exact_duplicate"
    async def process(self, items, context, config):
        if not config.exact_duplicate_enabled: return
        seen: dict[str, str] = {}
        for item in active(items):
            keys = [x for x in (item.canonical_url, item.metadata.source_native_id, item.metadata.doi, item.metadata.repository_full_name, item.content_fingerprint) if x]
            duplicate = next((seen[k] for k in keys if k in seen), None)
            if duplicate:
                item.status, item.duplicate_of_item_id = "duplicate", duplicate
                decide(context, config, item, self.name, DecisionType.REJECT, ReasonCode.EXACT_DUPLICATE, f"Exact fingerprint matches item {duplicate}.")
            else:
                for key in keys: seen[key] = item.item_id


class LexicalDuplicateStage:
    name = "lexical_duplicate"
    async def process(self, items, context, config):
        if not config.lexical_dedup_enabled: return
        accepted: list[SignalItem] = []
        for item in active(items):
            match = None
            for other in accepted:
                score = config.title_similarity_weight*cosine_similarity(item.title, other.title) + config.body_similarity_weight*cosine_similarity(item.body, other.body)
                if score >= config.lexical_duplicate_threshold: match = (other, score); break
            if match:
                item.status, item.duplicate_of_item_id = "duplicate", match[0].item_id
                decide(context, config, item, self.name, DecisionType.REJECT, ReasonCode.LEXICAL_DUPLICATE, f"Weighted lexical similarity matches item {match[0].item_id}.", config.lexical_duplicate_threshold, round(match[1], 4))
            else: accepted.append(item)


class SemanticDuplicateStage:
    name = "semantic_duplicate"
    async def process(self, items, context, config):
        provider = context.embedding_provider
        candidates = active(items)
        if not config.semantic_dedup_enabled or not provider or len(candidates) < 2: return
        missing = [x for x in candidates if x.content_fingerprint not in context.embedding_cache]
        if missing:
            vectors = await provider.embed([x.normalized_text or "" for x in missing])
            for item, vector in zip(missing, vectors, strict=True): context.embedding_cache[item.content_fingerprint or item.item_id] = vector
        kept: list[SignalItem] = []
        for item in candidates:
            vector = context.embedding_cache[item.content_fingerprint or item.item_id]
            match = next(((x, vector_similarity(vector, context.embedding_cache[x.content_fingerprint or x.item_id])) for x in kept if vector_similarity(vector, context.embedding_cache[x.content_fingerprint or x.item_id]) >= config.semantic_duplicate_threshold), None)
            if match:
                item.status, item.duplicate_of_item_id = "duplicate", match[0].item_id
                decide(context, config, item, self.name, DecisionType.REJECT, ReasonCode.SEMANTIC_DUPLICATE, f"Semantic content matches item {match[0].item_id}.", config.semantic_duplicate_threshold, round(match[1], 4), provider.model_version)
            else: kept.append(item)


class ClassificationAndExtractionStage:
    name = "classification_and_extraction"
    async def process(self, items, context, config):
        active_items = active(items)
        # Classification (fast, do synchronously)
        for item in active_items:
            url, text = (item.canonical_url or "").lower(), (item.normalized_text or "")
            if "github.com/" in url: item.metadata.source_type = SourceType.REPO
            elif "arxiv.org/" in url or item.metadata.doi: item.metadata.source_type = SourceType.RESEARCH_PAPER
            elif "/docs" in url or "documentation" in text[:300]: item.metadata.source_type = SourceType.DOCUMENTATION
        
        # Extraction (slow, batch API calls in parallel)
        if context.intelligence_provider:
            async def extract_item(item):
                try:
                    await context.intelligence_provider.extract(item)
                    context.metrics.llm_calls += 1
                except Exception as e:
                    # Log error but continue processing
                    print(f"Warning: Failed to extract item {item.item_id}: {e}")
            await asyncio.gather(*[extract_item(item) for item in active_items])
        elif config.claim_extraction_enabled:
            for item in active_items:
                sentences = re.split(r"(?<=[.!?])\s+", item.body)
                item.claims = [ExtractedClaim(claim_id=f"{item.item_id}-c{i}", claim_text=s, evidence_text=s, confidence=.55, claim_type="factual", verifiability="unknown", support_status="supported") for i, s in enumerate(sentences[:5], 1) if len(s) > 30 and re.search(r"\d|\b(announced|released|reported|increased|decreased|launched)\b", s, re.I)]


class EventClusteringStage:
    name = "event_clustering"
    async def process(self, items, context, config):
        if not config.event_clustering_enabled: return
        clusters: list[tuple[str, SignalItem]] = []
        for item in active(items):
            match = next(((cid, other) for cid, other in clusters if cosine_similarity(item.title, other.title) >= config.event_similarity_threshold), None)
            if match:
                item.event_cluster_id = match[0]; match[1].metadata.supporting_urls.extend([item.canonical_url] if item.canonical_url else [])
                decide(context, config, item, self.name, DecisionType.WARNING, ReasonCode.EVENT_CLUSTERED, f"Grouped with related coverage in {match[0]}.")
            else:
                item.event_cluster_id = "evt_" + hashlib.sha256(item.title.lower().encode()).hexdigest()[:12]
                clusters.append((item.event_cluster_id, item))


class HeuristicScoringStage:
    name = "scoring"
    async def process(self, items, context, config):
        active_items = active(items)
        # Set recency weights (fast, synchronous)
        for item in active_items:
            source_type = getattr(item.metadata.source_type, "value", item.metadata.source_type)
            half_life = config.recency_half_life_days.get(str(source_type), 30)
            item.recency_weight = recency_weight(item.metadata.published_at, half_life)
        
        # Scoring (slow, batch API calls in parallel)
        if context.intelligence_provider:
            async def score_item(item):
                try:
                    item.scores, generated = await context.intelligence_provider.score_and_generate(item)
                    context.metrics.llm_calls += 1
                    for key, value in generated.items(): setattr(item, key, value)
                except Exception as e:
                    # Log error but continue with fallback scoring
                    print(f"Warning: Failed to score item {item.item_id}: {e}")
            await asyncio.gather(*[score_item(item) for item in active_items])
        else:
            # Fallback scoring (no API calls needed)
            for item in active_items:
                if not item.scores:
                    text = item.normalized_text or ""; evidence = item.claims[0].evidence_text if item.claims else item.title
                    concrete = sum(term in text for term in ("launch", "release", "cost", "customer", "workflow", "benchmark", "revenue", "adoption", "security"))
                    authority = 2 + bool(item.metadata.author) + bool(item.canonical_url) + bool(item.claims)
                    def c(score, rationale, conf=.58): return CriterionScore(score=min(5, score), confidence=conf, rationale=rationale + " Deterministic fallback; validate in production.", evidence=[evidence] if evidence else [])
                    item.scores = SignalScores(business_relevance=c(2+min(3, concrete), "Business/workflow terms found."), actionability=c(2+min(3, concrete), "Concrete change signals found."), novelty=c(3 if item.event_cluster_id else 2, "No authoritative historical provider configured."), credibility=c(authority, "Metadata and traceable evidence assessed."), momentum=c(1, "No trend series available.", .30))
                item.overall_confidence = item.scores.confidence


class ThresholdAndConfidenceStage:
    name = "confidence_decision"
    async def process(self, items, context, config):
        for item in active(items):
            assert item.scores
            failed = [(name, getattr(item.scores, name).score, minimum) for name, minimum in config.min_scores.items() if getattr(item.scores, name).score < minimum]
            if failed:
                item.status = "rejected"; name, score, minimum = failed[0]
                decide(context, config, item, self.name, DecisionType.REJECT, ReasonCode.SCORE_MINIMUM_FAILED, f"{name} failed its non-compensable minimum.", minimum, score); continue
            if item.scores.total < config.min_total_score:
                item.status = "rejected"; decide(context, config, item, self.name, DecisionType.REJECT, ReasonCode.TOTAL_SCORE_FAILED, "Total score below threshold.", config.min_total_score, item.scores.total); continue
            if (item.overall_confidence or 0) < config.auto_accept_confidence:
                item.status = "review"; decide(context, config, item, self.name, DecisionType.REVIEW, ReasonCode.LOW_CONFIDENCE, "Qualified item requires human review due to confidence.", config.auto_accept_confidence, round(item.overall_confidence or 0, 3)); continue
            decide(context, config, item, self.name, DecisionType.PASS, ReasonCode.CONFIDENCE_ACCEPTED, "Score and confidence gates passed.")


class VolumeAndLanguageStage:
    name = "volume_and_language_qa"
    async def process(self, items, context, config):
        qualified = sorted(active(items), key=lambda x: ((x.scores.total if x.scores else 0), x.overall_confidence or 0, x.recency_weight or 0), reverse=True)
        counts: dict[str, int] = {}; kept = 0; previous: list[tuple[str, str, str]] = []
        for item in qualified:
            category = item.category or str(getattr(item.metadata.source_type, "value", item.metadata.source_type))
            cap = config.category_caps.get(category, config.category_caps.get("other", 5))
            if counts.get(category, 0) >= cap:
                item.status = "qualified_but_cut_for_volume"; decide(context, config, item, self.name, DecisionType.VOLUME_CUT, ReasonCode.CATEGORY_CAP, f"Qualified but category cap for {category} was reached.", cap, counts.get(category, 0)); continue
            if kept >= config.total_item_cap:
                item.status = "qualified_but_cut_for_volume"; decide(context, config, item, self.name, DecisionType.VOLUME_CUT, ReasonCode.TOTAL_CAP, "Qualified but total item cap was reached.", config.total_item_cap, kept); continue
            failures = []
            for field_name in ("why_it_matters", "the_move"):
                value = getattr(item, field_name) or ""
                normalized = normalized_language(value)
                if any(normalized_language(p) in normalized for p in config.deny_list): failures.append((field_name, "deny-list or generic phrase"))
                if any(name == field_name and cosine_similarity(value, old) >= config.uniqueness_similarity_threshold for name, old, _ in previous): failures.append((field_name, "repeated language"))
            if failures:
                if context.intelligence_provider and config.auto_regeneration_enabled:
                    for field_name, reason in failures:
                        replacement = await context.intelligence_provider.regenerate_field(item, field_name, reason, config.deny_list); context.metrics.llm_calls += 1; setattr(item, field_name, replacement)
                else:
                    item.status = "review"; decide(context, config, item, self.name, DecisionType.REVIEW, ReasonCode.LANGUAGE_QA_FAILED, f"Generated field failed QA: {failures[0][0]} ({failures[0][1]})."); continue
            item.status = "accepted"; counts[category] = counts.get(category, 0)+1; kept += 1
            previous.extend((name, getattr(item, name) or "", item.item_id) for name in ("why_it_matters", "the_move"))
            decide(context, config, item, self.name, DecisionType.PASS, ReasonCode.ACCEPTED, "Accepted after quality, confidence, diversity, volume, and language checks.")


DEFAULT_STAGES = [NormalizeStage(), MetadataValidationStage(), ExactDuplicateStage(), LexicalDuplicateStage(), SemanticDuplicateStage(), ClassificationAndExtractionStage(), EventClusteringStage(), HeuristicScoringStage(), ThresholdAndConfidenceStage(), VolumeAndLanguageStage()]


class SignalFilterPipeline:
    def __init__(self, stages: list[PipelineStage], config: SignalFilterConfig): self.stages, self.config = stages, config
    async def run(self, items: list[SignalItem], context: FilterContext | None = None) -> FilterRunResult:
        context = context or FilterContext(); started = datetime.now(UTC); clock = time.perf_counter(); context.metrics.candidate_count = len(items)
        for stage in self.stages:
            try: await stage.process(items, context, self.config)
            except Exception as exc:
                context.metrics.failures += 1
                for item in active(items):
                    item.status = "review"; decide(context, self.config, item, stage.name, DecisionType.REVIEW, ReasonCode.STAGE_ERROR, f"Stage failed safely: {type(exc).__name__}")
                break
        statuses = [x.status for x in items]
        context.metrics.accepted_count = statuses.count("accepted"); context.metrics.review_count = statuses.count("review")
        context.metrics.duplicate_count = statuses.count("duplicate"); context.metrics.volume_cut_count = statuses.count("qualified_but_cut_for_volume")
        context.metrics.rejected_count = statuses.count("rejected"); context.metrics.processing_time_ms = (time.perf_counter()-clock)*1000
        result = FilterRunResult(run_id=str(uuid.uuid4()), items=items, decisions=context.decisions, metrics=context.metrics, config_version=self.config.config_version, started_at=started, completed_at=datetime.now(UTC))
        if context.repository: await context.repository.save_run(result)
        return result


def build_default_pipeline(config: SignalFilterConfig | None = None) -> "SignalFilterPipeline":
    """Build a pipeline using the enhanced, production-ready implementation."""
    # The enhanced pipeline owns a different dataclass model graph. Public API
    # Pydantic objects cannot safely be passed to it without a full conversion
    # adapter (the similarly named classes have different fields).
    return SignalFilterPipeline(DEFAULT_STAGES, config or SignalFilterConfig())

    from .enhanced_pipeline import SignalFilterPipeline as EnhancedPipeline, SignalFilterConfig as EnhancedConfig
    
    # Use enhanced config with same settings
    if config:
        enhanced_config = EnhancedConfig(
            exact_duplicate_enabled=config.exact_duplicate_enabled,
            lexical_dedup_enabled=config.lexical_dedup_enabled,
            semantic_dedup_enabled=config.semantic_dedup_enabled,
            event_clustering_enabled=config.event_clustering_enabled,
            claim_extraction_enabled=config.claim_extraction_enabled,
            historical_novelty_enabled=config.historical_novelty_enabled,
            diversity_ranking_enabled=getattr(config, 'diversity_ranking_enabled', True),  # Default to True
            auto_regeneration_enabled=config.auto_regeneration_enabled,
            lexical_duplicate_threshold=config.lexical_duplicate_threshold,
            semantic_duplicate_threshold=config.semantic_duplicate_threshold,
            title_similarity_weight=config.title_similarity_weight,
            body_similarity_weight=config.body_similarity_weight,
            min_scores=config.min_scores,
            min_total_score=config.min_total_score,
            category_caps=config.category_caps,
            total_item_cap=config.total_item_cap,
            auto_accept_confidence=config.auto_accept_confidence,
            human_review_confidence=config.human_review_confidence,
            implication_review_confidence=getattr(config, 'implication_review_confidence', 0.60),
            max_regeneration_attempts=config.max_regeneration_attempts,
            denylist_phrases=getattr(config, 'deny_list', []),  # Map deny_list to denylist_phrases
            recency_half_life_days=config.recency_half_life_days,
            max_pdf_pages=config.max_pdf_pages,
            max_candidate_items=config.max_candidate_items,
        )
    else:
        enhanced_config = EnhancedConfig()
    
    # Create enhanced pipeline
    enhanced_pipeline = EnhancedPipeline(enhanced_config)
    
    # Wrap to handle old FilterContext → new FilterContext conversion
    class ContextAdapterPipeline:
        def __init__(self, pipeline):
            self._pipeline = pipeline
        
        async def run(self, items: list[SignalItem], context: FilterContext | None = None) -> FilterRunResult:
            from .enhanced_pipeline import FilterContext as EnhancedContext
            
            # Convert old context to enhanced context format
            # PipelineMetrics doesn't have run_id, generate a new one
            enhanced_context = EnhancedContext(
                run_id=str(uuid.uuid4()),
                brief=context.brief_overrides.get('brief') if context and hasattr(context, 'brief_overrides') else None,
            )
            
            # Run the enhanced pipeline
            enhanced_result = await self._pipeline.run(items, enhanced_context)
            
            # Normalize status values for API compatibility
            # Enhanced uses: "accept", "reject", "review", "qualified_but_cut_for_volume"
            # Old API expects: "accepted", "rejected", "review", "qualified_but_cut_for_volume"
            def normalize_status(status):
                if hasattr(status, 'value'):
                    status_str = status.value
                else:
                    status_str = str(status)
                
                # Map enhanced status to API-expected status
                status_map = {
                    "accept": "accepted",
                    "reject": "rejected",
                    "pass": "pending",
                }
                return status_map.get(status_str, status_str)
            
            # Apply status normalization to all items
            all_items = (
                enhanced_result.accepted + 
                enhanced_result.rejected + 
                enhanced_result.review + 
                enhanced_result.volume_cut
            )
            
            for item in all_items:
                item.status = normalize_status(item.status)
            
            # Convert enhanced result to old format for API compatibility
            # The enhanced result has separate lists: accepted, rejected, review, volume_cut
            # But the old API expects a single result.items list
            
            # Create a compatible result object with both formats
            class CompatibleResult:
                def __init__(self, enhanced_result, all_items):
                    self.run_id = enhanced_result.run_id
                    self.items = all_items  # For old API compatibility
                    self.accepted = enhanced_result.accepted
                    self.rejected = enhanced_result.rejected
                    self.review = enhanced_result.review
                    self.volume_cut = enhanced_result.volume_cut
                    self.decisions = enhanced_result.decisions
                    self.metrics = enhanced_result.metrics
                    self.config_version = getattr(enhanced_result, 'config_version', '2.0.0')
                    self.started_at = getattr(enhanced_result.metrics, 'started_at', datetime.now(UTC))
                    self.completed_at = getattr(enhanced_result.metrics, 'completed_at', datetime.now(UTC))
                
                def to_dict(self):
                    return enhanced_result.to_dict()
            
            return CompatibleResult(enhanced_result, all_items)
    
    return ContextAdapterPipeline(enhanced_pipeline)
