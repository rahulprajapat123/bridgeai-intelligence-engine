"""
Bridge AI Production-Ready Signal Filter
========================================

A dependency-free reference implementation for filtering intelligence signals
from news, blogs, GitHub repositories, research papers, documentation, reports,
and community sources.

Implemented capabilities
------------------------
1. Input normalization and metadata validation
2. Exact, lexical, and pluggable semantic duplicate detection
3. Event clustering hooks
4. Source-type classification hooks
5. Product/business implication filtering
6. Lightweight claim extraction with pluggable AI override
7. Source-specific credibility scoring
8. Historical novelty hooks
9. Separate recency and momentum calculations
10. Five-criterion scoring with per-score confidence, rationale, and evidence
11. Confidence-based accept/reject/review routing
12. Diversity-aware ranking and category/total caps
13. Structured generated intelligence fields
14. Stage 3 QA, deny-list checks, and targeted regeneration hooks
15. Complete structured audit trail and operational metrics

The module runs without external dependencies. Production deployments should
replace the heuristic classifier, claim extractor, scorer, embedding provider,
historical lookup, momentum provider, and generator with real services.

Python version: 3.11+
"""

from __future__ import annotations

import hashlib
import html
import json
import math
import re
import statistics
import time
import unicodedata
import urllib.parse
import uuid
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Callable, Iterable, Mapping, Optional, Protocol, Sequence


# =============================================================================
# Enumerations and reason codes
# =============================================================================


class SourceType(str, Enum):
    NEWS = "news"
    BLOG = "blog"
    REPO = "repo"
    RESEARCH_PAPER = "research_paper"
    DOCUMENTATION = "documentation"
    REPORT = "report"
    COMMUNITY = "community"
    OTHER = "other"


class DecisionStatus(str, Enum):
    PASS = "pass"
    ACCEPT = "accept"
    REJECT = "reject"
    REVIEW = "review"
    WARNING = "warning"
    QUALIFIED_BUT_CUT_FOR_VOLUME = "qualified_but_cut_for_volume"


class SupportStatus(str, Enum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    NOT_CHECKED = "not_checked"


class Verifiability(str, Enum):
    VERIFIABLE = "verifiable"
    PARTIALLY_VERIFIABLE = "partially_verifiable"
    OPINION = "opinion"
    UNKNOWN = "unknown"


class NoveltyType(str, Enum):
    NEW_EVENT = "new_event"
    MATERIAL_UPDATE = "material_update"
    NEW_EVIDENCE = "new_evidence"
    NEW_ADOPTION_SIGNAL = "new_adoption_signal"
    NEW_COMPETITOR_MOVE = "new_competitor_move"
    NEW_CAPABILITY = "new_capability"
    NEW_REGULATORY_CHANGE = "new_regulatory_change"
    REPEATED_COVERAGE = "repeated_coverage"
    MINOR_UPDATE = "minor_update"
    NO_MATERIAL_CHANGE = "no_material_change"
    UNKNOWN = "unknown"


class ReasonCode(str, Enum):
    NORMALIZED = "NORMALIZED"
    METADATA_VALID = "METADATA_VALID"
    METADATA_INVALID = "METADATA_INVALID"
    EXACT_DUPLICATE = "EXACT_DUPLICATE"
    LEXICAL_DUPLICATE = "LEXICAL_DUPLICATE"
    SEMANTIC_DUPLICATE = "SEMANTIC_DUPLICATE"
    EVENT_CLUSTERED = "EVENT_CLUSTERED"
    SOURCE_CLASSIFIED = "SOURCE_CLASSIFIED"
    PRODUCT_IMPLICATION_PRESENT = "PRODUCT_IMPLICATION_PRESENT"
    PRODUCT_IMPLICATION_MISSING = "PRODUCT_IMPLICATION_MISSING"
    PRODUCT_IMPLICATION_LOW_CONFIDENCE = "PRODUCT_IMPLICATION_LOW_CONFIDENCE"
    CLAIMS_EXTRACTED = "CLAIMS_EXTRACTED"
    CLAIM_UNSUPPORTED = "CLAIM_UNSUPPORTED"
    CLAIM_MISSING_EVIDENCE = "CLAIM_MISSING_EVIDENCE"
    CLAIM_NUMERIC_MISMATCH = "CLAIM_NUMERIC_MISMATCH"
    CLAIM_PRIMARY_SOURCE_MISSING = "CLAIM_PRIMARY_SOURCE_MISSING"
    CLAIM_CONTRADICTED = "CLAIM_CONTRADICTED"
    CREDIBILITY_SCORED = "CREDIBILITY_SCORED"
    NOVELTY_SCORED = "NOVELTY_SCORED"
    SCORE_PASSED = "SCORE_PASSED"
    SCORE_CRITERION_BELOW_MINIMUM = "SCORE_CRITERION_BELOW_MINIMUM"
    SCORE_TOTAL_BELOW_MINIMUM = "SCORE_TOTAL_BELOW_MINIMUM"
    SCORE_INVALID = "SCORE_INVALID"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    CATEGORY_CAP = "CATEGORY_CAP"
    TOTAL_CAP = "TOTAL_CAP"
    DIVERSITY_SUPPRESSED = "DIVERSITY_SUPPRESSED"
    GENERATION_COMPLETE = "GENERATION_COMPLETE"
    UNIQUENESS_FAILURE = "UNIQUENESS_FAILURE"
    DENYLIST_FAILURE = "DENYLIST_FAILURE"
    UNSUPPORTED_GENERATION = "UNSUPPORTED_GENERATION"
    REGENERATION_SUCCESS = "REGENERATION_SUCCESS"
    REGENERATION_FAILED = "REGENERATION_FAILED"
    ACCEPTED = "ACCEPTED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


# =============================================================================
# Configuration
# =============================================================================


@dataclass(slots=True)
class SignalFilterConfig:
    config_version: str = "2.0.0"

    # Feature flags
    exact_duplicate_enabled: bool = True
    lexical_dedup_enabled: bool = True
    semantic_dedup_enabled: bool = True
    event_clustering_enabled: bool = True
    claim_extraction_enabled: bool = True
    historical_novelty_enabled: bool = True
    auto_regeneration_enabled: bool = True
    diversity_ranking_enabled: bool = True

    # Similarity thresholds
    lexical_duplicate_threshold: float = 0.82
    semantic_duplicate_threshold: float = 0.88
    event_similarity_threshold: float = 0.82
    uniqueness_similarity_threshold: float = 0.60
    title_similarity_weight: float = 0.40
    body_similarity_weight: float = 0.60

    # Score thresholds
    min_scores: dict[str, int] = field(
        default_factory=lambda: {
            "business_relevance": 3,
            "actionability": 3,
            "novelty": 2,
            "credibility": 2,
            "momentum": 1,
        }
    )
    min_total_score: int = 15

    # Category and volume controls
    category_caps: dict[str, int] = field(
        default_factory=lambda: {
            "news": 8,
            "blog": 5,
            "repo": 5,
            "research_paper": 5,
            "documentation": 5,
            "report": 5,
            "community": 3,
            "other": 5,
        }
    )
    total_item_cap: int = 20
    max_per_domain: int = 4
    max_per_publisher: int = 4
    minimum_primary_sources: int = 2

    # Confidence routing
    auto_accept_confidence: float = 0.80
    human_review_confidence: float = 0.55
    implication_review_confidence: float = 0.55
    max_regeneration_attempts: int = 2

    # Source recency half-life
    recency_half_life_days: dict[str, int] = field(
        default_factory=lambda: {
            "news": 7,
            "blog": 30,
            "repo": 45,
            "research_paper": 180,
            "documentation": 90,
            "report": 180,
            "community": 14,
            "other": 30,
        }
    )

    technical_source_types: set[str] = field(
        default_factory=lambda: {
            "academic",
            "arxiv",
            "paper",
            "research_paper",
            "technical_blog",
            "documentation",
        }
    )

    denylist_phrases: list[str] = field(
        default_factory=lambda: [
            "candidate evidence for enterprise ai strategy and implementation decisions",
            "important for the ai landscape",
            "relevant to business strategy",
            "significant implications for the industry",
            "worth keeping an eye on",
        ]
    )

    # File-ingestion defaults retained for compatibility with the reference PRD.
    max_pdf_pages: int = 60
    max_candidate_items: int = 40

    def validate(self) -> None:
        probability_fields = {
            "lexical_duplicate_threshold": self.lexical_duplicate_threshold,
            "semantic_duplicate_threshold": self.semantic_duplicate_threshold,
            "event_similarity_threshold": self.event_similarity_threshold,
            "uniqueness_similarity_threshold": self.uniqueness_similarity_threshold,
            "title_similarity_weight": self.title_similarity_weight,
            "body_similarity_weight": self.body_similarity_weight,
            "auto_accept_confidence": self.auto_accept_confidence,
            "human_review_confidence": self.human_review_confidence,
            "implication_review_confidence": self.implication_review_confidence,
        }
        for name, value in probability_fields.items():
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1; got {value}")

        if not math.isclose(
            self.title_similarity_weight + self.body_similarity_weight,
            1.0,
            rel_tol=1e-9,
            abs_tol=1e-9,
        ):
            raise ValueError("title_similarity_weight + body_similarity_weight must equal 1")

        required_criteria = {
            "business_relevance",
            "actionability",
            "novelty",
            "credibility",
            "momentum",
        }
        if set(self.min_scores) != required_criteria:
            raise ValueError(f"min_scores must contain exactly {sorted(required_criteria)}")

        for criterion, minimum in self.min_scores.items():
            if not isinstance(minimum, int) or not 0 <= minimum <= 5:
                raise ValueError(f"Minimum for {criterion} must be an integer from 0 to 5")

        if not 0 <= self.min_total_score <= 25:
            raise ValueError("min_total_score must be between 0 and 25")
        if self.total_item_cap < 1:
            raise ValueError("total_item_cap must be positive")
        if self.max_regeneration_attempts < 0:
            raise ValueError("max_regeneration_attempts cannot be negative")

    @classmethod
    def from_json(cls, raw: str) -> "SignalFilterConfig":
        data = json.loads(raw)
        config = cls(**data)
        config.validate()
        return config

    def to_json(self, *, indent: int = 2) -> str:
        serializable = asdict(self)
        serializable["technical_source_types"] = sorted(self.technical_source_types)
        return json.dumps(serializable, indent=indent, default=str)


# =============================================================================
# Domain models
# =============================================================================


def utc_now() -> datetime:
    return datetime.now(UTC)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def validate_confidence(value: float, name: str = "confidence") -> float:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{name} must be a finite number")
    numeric = float(value)
    if not 0.0 <= numeric <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")
    return numeric


@dataclass(slots=True)
class SourceMetadata:
    source_url: str | None = None
    source_name: str | None = None
    source_type: SourceType = SourceType.OTHER
    author: str | None = None
    published_at: datetime | None = None
    retrieved_at: datetime = field(default_factory=utc_now)
    language: str | None = None
    domain: str | None = None
    source_native_id: str | None = None
    doi: str | None = None
    repository_full_name: str | None = None
    is_primary_source: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExtractedClaim:
    claim_id: str
    claim_text: str
    evidence_text: str | None = None
    evidence_location: str | None = None
    confidence: float = 0.50
    claim_type: str | None = None
    verifiability: Verifiability = Verifiability.UNKNOWN
    support_status: SupportStatus = SupportStatus.NOT_CHECKED
    entities: list[str] = field(default_factory=list)
    numeric_values: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.confidence = validate_confidence(self.confidence)


@dataclass(slots=True)
class CriterionScore:
    score: int
    confidence: float
    rationale: str
    evidence: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.score, int) or not 0 <= self.score <= 5:
            raise ValueError(f"score must be an integer from 0 to 5; got {self.score!r}")
        self.confidence = validate_confidence(self.confidence)
        if not self.rationale.strip():
            raise ValueError("rationale cannot be empty")


