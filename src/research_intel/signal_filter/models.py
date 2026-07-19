"""
Signal Filter Models
Re-exports models from the enhanced pipeline implementation for API compatibility.
"""
from __future__ import annotations

# Re-export all models from enhanced pipeline
from .enhanced_pipeline import (
    SignalItem,
    SourceMetadata,
    SourceType,
    SignalScores,
    CriterionScore,
    FilterRunResult,
    FilterDecision,
    DecisionStatus as DecisionType,  # Alias for backward compatibility
    ExtractedClaim,
    NoveltyAssessment,
    CredibilityAssessment,
    GeneratedSignalFields,
    ReasonCode,
    Verifiability,
    SupportStatus,
    NoveltyType,
)

# Export metrics class for compatibility
from .enhanced_pipeline import FilterRunMetrics as PipelineMetrics

__all__ = [
    "SignalItem",
    "SourceMetadata",
    "SourceType",
    "SignalScores",
    "CriterionScore",
    "FilterRunResult",
    "FilterDecision",
    "DecisionType",
    "ExtractedClaim",
    "NoveltyAssessment",
    "CredibilityAssessment",
    "GeneratedSignalFields",
    "ReasonCode",
    "Verifiability",
    "SupportStatus",
    "NoveltyType",
    "PipelineMetrics",
]

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


def now_utc() -> datetime:
    return datetime.now(UTC)


class SourceType(StrEnum):
    NEWS = "news"
    BLOG = "blog"
    REPO = "repo"
    RESEARCH_PAPER = "research_paper"
    DOCUMENTATION = "documentation"
    REPORT = "report"
    COMMUNITY = "community"
    OTHER = "other"


class DecisionType(StrEnum):
    PASS = "pass"
    REJECT = "reject"
    REVIEW = "review"
    VOLUME_CUT = "qualified_but_cut_for_volume"
    WARNING = "warning"


class SourceMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")
    source_url: str | None = None
    source_name: str | None = None
    source_type: SourceType = SourceType.OTHER
    author: str | None = None
    published_at: datetime | None = None
    retrieved_at: datetime = Field(default_factory=now_utc)
    language: str | None = None
    domain: str | None = None
    source_native_id: str | None = None
    doi: str | None = None
    repository_full_name: str | None = None
    supporting_urls: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)


class ExtractedClaim(BaseModel):
    claim_id: str
    claim_text: str
    evidence_text: str | None = None
    evidence_location: str | None = None
    confidence: float = Field(ge=0, le=1)
    claim_type: str | None = None
    entities: list[str] = Field(default_factory=list)
    numeric_values: list[str] = Field(default_factory=list)
    verifiability: str = "unknown"
    support_status: str = "not_checked"


class CriterionScore(BaseModel):
    score: int = Field(ge=0, le=5)
    confidence: float = Field(ge=0, le=1)
    rationale: str
    evidence: list[str] = Field(default_factory=list)


class SignalScores(BaseModel):
    business_relevance: CriterionScore
    actionability: CriterionScore
    novelty: CriterionScore
    credibility: CriterionScore
    momentum: CriterionScore

    @property
    def total(self) -> int:
        return sum(getattr(self, name).score for name in type(self).model_fields)

    @property
    def confidence(self) -> float:
        return sum(getattr(self, name).confidence for name in type(self).model_fields) / 5


class SignalItem(BaseModel):
    item_id: str
    title: str
    body: str
    raw_title: str | None = None
    raw_body: str | None = None
    normalized_text: str | None = None
    canonical_url: str | None = None
    content_fingerprint: str | None = None
    metadata: SourceMetadata
    claims: list[ExtractedClaim] = Field(default_factory=list)
    product_implication: str | None = None
    scores: SignalScores | None = None
    recency_weight: float | None = Field(default=None, ge=0, le=1)
    overall_confidence: float | None = Field(default=None, ge=0, le=1)
    category: str | None = None
    event_cluster_id: str | None = None
    duplicate_of_item_id: str | None = None
    why_it_matters: str | None = None
    the_move: str | None = None
    recommended_action: str | None = None
    status: str = "pending"
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)

    @model_validator(mode="after")
    def preserve_raw(self) -> "SignalItem":
        self.raw_title = self.raw_title if self.raw_title is not None else self.title
        self.raw_body = self.raw_body if self.raw_body is not None else self.body
        return self


class FilterDecision(BaseModel):
    item_id: str
    stage: str
    decision: DecisionType
    reason_code: str
    explanation: str
    threshold: float | int | None = None
    observed_value: float | int | str | None = None
    config_version: str
    model_version: str | None = None
    created_at: datetime = Field(default_factory=now_utc)


class PipelineMetrics(BaseModel):
    candidate_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    review_count: int = 0
    duplicate_count: int = 0
    volume_cut_count: int = 0
    stage_drop_counts: dict[str, int] = Field(default_factory=dict)
    processing_time_ms: float = 0
    llm_calls: int = 0
    token_usage: int = 0
    estimated_cost: float = 0
    cache_hits: int = 0
    failures: int = 0


class FilterRunResult(BaseModel):
    run_id: str
    items: list[SignalItem]
    decisions: list[FilterDecision]
    metrics: PipelineMetrics
    config_version: str
    started_at: datetime
    completed_at: datetime

    @property
    def accepted(self) -> list[SignalItem]:
        return [item for item in self.items if item.status == "accepted"]