@dataclass(slots=True)
class SignalScores:
    business_relevance: CriterionScore
    actionability: CriterionScore
    novelty: CriterionScore
    credibility: CriterionScore
    momentum: CriterionScore

    @property
    def total(self) -> int:
        return sum(
            (
                self.business_relevance.score,
                self.actionability.score,
                self.novelty.score,
                self.credibility.score,
                self.momentum.score,
            )
        )

    @property
    def average_confidence(self) -> float:
        return statistics.fmean(
            (
                self.business_relevance.confidence,
                self.actionability.confidence,
                self.novelty.confidence,
                self.credibility.confidence,
                self.momentum.confidence,
            )
        )

    def as_dict(self) -> dict[str, CriterionScore]:
        return {
            "business_relevance": self.business_relevance,
            "actionability": self.actionability,
            "novelty": self.novelty,
            "credibility": self.credibility,
            "momentum": self.momentum,
        }


@dataclass(slots=True)
class NoveltyAssessment:
    novelty_type: NoveltyType
    score: int
    confidence: float
    rationale: str
    previous_reference_ids: list[str] = field(default_factory=list)
    new_information: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.score, int) or not 0 <= self.score <= 5:
            raise ValueError("Novelty score must be an integer from 0 to 5")
        self.confidence = validate_confidence(self.confidence)


@dataclass(slots=True)
class CredibilityAssessment:
    score: int
    confidence: float
    rationale: str
    components: dict[str, float] = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.score, int) or not 0 <= self.score <= 5:
            raise ValueError("Credibility score must be an integer from 0 to 5")
        self.confidence = validate_confidence(self.confidence)
        for key, value in self.components.items():
            self.components[key] = validate_confidence(value, f"credibility component {key}")


@dataclass(slots=True)
class GeneratedSignalFields:
    headline: str
    summary: str
    why_it_matters: str
    the_move: str
    recommended_action: str
    affected_teams: list[str] = field(default_factory=list)
    key_entities: list[str] = field(default_factory=list)
    key_claims: list[str] = field(default_factory=list)
    risks_or_caveats: list[str] = field(default_factory=list)
    source_citations: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SignalItem:
    title: str
    body: str
    metadata: SourceMetadata
    item_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    raw_title: str | None = None
    raw_body: str | None = None
    normalized_text: str | None = None
    canonical_url: str | None = None
    content_hash: str | None = None
    claims: list[ExtractedClaim] = field(default_factory=list)
    product_implication: str | None = None
    product_implication_confidence: float | None = None
    affected_teams: list[str] = field(default_factory=list)
    scores: SignalScores | None = None
    credibility: CredibilityAssessment | None = None
    novelty: NoveltyAssessment | None = None
    recency_weight: float = 1.0
    momentum_evidence: list[str] = field(default_factory=list)
    overall_confidence: float | None = None
    category: str | None = None
    event_cluster_id: str | None = None
    duplicate_of_item_id: str | None = None
    duplicate_similarity: float | None = None
    generated: GeneratedSignalFields | None = None
    status: DecisionStatus = DecisionStatus.PASS
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class FilterDecision:
    item_id: str
    stage: str
    decision: DecisionStatus
    reason_code: ReasonCode
    explanation: str
    threshold: float | int | None = None
    observed_value: float | int | str | None = None
    config_version: str = "2.0.0"
    model_version: str | None = None
    prompt_version: str | None = None
    confidence: float | None = None
    duration_ms: float | None = None
    created_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class StageMetrics:
    stage: str
    input_count: int
    output_count: int
    rejected_count: int = 0
    review_count: int = 0
    warning_count: int = 0
    duration_ms: float = 0.0


@dataclass(slots=True)
class FilterRunMetrics:
    run_id: str
    started_at: datetime
    completed_at: datetime | None = None
    candidate_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    review_count: int = 0
    duplicate_count: int = 0
    volume_cut_count: int = 0
    regeneration_attempts: int = 0
    regeneration_successes: int = 0
    stage_metrics: list[StageMetrics] = field(default_factory=list)


@dataclass(slots=True)
class FilterRunResult:
    run_id: str
    accepted: list[SignalItem]
    rejected: list[SignalItem]
    review: list[SignalItem]
    volume_cut: list[SignalItem]
    decisions: list[FilterDecision]
    metrics: FilterRunMetrics

    def to_dict(self) -> dict[str, Any]:
        return _serialize_dataclass(self)


@dataclass(slots=True)
class FilterContext:
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    brief: str | None = None
    domain: str | None = None
    target_audience: list[str] = field(default_factory=list)
    model_version: str | None = None
    prompt_version: str | None = None


# =============================================================================
# Provider protocols and callable aliases
# =============================================================================


class EmbeddingProvider(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""


class HistoricalRepository(Protocol):
    def find_similar_items(self, item: SignalItem, limit: int = 10) -> list[SignalItem]:
        """Return historically similar signals ordered by similarity."""


class MomentumProvider(Protocol):
    def assess(self, item: SignalItem) -> tuple[int, float, str, list[str]]:
        """Return score, confidence, rationale, and evidence."""


ProductImplicationFn = Callable[[SignalItem, FilterContext], tuple[str | None, float, list[str]]]
ClaimExtractorFn = Callable[[SignalItem, FilterContext], list[ExtractedClaim]]
ScorerFn = Callable[[SignalItem, FilterContext], SignalScores]
GeneratorFn = Callable[[SignalItem, FilterContext], GeneratedSignalFields]
RegeneratorFn = Callable[[SignalItem, str, str, FilterContext], str]
EventKeyFn = Callable[[SignalItem, FilterContext], str | None]
SourceClassifierFn = Callable[[SignalItem, FilterContext], tuple[SourceType, float, str]]


# =============================================================================
# Text, URL, date, and similarity utilities
# =============================================================================


_WORD_RE = re.compile(r"[a-z0-9]+")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_NUMBER_RE = re.compile(r"\b(?:\d+(?:\.\d+)?(?:%|x|k|m|b)?|\$\d+(?:\.\d+)?(?:k|m|b)?)\b", re.I)
_TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
    "mc_cid",
    "mc_eid",
}


def normalize_text(text: str) -> str:
    text = html.unescape(text or "")
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u200b", " ").replace("\ufeff", " ")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_for_matching(text: str) -> str:
    return " ".join(_WORD_RE.findall(normalize_text(text).lower()))


def canonicalize_url(url: str | None) -> str | None:
    if not url:
        return None
    candidate = url.strip()
    if not candidate:
        return None
    try:
        parsed = urllib.parse.urlsplit(candidate)
    except ValueError:
        return candidate

    scheme = parsed.scheme.lower() or "https"
    hostname = (parsed.hostname or "").lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    port = parsed.port
    netloc = hostname
    if port and not ((scheme == "https" and port == 443) or (scheme == "http" and port == 80)):
        netloc = f"{hostname}:{port}"

    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")

    query_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
    filtered = sorted((k, v) for k, v in query_pairs if k.lower() not in _TRACKING_PARAMS)
    query = urllib.parse.urlencode(filtered, doseq=True)

    return urllib.parse.urlunsplit((scheme, netloc, path, query, ""))


def extract_domain(url: str | None) -> str | None:
    canonical = canonicalize_url(url)
    if not canonical:
        return None
    try:
        hostname = urllib.parse.urlsplit(canonical).hostname
    except ValueError:
        return None
    if not hostname:
        return None
    return hostname.removeprefix("www.").lower()


def stable_hash(*parts: str | None) -> str:
    payload = "\n".join(normalize_for_matching(part or "") for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def tokenize(text: str) -> Counter[str]:
    return Counter(_WORD_RE.findall(normalize_text(text).lower()))


def cosine_similarity_from_counters(a: Counter[str], b: Counter[str]) -> float:
    if not a or not b:
        return 0.0
    shared = set(a) & set(b)
    dot = sum(a[word] * b[word] for word in shared)
    norm_a = math.sqrt(sum(value * value for value in a.values()))
    norm_b = math.sqrt(sum(value * value for value in b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return clamp(dot / (norm_a * norm_b), 0.0, 1.0)


def text_similarity(a: str, b: str) -> float:
    return cosine_similarity_from_counters(tokenize(a), tokenize(b))


def weighted_item_similarity(
    a: SignalItem,
    b: SignalItem,
    config: SignalFilterConfig,
) -> float:
    title_score = text_similarity(a.title, b.title)
    body_score = text_similarity(a.body, b.body)
    return (
        config.title_similarity_weight * title_score
        + config.body_similarity_weight * body_score
    )


def vector_cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return clamp(dot / (norm_a * norm_b), -1.0, 1.0)


def recency_weight(age_days: float, half_life_days: float) -> float:
    if half_life_days <= 0:
        raise ValueError("half_life_days must be positive")
    if age_days <= 0:
        return 1.0
    return math.exp(-math.log(2.0) * age_days / half_life_days)


def infer_age_days(published_at: datetime | None, now: datetime | None = None) -> float | None:
    if published_at is None:
        return None
    current = now or utc_now()
    published = published_at
    if published.tzinfo is None:
        published = published.replace(tzinfo=UTC)
    delta = current - published.astimezone(UTC)
    return max(0.0, delta.total_seconds() / 86400.0)


def contains_denylisted_phrase(text: str, denylist: Sequence[str]) -> str | None:
    normalized = normalize_for_matching(text)
    for phrase in denylist:
        normalized_phrase = normalize_for_matching(phrase)
        if normalized_phrase and normalized_phrase in normalized:
            return phrase
    return None


def split_sentences(text: str) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []
    return [sentence.strip() for sentence in _SENTENCE_RE.split(normalized) if sentence.strip()]


def short_text(text: str, limit: int = 220) -> str:
    normalized = normalize_text(text)
    if len(normalized) <= limit:
        return normalized
    truncated = normalized[: limit - 1].rsplit(" ", 1)[0]
    return f"{truncated}…"


def source_type_from_value(value: str | SourceType | None) -> SourceType:
    if isinstance(value, SourceType):
        return value
    normalized = normalize_for_matching(value or "").replace(" ", "_")
    aliases = {
        "news": SourceType.NEWS,
        "article": SourceType.NEWS,
        "press_release": SourceType.NEWS,
        "blog": SourceType.BLOG,
        "technical_blog": SourceType.BLOG,
        "repo": SourceType.REPO,
        "repository": SourceType.REPO,
        "github": SourceType.REPO,
        "academic": SourceType.RESEARCH_PAPER,
        "arxiv": SourceType.RESEARCH_PAPER,
        "paper": SourceType.RESEARCH_PAPER,
        "research_paper": SourceType.RESEARCH_PAPER,
        "documentation": SourceType.DOCUMENTATION,
        "docs": SourceType.DOCUMENTATION,
        "report": SourceType.REPORT,
        "industry_report": SourceType.REPORT,
        "community": SourceType.COMMUNITY,
        "forum": SourceType.COMMUNITY,
        "reddit": SourceType.COMMUNITY,
    }
    return aliases.get(normalized, SourceType.OTHER)


def criterion_score(
    score: int,
    confidence: float,
    rationale: str,
    evidence: Iterable[str] = (),
) -> CriterionScore:
    return CriterionScore(
        score=int(score),
        confidence=float(confidence),
        rationale=normalize_text(rationale),
        evidence=[normalize_text(item) for item in evidence if normalize_text(item)],
    )


def _serialize_dataclass(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "__dataclass_fields__"):
        return {key: _serialize_dataclass(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _serialize_dataclass(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_serialize_dataclass(item) for item in value]
    return value


# =============================================================================
# Default heuristics — replace with AI/data providers in production
# =============================================================================


_GENERIC_METHOD_PATTERNS = [
    r"\bwe (propose|present|introduce)\b.*\b(architecture|method|approach|framework|technique)\b",
    r"\bbenchmark(ing)?\b",
    r"\bablation\b",
    r"\bstate[- ]of[- ]the[- ]art\b",
]

_WORKFLOW_TERMS = {
    "campaign": "marketing",
    "crm": "sales",
    "support ticket": "customer support",
    "ticket": "customer support",
    "sales": "sales",
    "marketing": "marketing",
    "analytics": "analytics",
    "dashboard": "analytics",
    "pipeline": "engineering",
    "workflow": "operations",
    "repository": "engineering",
    "developer": "engineering",
    "compliance": "legal/compliance",
    "partner": "partnerships",
    "customer": "product/customer success",
}


def default_source_classifier(
    item: SignalItem,
    context: FilterContext,
) -> tuple[SourceType, float, str]:
    del context
    url = (item.metadata.source_url or "").lower()
    domain = item.metadata.domain or extract_domain(url) or ""
    text = f"{item.title} {item.body}".lower()

    if "github.com" in domain or item.metadata.repository_full_name:
        return SourceType.REPO, 0.99, "Repository metadata or GitHub domain detected."
    if item.metadata.doi or "arxiv.org" in domain or re.search(r"\b(abstract|methodology|references)\b", text):
        return SourceType.RESEARCH_PAPER, 0.90, "Research-paper metadata or structure detected."
    if "/docs" in url or domain.startswith("docs.") or "documentation" in text[:500]:
        return SourceType.DOCUMENTATION, 0.88, "Documentation URL or content structure detected."
    if re.search(r"\b(press release|announced|newsroom)\b", text[:600]):
        return SourceType.NEWS, 0.82, "News or announcement language detected."
    if re.search(r"\b(blog|opinion|by [a-z])\b", text[:400]):
        return SourceType.BLOG, 0.75, "Blog-like structure detected."
    return item.metadata.source_type, 0.60, "Retained supplied source type due to limited deterministic evidence."


def default_product_implication_classifier(
    item: SignalItem,
    context: FilterContext,
) -> tuple[str | None, float, list[str]]:
    del context
    text = normalize_text(f"{item.title}. {item.body}")
    lowered = text.lower()

    affected_teams = sorted({team for term, team in _WORKFLOW_TERMS.items() if term in lowered})
    concrete_patterns = {
        "cost": r"\b(cost|spend|price|cheaper|reduce expenses?)\b",
        "time": r"\b(time|latency|faster|hours?|days?|productivity)\b",
        "automation": r"\b(automat(?:e|ion)|workflow|agent|copilot)\b",
        "quality": r"\b(accuracy|quality|reliability|precision|recall|error rate)\b",
        "market": r"\b(launch|release|availability|partnership|acquisition|funding)\b",
        "risk": r"\b(risk|security|privacy|compliance|regulation)\b",
        "adoption": r"\b(adoption|customers?|users?|downloads?|stars?)\b",
    }
    matched = [label for label, pattern in concrete_patterns.items() if re.search(pattern, lowered)]
    generic_method = any(re.search(pattern, lowered) for pattern in _GENERIC_METHOD_PATTERNS)

    if not affected_teams and not matched and generic_method:
        return None, 0.78, []
    if not affected_teams and not matched:
        return None, 0.52, []

    team_text = ", ".join(affected_teams[:3]) if affected_teams else "product and engineering teams"
    evidence = []
    for sentence in split_sentences(text):
        if any(term in sentence.lower() for term in matched) or any(term in sentence.lower() for term in _WORKFLOW_TERMS):
            evidence.append(short_text(sentence, 180))
        if len(evidence) >= 2:
            break

    implication = (
        f"{team_text.capitalize()} should evaluate whether this development changes "
        f"their {'/'.join(matched[:3]) or 'workflow'} decisions: {short_text(item.title, 120)}"
    )
    confidence = 0.82 if affected_teams and matched else 0.66
    return implication, confidence, affected_teams


def default_claim_extractor(item: SignalItem, context: FilterContext) -> list[ExtractedClaim]:
    del context
    claims: list[ExtractedClaim] = []
    for index, sentence in enumerate(split_sentences(item.body)):
        lowered = sentence.lower()
        has_number = bool(_NUMBER_RE.search(sentence))
        has_claim_verb = bool(
            re.search(
                r"\b(announced|launched|released|reported|achieved|increased|reduced|supports|enables|acquired|raised|partnered|grew|declined)\b",
                lowered,
            )
        )
        if not has_number and not has_claim_verb:
            continue
        claim_type = "numeric" if has_number else "factual"
        claims.append(
            ExtractedClaim(
                claim_id=f"{item.item_id}-claim-{index + 1}",
                claim_text=short_text(sentence, 350),
                evidence_text=sentence,
                evidence_location=f"body_sentence_{index + 1}",
                confidence=0.72 if has_number and has_claim_verb else 0.62,
                claim_type=claim_type,
                verifiability=Verifiability.VERIFIABLE,
                support_status=SupportStatus.SUPPORTED,
                numeric_values=_NUMBER_RE.findall(sentence),
            )
        )
        if len(claims) >= 8:
            break
    return claims


def _metadata_completeness(item: SignalItem) -> float:
    fields = [
        item.metadata.source_url,
        item.metadata.source_name,
        item.metadata.author,
        item.metadata.published_at,
        item.metadata.domain,
    ]
    return sum(value is not None and value != "" for value in fields) / len(fields)


def default_credibility_assessment(item: SignalItem) -> CredibilityAssessment:
    source_type = item.metadata.source_type
    completeness = _metadata_completeness(item)
    primary = 1.0 if item.metadata.is_primary_source else 0.45
    evidence_quality = 0.50
    authority = 0.50
    recency_component = item.recency_weight
    rationale_parts: list[str] = []
    evidence: list[str] = []

    if source_type == SourceType.NEWS:
        authority = 0.72 if item.metadata.author else 0.55
        evidence_quality = 0.72 if item.claims else 0.45
        rationale_parts.append("News credibility considers author, metadata, evidence, and primary-source proximity.")
    elif source_type == SourceType.BLOG:
        authority = 0.82 if item.metadata.is_primary_source else 0.50
        evidence_quality = 0.66 if item.claims else 0.42
        rationale_parts.append("Blog credibility is higher for official company sources with concrete evidence.")
    elif source_type == SourceType.REPO:
        stars = float(item.metadata.extra.get("stars", 0) or 0)
        recent_commits = float(item.metadata.extra.get("commits_last_90d", 0) or 0)
        archived = bool(item.metadata.extra.get("archived", False))
        authority = clamp(math.log10(stars + 1) / 5.0, 0.20, 0.90)
        evidence_quality = clamp(recent_commits / 30.0, 0.20, 0.90)
        if archived:
            authority *= 0.60
            evidence_quality *= 0.50
            evidence.append("Repository is archived.")
        rationale_parts.append("Repository credibility considers activity, maintenance, adoption, and archived status.")
    elif source_type == SourceType.RESEARCH_PAPER:
        peer_reviewed = bool(item.metadata.extra.get("peer_reviewed", False))
        citations = float(item.metadata.extra.get("citation_count", 0) or 0)
        code_available = bool(item.metadata.extra.get("code_available", False))
        authority = 0.82 if peer_reviewed else 0.62
        evidence_quality = 0.60 + min(0.25, math.log10(citations + 1) / 12.0)
        if code_available:
            evidence_quality += 0.08
            evidence.append("Code or reproducibility artifact is available.")
        rationale_parts.append("Research credibility considers review status, citations, and reproducibility.")
    elif source_type == SourceType.DOCUMENTATION:
        authority = 0.92 if item.metadata.is_primary_source else 0.58
        evidence_quality = 0.75
        rationale_parts.append("Official, current documentation is treated as strong product evidence.")
    elif source_type == SourceType.REPORT:
        authority = 0.70
        evidence_quality = 0.70 if item.claims else 0.50
        rationale_parts.append("Report credibility considers methodology, named authorship, and evidence density.")
    elif source_type == SourceType.COMMUNITY:
        authority = 0.35
        evidence_quality = 0.35
        rationale_parts.append("Community content is useful as a signal but generally requires corroboration.")
    else:
        rationale_parts.append("Limited source-type evidence; credibility is conservatively scored.")

    components = {
        "source_authority": clamp(authority, 0.0, 1.0),
        "evidence_quality": clamp(evidence_quality, 0.0, 1.0),
        "primary_source_proximity": clamp(primary, 0.0, 1.0),
        "metadata_completeness": clamp(completeness, 0.0, 1.0),
        "recency": clamp(recency_component, 0.0, 1.0),
    }
    weighted = (
        0.30 * components["source_authority"]
        + 0.27 * components["evidence_quality"]
        + 0.20 * components["primary_source_proximity"]
        + 0.13 * components["metadata_completeness"]
        + 0.10 * components["recency"]
    )
    score = int(round(clamp(weighted * 5.0, 0.0, 5.0)))
    confidence = 0.82 if completeness >= 0.6 else 0.62
    return CredibilityAssessment(
        score=score,
        confidence=confidence,
        rationale=" ".join(rationale_parts),
        components=components,
        evidence=evidence,
    )


def default_novelty_assessment(
    item: SignalItem,
    historical_items: Sequence[SignalItem],
    config: SignalFilterConfig,
) -> NoveltyAssessment:
    if not historical_items:
        return NoveltyAssessment(
            novelty_type=NoveltyType.NEW_EVENT,
            score=4,
            confidence=0.64,
            rationale="No historical comparison items were available; treated as provisionally new.",
            new_information=[short_text(item.title, 180)],
        )

    best_item: SignalItem | None = None
    best_similarity = 0.0
    for previous in historical_items:
        similarity = weighted_item_similarity(item, previous, config)
        if similarity > best_similarity:
            best_similarity = similarity
            best_item = previous

    if best_similarity >= config.lexical_duplicate_threshold:
        return NoveltyAssessment(
            novelty_type=NoveltyType.REPEATED_COVERAGE,
            score=1,
            confidence=0.84,
            rationale=f"Highly similar historical signal found (similarity={best_similarity:.2f}).",
            previous_reference_ids=[best_item.item_id] if best_item else [],
        )
    if best_similarity >= 0.60:
        return NoveltyAssessment(
            novelty_type=NoveltyType.MATERIAL_UPDATE,
            score=3,
            confidence=0.70,
            rationale=f"Related historical signal exists, but current content contains additional detail (similarity={best_similarity:.2f}).",
            previous_reference_ids=[best_item.item_id] if best_item else [],
            new_information=[short_text(item.title, 180)],
        )
    return NoveltyAssessment(
        novelty_type=NoveltyType.NEW_EVENT,
        score=4,
        confidence=0.76,
        rationale=f"No close historical match found (highest similarity={best_similarity:.2f}).",
        previous_reference_ids=[best_item.item_id] if best_item else [],
        new_information=[short_text(item.title, 180)],
    )


def default_momentum_assessment(item: SignalItem) -> tuple[int, float, str, list[str]]:
    extra = item.metadata.extra
    evidence: list[str] = []

    growth_values = []
    for key in (
        "star_growth_30d",
        "download_growth_30d",
        "citation_growth_90d",
        "engagement_growth_7d",
        "customer_growth",
    ):
        raw = extra.get(key)
        if isinstance(raw, (int, float)) and math.isfinite(float(raw)):
            growth_values.append(float(raw))
            evidence.append(f"{key}={raw}")

    confirmations = extra.get("independent_confirmations", 0)
    if isinstance(confirmations, (int, float)) and confirmations:
        evidence.append(f"independent_confirmations={confirmations}")

    if not growth_values and not confirmations:
        return 1, 0.35, "No reliable trend series was available; momentum remains low-confidence.", []

    average_growth = statistics.fmean(growth_values) if growth_values else 0.0
    if average_growth >= 50 or confirmations >= 5:
        score = 5
    elif average_growth >= 20 or confirmations >= 3:
        score = 4
    elif average_growth >= 5 or confirmations >= 2:
        score = 3
    elif average_growth > 0 or confirmations >= 1:
        score = 2
    else:
        score = 1
    return score, 0.78, "Momentum is based on measurable growth or independent confirmation signals.", evidence


def default_scorer(item: SignalItem, context: FilterContext) -> SignalScores:
    brief = normalize_for_matching(context.brief or "")
    text = normalize_for_matching(f"{item.title} {item.body}")

    business_terms = {
        "marketing",
        "sales",
        "customer",
        "revenue",
        "product",
        "engineering",
        "analytics",
        "operations",
        "partnership",
        "compliance",
        "cost",
        "workflow",
        "strategy",
    }
    matched_business = sorted(term for term in business_terms if term in text)
    brief_overlap = text_similarity(brief, text) if brief else 0.0
    business_score = min(5, 1 + min(3, len(matched_business)) + (1 if brief_overlap >= 0.25 else 0))
    business_confidence = 0.78 if matched_business or brief else 0.55

    action_terms = {
        "launch",
        "release",
        "available",
        "integrate",
        "pilot",
        "test",
        "compare",
        "monitor",
        "contact",
        "migrate",
        "update",
        "adopt",
        "partner",
    }
    matched_actions = sorted(term for term in action_terms if term in text)
    action_score = min(5, 2 + min(3, len(matched_actions))) if matched_actions else 2

    novelty = item.novelty or NoveltyAssessment(
        novelty_type=NoveltyType.UNKNOWN,
        score=3,
        confidence=0.45,
        rationale="Novelty provider was unavailable.",
    )
    credibility = item.credibility or default_credibility_assessment(item)
    momentum_score, momentum_confidence, momentum_rationale, momentum_evidence = default_momentum_assessment(item)
    item.momentum_evidence = momentum_evidence

    return SignalScores(
        business_relevance=criterion_score(
            business_score,
            business_confidence,
            "Business relevance reflects workflow/team terms and alignment with the supplied brief.",
            matched_business[:5],
        ),
        actionability=criterion_score(
            action_score,
            0.72 if matched_actions else 0.48,
            "Actionability reflects whether the item supports a concrete next step.",
            matched_actions[:5],
        ),
        novelty=criterion_score(
            novelty.score,
            novelty.confidence,
            novelty.rationale,
            novelty.new_information,
        ),
        credibility=criterion_score(
            credibility.score,
            credibility.confidence,
            credibility.rationale,
            credibility.evidence,
        ),
        momentum=criterion_score(
            momentum_score,
            momentum_confidence,
            momentum_rationale,
            momentum_evidence,
        ),
    )


def default_generator(item: SignalItem, context: FilterContext) -> GeneratedSignalFields:
    del context
    claims = [claim.claim_text for claim in item.claims if claim.support_status != SupportStatus.UNSUPPORTED]
    summary_source = claims[0] if claims else split_sentences(item.body)[0] if split_sentences(item.body) else item.body
    implication = item.product_implication or "The signal may affect product or operational decisions."

    action = "monitor"
    text = normalize_for_matching(f"{item.title} {item.body}")
    if any(term in text for term in ("launch", "available", "release", "integration")):
        action = "validate"
    if any(term in text for term in ("security", "risk", "regulation", "compliance")):
        action = "escalate"
    if item.metadata.source_type == SourceType.REPO:
        action = "pilot"

    citation = item.canonical_url or item.metadata.source_url
    return GeneratedSignalFields(
        headline=short_text(item.title, 140),
        summary=short_text(summary_source, 300),
        why_it_matters=short_text(implication, 300),
        the_move=short_text(
            f"{action.capitalize()} this signal with {', '.join(item.affected_teams[:3]) or 'the relevant owner'} and document a specific decision or follow-up.",
            280,
        ),
        recommended_action=action,
        affected_teams=item.affected_teams[:],
        key_entities=_extract_simple_entities(item.title + " " + item.body)[:10],
        key_claims=claims[:5],
        risks_or_caveats=_default_caveats(item),
        source_citations=[citation] if citation else [],
    )


def default_regenerator(
    item: SignalItem,
    field_name: str,
    failure_reason: str,
    context: FilterContext,
) -> str:
    del context
    generated = item.generated
    if generated is None:
        raise ValueError("Cannot regenerate before fields are generated")

    team = ", ".join(item.affected_teams[:2]) or "the relevant team"
    alternatives = {
        "why_it_matters": (
            f"This matters to {team} because it may change a concrete workflow, cost, quality, "
            f"or competitive decision associated with {short_text(item.title, 110)}."
        ),
        "the_move": (
            f"Assign {team} to verify the source evidence, compare it with the current roadmap, "
            "and record a go/no-go, monitor, or pilot decision."
        ),
        "headline": short_text(f"New signal: {item.title}", 140),
        "summary": short_text(
            next((claim.claim_text for claim in item.claims if claim.evidence_text), item.body),
            300,
        ),
    }
    replacement = alternatives.get(field_name)
    if replacement is None:
        replacement = short_text(f"Rewritten because {failure_reason}: {getattr(generated, field_name)}", 280)
    return replacement


def default_event_key(item: SignalItem, context: FilterContext) -> str | None:
    del context
    entities = _extract_simple_entities(item.title)
    event_terms = re.findall(
        r"\b(launch(?:es|ed)?|release(?:s|d)?|announce(?:s|d)?|acquire(?:s|d)?|partner(?:s|ed)?|funding|raises?|general availability|preview)\b",
        item.title.lower(),
    )
    if not entities and not event_terms:
        return None
    date_part = item.metadata.published_at.date().isoformat() if item.metadata.published_at else "unknown-date"
    return stable_hash("|".join(entities[:3]), "|".join(event_terms[:2]), date_part)[:20]


def _extract_simple_entities(text: str) -> list[str]:
    candidates = re.findall(r"\b(?:[A-Z][A-Za-z0-9&.-]+(?:\s+[A-Z][A-Za-z0-9&.-]+){0,3})\b", text)
    stop = {"The", "This", "That", "New", "For", "With", "From", "And", "But"}
    seen: set[str] = set()
    result: list[str] = []
    for candidate in candidates:
        candidate = candidate.strip()
        if candidate in stop or len(candidate) < 3:
            continue
        key = candidate.lower()
        if key not in seen:
            seen.add(key)
            result.append(candidate)
    return result


def _default_caveats(item: SignalItem) -> list[str]:
    caveats: list[str] = []
    if item.metadata.source_type == SourceType.COMMUNITY:
        caveats.append("Community evidence should be corroborated with a primary or authoritative source.")
    if item.credibility and item.credibility.score <= 2:
        caveats.append("Credibility is below the preferred production threshold.")
    if item.novelty and item.novelty.novelty_type == NoveltyType.REPEATED_COVERAGE:
        caveats.append("The item substantially overlaps previously observed intelligence.")
    if any(claim.support_status == SupportStatus.UNSUPPORTED for claim in item.claims):
        caveats.append("One or more extracted claims were marked unsupported.")
    return caveats


# =============================================================================
# Pipeline implementation
# =============================================================================


class SignalFilterPipeline:
    """Production-oriented orchestration while remaining dependency-free."""

    def __init__(
        self,
        config: SignalFilterConfig | None = None,
        *,
        embedding_provider: EmbeddingProvider | None = None,
        historical_repository: HistoricalRepository | None = None,
        momentum_provider: MomentumProvider | None = None,
        product_implication_fn: ProductImplicationFn = default_product_implication_classifier,
        claim_extractor_fn: ClaimExtractorFn = default_claim_extractor,
        scorer_fn: ScorerFn = default_scorer,
        generator_fn: GeneratorFn = default_generator,
        regenerator_fn: RegeneratorFn = default_regenerator,
        event_key_fn: EventKeyFn = default_event_key,
        source_classifier_fn: SourceClassifierFn = default_source_classifier,
    ) -> None:
        self.config = config or SignalFilterConfig()
        self.config.validate()
        self.embedding_provider = embedding_provider
        self.historical_repository = historical_repository
        self.momentum_provider = momentum_provider
        self.product_implication_fn = product_implication_fn
        self.claim_extractor_fn = claim_extractor_fn
        self.scorer_fn = scorer_fn
        self.generator_fn = generator_fn
        self.regenerator_fn = regenerator_fn
        self.event_key_fn = event_key_fn
        self.source_classifier_fn = source_classifier_fn

    async def run(
        self,
        items: Sequence[SignalItem],
        context: FilterContext | None = None,
    ) -> FilterRunResult:
        """Async version of the signal filtering pipeline."""
        # Run in thread pool to not block event loop since this is CPU-intensive
        import asyncio
        return await asyncio.to_thread(self._run_sync, items, context)
    
    def _run_sync(
        self,
        items: Sequence[SignalItem],
        context: FilterContext | None = None,
    ) -> FilterRunResult:
        ctx = context or FilterContext()
        metrics = FilterRunMetrics(run_id=ctx.run_id, started_at=utc_now(), candidate_count=len(items))
        decisions: list[FilterDecision] = []
        active = list(items)
        rejected: list[SignalItem] = []
        review: list[SignalItem] = []
        volume_cut: list[SignalItem] = []

        active = self._normalize_stage(active, ctx, decisions, metrics)
        active, newly_rejected = self._metadata_validation_stage(active, ctx, decisions, metrics)
        rejected.extend(newly_rejected)

        active, newly_rejected = self._exact_dedup_stage(active, ctx, decisions, metrics)
        rejected.extend(newly_rejected)
        active, newly_rejected = self._lexical_dedup_stage(active, ctx, decisions, metrics)
        rejected.extend(newly_rejected)
        active, newly_rejected = self._semantic_dedup_stage(active, ctx, decisions, metrics)
        rejected.extend(newly_rejected)

        active = self._event_clustering_stage(active, ctx, decisions, metrics)
        active = self._source_classification_stage(active, ctx, decisions, metrics)

        active, newly_rejected, newly_review = self._product_implication_stage(active, ctx, decisions, metrics)
        rejected.extend(newly_rejected)
        review.extend(newly_review)

        active = self._claim_extraction_stage(active, ctx, decisions, metrics)
        active = self._recency_stage(active, ctx, decisions, metrics)
        active = self._credibility_stage(active, ctx, decisions, metrics)
        active = self._historical_novelty_stage(active, ctx, decisions, metrics)
        active = self._scoring_stage(active, ctx, decisions, metrics)

        active, newly_rejected, newly_review = self._score_and_confidence_decision_stage(
            active, ctx, decisions, metrics
        )
        rejected.extend(newly_rejected)
        review.extend(newly_review)

        active, diversity_cut = self._diversity_ranking_stage(active, ctx, decisions, metrics)
        volume_cut.extend(diversity_cut)
        active, cap_cut = self._volume_cap_stage(active, ctx, decisions, metrics)
        volume_cut.extend(cap_cut)

        active = self._generation_stage(active, ctx, decisions, metrics)
        active, newly_review = self._language_qa_and_regeneration_stage(
            active, ctx, decisions, metrics
        )
        review.extend(newly_review)

        accepted: list[SignalItem] = []
        for item in active:
            if item.status == DecisionStatus.REVIEW:
                review.append(item)
                continue
            item.status = DecisionStatus.ACCEPT
            item.updated_at = utc_now()
            accepted.append(item)
            decisions.append(
                self._decision(
                    item,
                    "finalization",
                    DecisionStatus.ACCEPT,
                    ReasonCode.ACCEPTED,
                    "Item passed all enabled gates and QA checks.",
                    confidence=item.overall_confidence,
                    context=ctx,
                )
            )

        # De-duplicate queues by item_id while preserving order.
        accepted = _unique_items(accepted)
        rejected = _unique_items(rejected)
        review = _unique_items([item for item in review if item.item_id not in {x.item_id for x in accepted}])
        volume_cut = _unique_items(volume_cut)

        metrics.accepted_count = len(accepted)
        metrics.rejected_count = len(rejected)
        metrics.review_count = len(review)
        metrics.volume_cut_count = len(volume_cut)
        metrics.duplicate_count = sum(
            decision.reason_code
            in {ReasonCode.EXACT_DUPLICATE, ReasonCode.LEXICAL_DUPLICATE, ReasonCode.SEMANTIC_DUPLICATE}
            for decision in decisions
        )
        metrics.completed_at = utc_now()

        return FilterRunResult(
            run_id=ctx.run_id,
            accepted=accepted,
            rejected=rejected,
            review=review,
            volume_cut=volume_cut,
            decisions=decisions,
            metrics=metrics,
        )

    # ------------------------------------------------------------------
    # Stage helpers
    # ------------------------------------------------------------------

    def _decision(
        self,
        item: SignalItem,
        stage: str,
        status: DecisionStatus,
        reason_code: ReasonCode,
        explanation: str,
        *,
        threshold: float | int | None = None,
        observed_value: float | int | str | None = None,
        confidence: float | None = None,
        duration_ms: float | None = None,
        context: FilterContext,
    ) -> FilterDecision:
        return FilterDecision(
            item_id=item.item_id,
            stage=stage,
            decision=status,
            reason_code=reason_code,
            explanation=explanation,
            threshold=threshold,
            observed_value=observed_value,
            config_version=self.config.config_version,
            model_version=context.model_version,
            prompt_version=context.prompt_version,
            confidence=confidence,
            duration_ms=duration_ms,
        )

    def _record_stage_metrics(
        self,
        metrics: FilterRunMetrics,
        stage: str,
        input_count: int,
        output_count: int,
        start: float,
        *,
        rejected_count: int = 0,
        review_count: int = 0,
        warning_count: int = 0,
    ) -> None:
        metrics.stage_metrics.append(
            StageMetrics(
                stage=stage,
                input_count=input_count,
                output_count=output_count,
                rejected_count=rejected_count,
                review_count=review_count,
                warning_count=warning_count,
                duration_ms=(time.perf_counter() - start) * 1000.0,
            )
        )

    # ------------------------------------------------------------------
    # Stages
    # ------------------------------------------------------------------

    def _normalize_stage(
        self,
        items: list[SignalItem],
        context: FilterContext,
        decisions: list[FilterDecision],
        metrics: FilterRunMetrics,
    ) -> list[SignalItem]:
        stage = "normalize"
        start = time.perf_counter()
        for item in items:
            item.raw_title = item.raw_title or item.title
            item.raw_body = item.raw_body or item.body
            item.title = normalize_text(item.title)
            item.body = normalize_text(item.body)
            item.metadata.source_name = normalize_text(item.metadata.source_name or "") or None
            item.metadata.author = normalize_text(item.metadata.author or "") or None
            item.metadata.source_type = source_type_from_value(item.metadata.source_type)
            item.category = normalize_for_matching(item.category or item.metadata.source_type.value).replace(" ", "_")
            item.canonical_url = canonicalize_url(item.metadata.source_url)
            item.metadata.domain = item.metadata.domain or extract_domain(item.canonical_url)
            item.normalized_text = normalize_for_matching(f"{item.title} {item.body}")
            item.content_hash = stable_hash(item.title, item.body)
            item.updated_at = utc_now()
            decisions.append(
                self._decision(
                    item,
                    stage,
                    DecisionStatus.PASS,
                    ReasonCode.NORMALIZED,
                    "Text, URL, source type, category, domain, and content fingerprint were normalized.",
                    context=context,
                )
            )
        self._record_stage_metrics(metrics, stage, len(items), len(items), start)
        return items

    def _metadata_validation_stage(
        self,
        items: list[SignalItem],
        context: FilterContext,
        decisions: list[FilterDecision],
        metrics: FilterRunMetrics,
    ) -> tuple[list[SignalItem], list[SignalItem]]:
        stage = "metadata_validation"
        start = time.perf_counter()
        survivors: list[SignalItem] = []
        rejected: list[SignalItem] = []
        for item in items:
            problems = []
            if not item.title:
                problems.append("title is empty")
            if not item.body:
                problems.append("body is empty")
            if len(item.body) < 20:
                problems.append("body is too short")
            if item.metadata.published_at and item.metadata.published_at.year < 1990:
                problems.append("published_at appears invalid")

            if problems:
                item.status = DecisionStatus.REJECT
                rejected.append(item)
                decisions.append(
                    self._decision(
                        item,
                        stage,
                        DecisionStatus.REJECT,
                        ReasonCode.METADATA_INVALID,
                        "; ".join(problems),
                        context=context,
                    )
                )
            else:
                survivors.append(item)
                decisions.append(
                    self._decision(
                        item,
                        stage,
                        DecisionStatus.PASS,
                        ReasonCode.METADATA_VALID,
                        "Required title/body metadata is valid.",
                        context=context,
                    )
                )
        self._record_stage_metrics(
            metrics, stage, len(items), len(survivors), start, rejected_count=len(rejected)
        )
        return survivors, rejected

    def _exact_dedup_stage(
        self,
        items: list[SignalItem],
        context: FilterContext,
        decisions: list[FilterDecision],
        metrics: FilterRunMetrics,
    ) -> tuple[list[SignalItem], list[SignalItem]]:
        stage = "exact_dedup"
        start = time.perf_counter()
        if not self.config.exact_duplicate_enabled:
            self._record_stage_metrics(metrics, stage, len(items), len(items), start)
            return items, []

        survivors: list[SignalItem] = []
        rejected: list[SignalItem] = []
        keys: dict[str, SignalItem] = {}
        for item in _prefer_best_sources(items):
            candidate_keys = [
                item.canonical_url,
                item.metadata.source_native_id,
                item.metadata.doi,
                item.metadata.repository_full_name,
                item.content_hash,
            ]
            duplicate = next((keys[key] for key in candidate_keys if key and key in keys), None)
            if duplicate:
                item.status = DecisionStatus.REJECT
                item.duplicate_of_item_id = duplicate.item_id
                item.duplicate_similarity = 1.0
                rejected.append(item)
                decisions.append(
                    self._decision(
                        item,
                        stage,
                        DecisionStatus.REJECT,
                        ReasonCode.EXACT_DUPLICATE,
                        f"Exact duplicate of '{duplicate.title}'.",
                        threshold=1.0,
                        observed_value=1.0,
                        confidence=1.0,
                        context=context,
                    )
                )
                continue
            survivors.append(item)
            for key in candidate_keys:
                if key:
                    keys[key] = item

        self._record_stage_metrics(
            metrics, stage, len(items), len(survivors), start, rejected_count=len(rejected)
        )
        return survivors, rejected

    def _lexical_dedup_stage(
        self,
        items: list[SignalItem],
        context: FilterContext,
        decisions: list[FilterDecision],
        metrics: FilterRunMetrics,
    ) -> tuple[list[SignalItem], list[SignalItem]]:
        stage = "lexical_dedup"
        start = time.perf_counter()
        if not self.config.lexical_dedup_enabled:
            self._record_stage_metrics(metrics, stage, len(items), len(items), start)
            return items, []

        survivors: list[SignalItem] = []
        rejected: list[SignalItem] = []
        for candidate in _prefer_best_sources(items):
            best_match: SignalItem | None = None
            best_similarity = 0.0
            for existing in survivors:
                similarity = weighted_item_similarity(candidate, existing, self.config)
                if similarity > best_similarity:
                    best_match = existing
                    best_similarity = similarity
            if best_match and best_similarity >= self.config.lexical_duplicate_threshold:
                candidate.status = DecisionStatus.REJECT
                candidate.duplicate_of_item_id = best_match.item_id
                candidate.duplicate_similarity = best_similarity
                rejected.append(candidate)
                decisions.append(
                    self._decision(
                        candidate,
                        stage,
                        DecisionStatus.REJECT,
                        ReasonCode.LEXICAL_DUPLICATE,
                        f"Near-duplicate of '{best_match.title}' using weighted title/body similarity.",
                        threshold=self.config.lexical_duplicate_threshold,
                        observed_value=round(best_similarity, 4),
                        confidence=0.90,
                        context=context,
                    )
                )
            else:
                survivors.append(candidate)

        self._record_stage_metrics(
            metrics, stage, len(items), len(survivors), start, rejected_count=len(rejected)
        )
        return survivors, rejected

    def _semantic_dedup_stage(
        self,
        items: list[SignalItem],
        context: FilterContext,
        decisions: list[FilterDecision],
        metrics: FilterRunMetrics,
    ) -> tuple[list[SignalItem], list[SignalItem]]:
        stage = "semantic_dedup"
        start = time.perf_counter()
        if not self.config.semantic_dedup_enabled or self.embedding_provider is None or len(items) < 2:
            self._record_stage_metrics(metrics, stage, len(items), len(items), start)
            return items, []

        vectors = self.embedding_provider.embed([f"{item.title}\n{item.body}" for item in items])
        if len(vectors) != len(items):
            raise ValueError("Embedding provider returned an unexpected vector count")

        survivors: list[SignalItem] = []
        survivor_vectors: list[list[float]] = []
        rejected: list[SignalItem] = []
        for item, vector in zip(items, vectors):
            best_index: int | None = None
            best_similarity = 0.0
            for index, existing_vector in enumerate(survivor_vectors):
                similarity = vector_cosine_similarity(vector, existing_vector)
                if similarity > best_similarity:
                    best_index = index
                    best_similarity = similarity
            if best_index is not None and best_similarity >= self.config.semantic_duplicate_threshold:
                duplicate = survivors[best_index]
                item.status = DecisionStatus.REJECT
                item.duplicate_of_item_id = duplicate.item_id
                item.duplicate_similarity = best_similarity
                rejected.append(item)
                decisions.append(
                    self._decision(
                        item,
                        stage,
                        DecisionStatus.REJECT,
                        ReasonCode.SEMANTIC_DUPLICATE,
                        f"Semantically equivalent to '{duplicate.title}'.",
                        threshold=self.config.semantic_duplicate_threshold,
                        observed_value=round(best_similarity, 4),
                        confidence=0.90,
                        context=context,
                    )
                )
            else:
                survivors.append(item)
                survivor_vectors.append(vector)

        self._record_stage_metrics(
            metrics, stage, len(items), len(survivors), start, rejected_count=len(rejected)
        )
        return survivors, rejected

    def _event_clustering_stage(
        self,
        items: list[SignalItem],
        context: FilterContext,
        decisions: list[FilterDecision],
        metrics: FilterRunMetrics,
    ) -> list[SignalItem]:
        stage = "event_clustering"
        start = time.perf_counter()
        if not self.config.event_clustering_enabled:
            self._record_stage_metrics(metrics, stage, len(items), len(items), start)
            return items

        for item in items:
            event_key = self.event_key_fn(item, context)
            if event_key:
                item.event_cluster_id = event_key
                decisions.append(
                    self._decision(
                        item,
                        stage,
                        DecisionStatus.PASS,
                        ReasonCode.EVENT_CLUSTERED,
                        f"Assigned to event cluster {event_key}.",
                        context=context,
                    )
                )
        self._record_stage_metrics(metrics, stage, len(items), len(items), start)
        return items

    def _source_classification_stage(
        self,
        items: list[SignalItem],
        context: FilterContext,
        decisions: list[FilterDecision],
        metrics: FilterRunMetrics,
    ) -> list[SignalItem]:
        stage = "source_classification"
        start = time.perf_counter()
        for item in items:
            source_type, confidence, rationale = self.source_classifier_fn(item, context)
            item.metadata.source_type = source_type
            if not item.category or item.category == "other":
                item.category = source_type.value
            decisions.append(
                self._decision(
                    item,
                    stage,
                    DecisionStatus.PASS,
                    ReasonCode.SOURCE_CLASSIFIED,
                    rationale,
                    observed_value=source_type.value,
                    confidence=confidence,
                    context=context,
                )
            )
        self._record_stage_metrics(metrics, stage, len(items), len(items), start)
        return items

    def _product_implication_stage(
        self,
        items: list[SignalItem],
        context: FilterContext,
        decisions: list[FilterDecision],
        metrics: FilterRunMetrics,
    ) -> tuple[list[SignalItem], list[SignalItem], list[SignalItem]]:
        stage = "product_implication"
        start = time.perf_counter()
        survivors: list[SignalItem] = []
        rejected: list[SignalItem] = []
        review: list[SignalItem] = []

        for item in items:
            source_value = item.metadata.source_type.value
            is_technical = source_value in self.config.technical_source_types or item.metadata.source_type in {
                SourceType.RESEARCH_PAPER,
                SourceType.DOCUMENTATION,
            }
            if not is_technical:
                survivors.append(item)
                continue

            implication, confidence, affected_teams = self.product_implication_fn(item, context)
            item.product_implication = implication
            item.product_implication_confidence = confidence
            item.affected_teams = affected_teams

            if implication:
                survivors.append(item)
                decisions.append(
                    self._decision(
                        item,
                        stage,
                        DecisionStatus.PASS,
                        ReasonCode.PRODUCT_IMPLICATION_PRESENT,
                        implication,
                        confidence=confidence,
                        context=context,
                    )
                )
            elif confidence < self.config.implication_review_confidence:
                item.status = DecisionStatus.REVIEW
                review.append(item)
                decisions.append(
                    self._decision(
                        item,
                        stage,
                        DecisionStatus.REVIEW,
                        ReasonCode.PRODUCT_IMPLICATION_LOW_CONFIDENCE,
                        "No reliable implication was generated, but classifier confidence is too low for automatic rejection.",
                        threshold=self.config.implication_review_confidence,
                        observed_value=confidence,
                        confidence=confidence,
                        context=context,
                    )
                )
            else:
                item.status = DecisionStatus.REJECT
                rejected.append(item)
                decisions.append(
                    self._decision(
                        item,
                        stage,
                        DecisionStatus.REJECT,
                        ReasonCode.PRODUCT_IMPLICATION_MISSING,
                        "No concrete product, workflow, cost, quality, market, adoption, or risk implication was identified.",
                        confidence=confidence,
                        context=context,
                    )
                )

        self._record_stage_metrics(
            metrics,
            stage,
            len(items),
            len(survivors),
            start,
            rejected_count=len(rejected),
            review_count=len(review),
        )
        return survivors, rejected, review

    def _claim_extraction_stage(
        self,
        items: list[SignalItem],
        context: FilterContext,
        decisions: list[FilterDecision],
        metrics: FilterRunMetrics,
    ) -> list[SignalItem]:
        stage = "claim_extraction"
        start = time.perf_counter()
        if not self.config.claim_extraction_enabled:
            self._record_stage_metrics(metrics, stage, len(items), len(items), start)
            return items

        for item in items:
            item.claims = self.claim_extractor_fn(item, context)
            decisions.append(
                self._decision(
                    item,
                    stage,
                    DecisionStatus.PASS,
                    ReasonCode.CLAIMS_EXTRACTED,
                    f"Extracted {len(item.claims)} traceable claims.",
                    observed_value=len(item.claims),
                    confidence=statistics.fmean([claim.confidence for claim in item.claims]) if item.claims else 0.40,
                    context=context,
                )
            )
        self._record_stage_metrics(metrics, stage, len(items), len(items), start)
        return items

    def _recency_stage(
        self,
        items: list[SignalItem],
        context: FilterContext,
        decisions: list[FilterDecision],
        metrics: FilterRunMetrics,
    ) -> list[SignalItem]:
        del decisions, context
        stage = "recency"
        start = time.perf_counter()
        for item in items:
            age = infer_age_days(item.metadata.published_at)
            half_life = self.config.recency_half_life_days.get(item.metadata.source_type.value, 30)
            item.recency_weight = recency_weight(age, half_life) if age is not None else 0.55
        self._record_stage_metrics(metrics, stage, len(items), len(items), start)
        return items

    def _credibility_stage(
        self,
        items: list[SignalItem],
        context: FilterContext,
        decisions: list[FilterDecision],
        metrics: FilterRunMetrics,
    ) -> list[SignalItem]:
        stage = "credibility"
        start = time.perf_counter()
        for item in items:
            item.credibility = default_credibility_assessment(item)
            decisions.append(
                self._decision(
                    item,
                    stage,
                    DecisionStatus.PASS,
                    ReasonCode.CREDIBILITY_SCORED,
                    item.credibility.rationale,
                    observed_value=item.credibility.score,
                    confidence=item.credibility.confidence,
                    context=context,
                )
            )
        self._record_stage_metrics(metrics, stage, len(items), len(items), start)
        return items

    def _historical_novelty_stage(
        self,
        items: list[SignalItem],
        context: FilterContext,
        decisions: list[FilterDecision],
        metrics: FilterRunMetrics,
    ) -> list[SignalItem]:
        stage = "historical_novelty"
        start = time.perf_counter()
        for item in items:
            historical = (
                self.historical_repository.find_similar_items(item, limit=10)
                if self.config.historical_novelty_enabled and self.historical_repository
                else []
            )
            item.novelty = default_novelty_assessment(item, historical, self.config)
            decisions.append(
                self._decision(
                    item,
                    stage,
                    DecisionStatus.PASS,
                    ReasonCode.NOVELTY_SCORED,
                    item.novelty.rationale,
                    observed_value=item.novelty.score,
                    confidence=item.novelty.confidence,
                    context=context,
                )
            )
        self._record_stage_metrics(metrics, stage, len(items), len(items), start)
        return items

    def _scoring_stage(
        self,
        items: list[SignalItem],
        context: FilterContext,
        decisions: list[FilterDecision],
        metrics: FilterRunMetrics,
    ) -> list[SignalItem]:
        stage = "scoring"
        start = time.perf_counter()
        for item in items:
            item.scores = self.scorer_fn(item, context)
            item.overall_confidence = self._calculate_overall_confidence(item)
            decisions.append(
                self._decision(
                    item,
                    stage,
                    DecisionStatus.PASS,
                    ReasonCode.SCORE_PASSED,
                    "Scoring completed; threshold decision follows in the next stage.",
                    observed_value=item.scores.total,
                    confidence=item.overall_confidence,
                    context=context,
                )
            )
        self._record_stage_metrics(metrics, stage, len(items), len(items), start)
        return items

    def _calculate_overall_confidence(self, item: SignalItem) -> float:
        values = []
        if item.scores:
            values.append(item.scores.average_confidence)
        if item.credibility:
            values.append(item.credibility.confidence)
        if item.novelty:
            values.append(item.novelty.confidence)
        if item.product_implication_confidence is not None:
            values.append(item.product_implication_confidence)
        if item.claims:
            values.append(statistics.fmean(claim.confidence for claim in item.claims))
        return clamp(statistics.fmean(values), 0.0, 1.0) if values else 0.50

    def _score_and_confidence_decision_stage(
        self,
        items: list[SignalItem],
        context: FilterContext,
        decisions: list[FilterDecision],
        metrics: FilterRunMetrics,
    ) -> tuple[list[SignalItem], list[SignalItem], list[SignalItem]]:
        stage = "threshold_and_confidence"
        start = time.perf_counter()
        survivors: list[SignalItem] = []
        rejected: list[SignalItem] = []
        review: list[SignalItem] = []

        for item in items:
            if item.scores is None:
                item.status = DecisionStatus.REVIEW
                review.append(item)
                decisions.append(
                    self._decision(
                        item,
                        stage,
                        DecisionStatus.REVIEW,
                        ReasonCode.SCORE_INVALID,
                        "Scores are missing.",
                        context=context,
                    )
                )
                continue

            failed_criterion: tuple[str, int, int] | None = None
            for criterion, minimum in self.config.min_scores.items():
                score = item.scores.as_dict()[criterion].score
                if score < minimum:
                    failed_criterion = (criterion, score, minimum)
                    break

            passes = failed_criterion is None and item.scores.total >= self.config.min_total_score
            confidence = item.overall_confidence or 0.0

            if passes and confidence >= self.config.auto_accept_confidence:
                survivors.append(item)
                decisions.append(
                    self._decision(
                        item,
                        stage,
                        DecisionStatus.PASS,
                        ReasonCode.SCORE_PASSED,
                        "All individual and total thresholds passed with high confidence.",
                        threshold=self.config.min_total_score,
                        observed_value=item.scores.total,
                        confidence=confidence,
                        context=context,
                    )
                )
            elif passes and confidence >= self.config.human_review_confidence:
                item.status = DecisionStatus.REVIEW
                review.append(item)
                decisions.append(
                    self._decision(
                        item,
                        stage,
                        DecisionStatus.REVIEW,
                        ReasonCode.LOW_CONFIDENCE,
                        "Scores pass, but confidence is below the automatic acceptance threshold.",
                        threshold=self.config.auto_accept_confidence,
                        observed_value=confidence,
                        confidence=confidence,
                        context=context,
                    )
                )
            elif passes:
                item.status = DecisionStatus.REVIEW
                review.append(item)
                decisions.append(
                    self._decision(
                        item,
                        stage,
                        DecisionStatus.REVIEW,
                        ReasonCode.LOW_CONFIDENCE,
                        "Scores pass, but confidence is too low for an automatic decision.",
                        threshold=self.config.human_review_confidence,
                        observed_value=confidence,
                        confidence=confidence,
                        context=context,
                    )
                )
            elif confidence < self.config.human_review_confidence:
                item.status = DecisionStatus.REVIEW
                review.append(item)
                reason = (
                    f"Criterion {failed_criterion[0]}={failed_criterion[1]} below {failed_criterion[2]}."
                    if failed_criterion
                    else f"Total {item.scores.total} below {self.config.min_total_score}."
                )
                decisions.append(
                    self._decision(
                        item,
                        stage,
                        DecisionStatus.REVIEW,
                        ReasonCode.LOW_CONFIDENCE,
                        f"{reason} Low confidence requires human review rather than automatic rejection.",
                        observed_value=confidence,
                        confidence=confidence,
                        context=context,
                    )
                )
            else:
                item.status = DecisionStatus.REJECT
                rejected.append(item)
                if failed_criterion:
                    criterion, score, minimum = failed_criterion
                    decisions.append(
                        self._decision(
                            item,
                            stage,
                            DecisionStatus.REJECT,
                            ReasonCode.SCORE_CRITERION_BELOW_MINIMUM,
                            f"{criterion}={score} is below minimum {minimum}.",
                            threshold=minimum,
                            observed_value=score,
                            confidence=confidence,
                            context=context,
                        )
                    )
                else:
                    decisions.append(
                        self._decision(
                            item,
                            stage,
                            DecisionStatus.REJECT,
                            ReasonCode.SCORE_TOTAL_BELOW_MINIMUM,
                            f"Total score {item.scores.total} is below minimum {self.config.min_total_score}.",
                            threshold=self.config.min_total_score,
                            observed_value=item.scores.total,
                            confidence=confidence,
                            context=context,
                        )
                    )

        self._record_stage_metrics(
            metrics,
            stage,
            len(items),
            len(survivors),
            start,
            rejected_count=len(rejected),
            review_count=len(review),
        )
        return survivors, rejected, review

    def _diversity_ranking_stage(
        self,
        items: list[SignalItem],
        context: FilterContext,
        decisions: list[FilterDecision],
        metrics: FilterRunMetrics,
    ) -> tuple[list[SignalItem], list[SignalItem]]:
        stage = "diversity_ranking"
        start = time.perf_counter()
        ranked = sorted(items, key=_ranking_score, reverse=True)
        if not self.config.diversity_ranking_enabled:
            self._record_stage_metrics(metrics, stage, len(items), len(ranked), start)
            return ranked, []

        kept: list[SignalItem] = []
        cut: list[SignalItem] = []
        domain_counts: Counter[str] = Counter()
        publisher_counts: Counter[str] = Counter()

        for item in ranked:
            domain = item.metadata.domain or "unknown"
            publisher = item.metadata.source_name or domain
            if domain_counts[domain] >= self.config.max_per_domain:
                item.status = DecisionStatus.QUALIFIED_BUT_CUT_FOR_VOLUME
                cut.append(item)
                decisions.append(
                    self._decision(
                        item,
                        stage,
                        DecisionStatus.QUALIFIED_BUT_CUT_FOR_VOLUME,
                        ReasonCode.DIVERSITY_SUPPRESSED,
                        f"Qualified item suppressed because domain '{domain}' reached the diversity limit.",
                        threshold=self.config.max_per_domain,
                        observed_value=domain_counts[domain],
                        context=context,
                    )
                )
                continue
            if publisher_counts[publisher] >= self.config.max_per_publisher:
                item.status = DecisionStatus.QUALIFIED_BUT_CUT_FOR_VOLUME
                cut.append(item)
                decisions.append(
                    self._decision(
                        item,
                        stage,
                        DecisionStatus.QUALIFIED_BUT_CUT_FOR_VOLUME,
                        ReasonCode.DIVERSITY_SUPPRESSED,
                        f"Qualified item suppressed because publisher '{publisher}' reached the diversity limit.",
                        threshold=self.config.max_per_publisher,
                        observed_value=publisher_counts[publisher],
                        context=context,
                    )
                )
                continue
            kept.append(item)
            domain_counts[domain] += 1
            publisher_counts[publisher] += 1

        self._record_stage_metrics(
            metrics, stage, len(items), len(kept), start, rejected_count=len(cut)
        )
        return kept, cut

    def _volume_cap_stage(
        self,
        items: list[SignalItem],
        context: FilterContext,
        decisions: list[FilterDecision],
        metrics: FilterRunMetrics,
    ) -> tuple[list[SignalItem], list[SignalItem]]:
        stage = "volume_caps"
        start = time.perf_counter()
        grouped: dict[str, list[SignalItem]] = defaultdict(list)
        for item in items:
            grouped[item.category or item.metadata.source_type.value].append(item)

        kept: list[SignalItem] = []
        cut: list[SignalItem] = []
        for category, group in grouped.items():
            cap = self.config.category_caps.get(category, self.config.category_caps.get("other", 5))
            ranked = sorted(group, key=_ranking_score, reverse=True)
            kept.extend(ranked[:cap])
            for item in ranked[cap:]:
                item.status = DecisionStatus.QUALIFIED_BUT_CUT_FOR_VOLUME
                cut.append(item)
                decisions.append(
                    self._decision(
                        item,
                        stage,
                        DecisionStatus.QUALIFIED_BUT_CUT_FOR_VOLUME,
                        ReasonCode.CATEGORY_CAP,
                        f"Qualified but cut because category '{category}' is capped at {cap}.",
                        threshold=cap,
                        observed_value=len(group),
                        context=context,
                    )
                )

        ranked_kept = sorted(kept, key=_ranking_score, reverse=True)
        final = ranked_kept[: self.config.total_item_cap]
        for item in ranked_kept[self.config.total_item_cap :]:
            item.status = DecisionStatus.QUALIFIED_BUT_CUT_FOR_VOLUME
            cut.append(item)
            decisions.append(
                self._decision(
                    item,
                    stage,
                    DecisionStatus.QUALIFIED_BUT_CUT_FOR_VOLUME,
                    ReasonCode.TOTAL_CAP,
                    f"Qualified but cut because the total cap is {self.config.total_item_cap}.",
                    threshold=self.config.total_item_cap,
                    observed_value=len(ranked_kept),
                    context=context,
                )
            )

        self._record_stage_metrics(
            metrics, stage, len(items), len(final), start, rejected_count=len(cut)
        )
        return final, cut

    def _generation_stage(
        self,
        items: list[SignalItem],
        context: FilterContext,
        decisions: list[FilterDecision],
        metrics: FilterRunMetrics,
    ) -> list[SignalItem]:
        stage = "generation"
        start = time.perf_counter()
        for item in items:
            item.generated = self.generator_fn(item, context)
            decisions.append(
                self._decision(
                    item,
                    stage,
                    DecisionStatus.PASS,
                    ReasonCode.GENERATION_COMPLETE,
                    "Generated structured intelligence fields.",
                    context=context,
                )
            )
        self._record_stage_metrics(metrics, stage, len(items), len(items), start)
        return items

    def _language_qa_and_regeneration_stage(
        self,
        items: list[SignalItem],
        context: FilterContext,
        decisions: list[FilterDecision],
        metrics: FilterRunMetrics,
    ) -> tuple[list[SignalItem], list[SignalItem]]:
        stage = "language_qa"
        start = time.perf_counter()
        review: list[SignalItem] = []

        failures = self._collect_qa_failures(items)
        if not failures:
            self._record_stage_metrics(metrics, stage, len(items), len(items), start)
            return items, review

        for item_id, field_name, failure_reason, reason_code in failures:
            item = next(item for item in items if item.item_id == item_id)
            decisions.append(
                self._decision(
                    item,
                    stage,
                    DecisionStatus.WARNING,
                    reason_code,
                    failure_reason,
                    context=context,
                )
            )

        if self.config.auto_regeneration_enabled:
            for _attempt in range(self.config.max_regeneration_attempts):
                if not failures:
                    break
                metrics.regeneration_attempts += len(failures)
                for item_id, field_name, failure_reason, _reason_code in failures:
                    item = next(item for item in items if item.item_id == item_id)
                    if item.generated is None:
                        continue
                    replacement = self.regenerator_fn(item, field_name, failure_reason, context)
                    setattr(item.generated, field_name, replacement)
                failures = self._collect_qa_failures(items)

            unresolved_ids = {item_id for item_id, *_rest in failures}
            for item in items:
                if item.item_id in unresolved_ids:
                    item.status = DecisionStatus.REVIEW
                    review.append(item)
                    decisions.append(
                        self._decision(
                            item,
                            stage,
                            DecisionStatus.REVIEW,
                            ReasonCode.REGENERATION_FAILED,
                            "Generated content still fails QA after targeted regeneration attempts.",
                            context=context,
                        )
                    )
                else:
                    metrics.regeneration_successes += 1
                    decisions.append(
                        self._decision(
                            item,
                            stage,
                            DecisionStatus.PASS,
                            ReasonCode.REGENERATION_SUCCESS,
                            "Generated content passed QA after targeted regeneration or required no further repair.",
                            context=context,
                        )
                    )
        else:
            unresolved_ids = {item_id for item_id, *_rest in failures}
            for item in items:
                if item.item_id in unresolved_ids:
                    item.status = DecisionStatus.REVIEW
                    review.append(item)

        self._record_stage_metrics(
            metrics, stage, len(items), len(items) - len(review), start, review_count=len(review)
        )
        return items, review

    def _collect_qa_failures(
        self,
        items: Sequence[SignalItem],
    ) -> list[tuple[str, str, str, ReasonCode]]:
        failures: list[tuple[str, str, str, ReasonCode]] = []
        fields = ("headline", "summary", "why_it_matters", "the_move")

        for item in items:
            if item.generated is None:
                continue
            for field_name in fields:
                value = getattr(item.generated, field_name)
                denylisted = contains_denylisted_phrase(value, self.config.denylist_phrases)
                if denylisted:
                    failures.append(
                        (
                            item.item_id,
                            field_name,
                            f"Field contains deny-listed phrase: {denylisted}",
                            ReasonCode.DENYLIST_FAILURE,
                        )
                    )

        for field_name in ("why_it_matters", "the_move"):
            for index, item_a in enumerate(items):
                if item_a.generated is None:
                    continue
                for item_b in items[index + 1 :]:
                    if item_b.generated is None:
                        continue
                    similarity = text_similarity(
                        getattr(item_a.generated, field_name),
                        getattr(item_b.generated, field_name),
                    )
                    if similarity >= self.config.uniqueness_similarity_threshold:
                        reason = (
                            f"{field_name} is too similar to another item "
                            f"(similarity={similarity:.2f}, threshold={self.config.uniqueness_similarity_threshold:.2f})."
                        )
                        failures.append((item_b.item_id, field_name, reason, ReasonCode.UNIQUENESS_FAILURE))
        return failures


# =============================================================================
# Compatibility helpers for the original V1 API
# =============================================================================


@dataclass(slots=True)
class LegacyItem:
    title: str
    source: str
    source_type: str
    category: str
    url: str
    raw_text: str
    published_date: str = ""


@dataclass(slots=True)
class LegacyScoredItem:
    item: LegacyItem
    scores: dict[str, int] = field(default_factory=dict)
    total: float = 0.0
    product_implication: str | None = None
    status: str = "accepted"


@dataclass(slots=True)
class LegacyAuditEntry:
    item: LegacyItem
    kept: bool
    gate: str
    reason: str
    scores: dict[str, int] | None = None
    total: float | None = None
    status: str | None = None


def _parse_legacy_date(value: str) -> datetime | None:
    if not value:
        return None
    for candidate in (value, value.replace("Z", "+00:00")):
        try:
            parsed = datetime.fromisoformat(candidate)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def legacy_to_signal(item: LegacyItem) -> SignalItem:
    source_type = source_type_from_value(item.source_type)
    return SignalItem(
        title=item.title,
        body=item.raw_text,
        metadata=SourceMetadata(
            source_url=item.url,
            source_name=item.source,
            source_type=source_type,
            published_at=_parse_legacy_date(item.published_date),
            domain=extract_domain(item.url),
            is_primary_source=source_type in {SourceType.BLOG, SourceType.DOCUMENTATION},
        ),
        category=normalize_for_matching(item.category).replace(" ", "_") or source_type.value,
    )


def run_signal_filtering(
    items: Sequence[LegacyItem],
    *,
    config: SignalFilterConfig | None = None,
    context: FilterContext | None = None,
) -> tuple[list[LegacyScoredItem], list[LegacyAuditEntry]]:
    """Compatibility wrapper for the original V1 function signature."""
    pipeline = SignalFilterPipeline(config=config)
    signal_items = [legacy_to_signal(item) for item in items]
    item_map = {signal.item_id: legacy for signal, legacy in zip(signal_items, items)}
    result = pipeline.run(signal_items, context=context)

    shortlist: list[LegacyScoredItem] = []
    for signal in result.accepted:
        score_dict = {
            name: score.score for name, score in signal.scores.as_dict().items()
        } if signal.scores else {}
        shortlist.append(
            LegacyScoredItem(
                item=item_map[signal.item_id],
                scores=score_dict,
                total=signal.scores.total if signal.scores else 0.0,
                product_implication=signal.product_implication,
                status=signal.status.value,
            )
        )

    audit: list[LegacyAuditEntry] = []
    latest_decision_by_item: dict[str, FilterDecision] = {}
    for decision in result.decisions:
        latest_decision_by_item[decision.item_id] = decision

    accepted_ids = {item.item_id for item in result.accepted}
    score_by_item = {item.item_id: item.scores for item in signal_items}
    for signal in signal_items:
        decision = latest_decision_by_item.get(signal.item_id)
        scores = score_by_item[signal.item_id]
        audit.append(
            LegacyAuditEntry(
                item=item_map[signal.item_id],
                kept=signal.item_id in accepted_ids,
                gate=decision.stage if decision else "unknown",
                reason=decision.explanation if decision else "No final decision recorded.",
                scores={name: score.score for name, score in scores.as_dict().items()} if scores else None,
                total=scores.total if scores else None,
                status=signal.status.value,
            )
        )
    return shortlist, audit


# =============================================================================
# Internal ranking helpers
# =============================================================================


def _source_priority(item: SignalItem) -> tuple[int, float, float]:
    primary = 1 if item.metadata.is_primary_source else 0
    completeness = _metadata_completeness(item)
    recency = item.recency_weight
    source_weight = {
        SourceType.DOCUMENTATION: 8,
        SourceType.RESEARCH_PAPER: 7,
        SourceType.REPO: 6,
        SourceType.NEWS: 5,
        SourceType.BLOG: 4,
        SourceType.REPORT: 4,
        SourceType.COMMUNITY: 2,
        SourceType.OTHER: 1,
    }[item.metadata.source_type]
    return source_weight + primary, completeness, recency


def _prefer_best_sources(items: Sequence[SignalItem]) -> list[SignalItem]:
    return sorted(items, key=_source_priority, reverse=True)


def _ranking_score(item: SignalItem) -> float:
    base = float(item.scores.total if item.scores else 0)
    confidence = item.overall_confidence or 0.0
    credibility = item.credibility.score if item.credibility else 0
    primary_bonus = 0.50 if item.metadata.is_primary_source else 0.0
    return base + confidence + 0.20 * credibility + 0.25 * item.recency_weight + primary_bonus


def _unique_items(items: Sequence[SignalItem]) -> list[SignalItem]:
    seen: set[str] = set()
    output: list[SignalItem] = []
    for item in items:
        if item.item_id not in seen:
            seen.add(item.item_id)
            output.append(item)
    return output


# =============================================================================
# Demo and smoke test
# =============================================================================


def _demo_items() -> list[SignalItem]:
    now = utc_now()
    return [
        SignalItem(
            title="Salesforce launches AI workflow for support-ticket routing",
            body=(
                "Salesforce announced a new AI workflow that automatically routes support tickets. "
                "The company reports that early customers reduced handling time by 28%. "
                "The workflow is available now through its official product platform."
            ),
            metadata=SourceMetadata(
                source_url="https://www.salesforce.com/news/ai-support-routing?utm_source=test",
                source_name="Salesforce Newsroom",
                source_type=SourceType.NEWS,
                author="Product Communications",
                published_at=now,
                is_primary_source=True,
            ),
            category="news",
        ),
        SignalItem(
            title="Salesforce releases automated AI support routing",
            body=(
                "Salesforce released an AI feature for routing customer-support tickets automatically. "
                "Early users reportedly cut handling time by 28 percent."
            ),
            metadata=SourceMetadata(
                source_url="https://example.com/salesforce-ai-routing",
                source_name="Example Tech News",
                source_type=SourceType.NEWS,
                author="Reporter",
                published_at=now,
            ),
            category="news",
        ),
        SignalItem(
            title="Open-source RAG evaluation toolkit gains active contributors",
            body=(
                "The repository released version 2.1 with automated retrieval evaluation, test fixtures, "
                "and CI integration. It has 12,000 stars and recorded 35% star growth in 30 days."
            ),
            metadata=SourceMetadata(
                source_url="https://github.com/example/rag-eval",
                source_name="GitHub",
                source_type=SourceType.REPO,
                published_at=now,
                repository_full_name="example/rag-eval",
                is_primary_source=True,
                extra={
                    "stars": 12000,
                    "commits_last_90d": 42,
                    "star_growth_30d": 35,
                    "archived": False,
                },
            ),
            category="repo",
        ),
        SignalItem(
            title="A benchmark framework for distributed multi-agent inference",
            body=(
                "We propose a benchmark framework for distributed multi-agent inference and present "
                "ablation results against state-of-the-art baselines."
            ),
            metadata=SourceMetadata(
                source_url="https://arxiv.org/abs/2607.00001",
                source_name="arXiv",
                source_type=SourceType.RESEARCH_PAPER,
                published_at=now,
                source_native_id="arxiv:2607.00001",
                extra={"peer_reviewed": False, "citation_count": 0, "code_available": False},
            ),
            category="research_paper",
        ),
    ]


def main() -> None:
    pipeline = SignalFilterPipeline()
    context = FilterContext(
        brief="Find actionable AI product, developer tooling, and workflow intelligence.",
        domain="AI/ML",
        target_audience=["product", "engineering", "marketing"],
        model_version="heuristic-local-v2",
        prompt_version="signal-filter-v2",
    )
    result = pipeline.run(_demo_items(), context)

    print("=== SIGNAL FILTER RESULT ===")
    print(f"Run ID: {result.run_id}")
    print(f"Accepted: {len(result.accepted)}")
    print(f"Review: {len(result.review)}")
    print(f"Rejected: {len(result.rejected)}")
    print(f"Volume cut: {len(result.volume_cut)}")

    for item in result.accepted:
        print(f"\n[ACCEPT] {item.title}")
        print(f"  Total score: {item.scores.total if item.scores else 'n/a'}")
        print(f"  Confidence: {item.overall_confidence:.2f}" if item.overall_confidence is not None else "  Confidence: n/a")
        if item.generated:
            print(f"  Why it matters: {item.generated.why_it_matters}")
            print(f"  The move: {item.generated.the_move}")

    print("\n=== FINAL DECISIONS ===")
    final_by_item: dict[str, FilterDecision] = {}
    for decision in result.decisions:
        final_by_item[decision.item_id] = decision
    all_items = result.accepted + result.review + result.rejected + result.volume_cut
    for item in _unique_items(all_items):
        decision = final_by_item.get(item.item_id)
        print(
            f"[{item.status.value.upper():32}] {item.title[:65]:65} | "
            f"{decision.reason_code.value if decision else 'UNKNOWN'} | "
            f"{decision.explanation if decision else ''}"
        )

    print("\n=== METRICS JSON ===")
    print(json.dumps(_serialize_dataclass(result.metrics), indent=2))


if __name__ == "__main__":
    main()
