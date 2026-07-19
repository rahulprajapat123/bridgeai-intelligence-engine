from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


def now_utc() -> datetime:
    return datetime.now(UTC)


class ResearchItem(Base):
    __tablename__ = "research_items"

    research_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_name: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    publisher: Mapped[str] = mapped_column(Text, default="")
    ingestion_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    credibility_score: Mapped[float] = mapped_column(Float, default=0)
    credibility_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    raw_text_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    authors: Mapped[list[str]] = mapped_column(JSON, default=list)
    publication_date = mapped_column(Date, nullable=True)
    domain_tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    raw_text: Mapped[str] = mapped_column(Text, default="")
    cleaned_text: Mapped[str] = mapped_column(Text, default="")
    parse_status: Mapped[str] = mapped_column(String(32), default="parsed")

    claims: Mapped[list["Claim"]] = relationship(
        back_populates="research_item", cascade="all, delete-orphan"
    )


class Claim(Base):
    __tablename__ = "claims"

    claim_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    research_id: Mapped[str] = mapped_column(ForeignKey("research_items.research_id"), index=True)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_summary: Mapped[str] = mapped_column(Text, default="")
    evidence_type: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_location: Mapped[str] = mapped_column(Text, default="")
    metrics: Mapped[list[str]] = mapped_column(JSON, default=list)
    conditions: Mapped[str] = mapped_column(Text, default="")
    limitations: Mapped[str] = mapped_column(Text, default="")
    applicability_tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    domain_tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    extraction_method: Mapped[str] = mapped_column(String(32), default="heuristic_auto")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    validated_at = mapped_column(DateTime(timezone=True), nullable=True)
    embedding: Mapped[list[float]] = mapped_column(JSON, default=list)
    citation_url: Mapped[str] = mapped_column(Text, default="")
    source_quote: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    research_item: Mapped[ResearchItem] = relationship(back_populates="claims")


class SourceHealth(Base):
    __tablename__ = "source_health"
    __table_args__ = (UniqueConstraint("source_name", name="uq_source_health_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String(80), nullable=False)
    enabled: Mapped[bool] = mapped_column(default=True)
    last_checked_at = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    finished_at = mapped_column(DateTime(timezone=True), nullable=True)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(String(80), default="general")
    status: Mapped[str] = mapped_column(String(32), default="running")
    documents_seen: Mapped[int] = mapped_column(Integer, default=0)
    documents_inserted: Mapped[int] = mapped_column(Integer, default=0)
    claims_inserted: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list[str]] = mapped_column(JSON, default=list)


class UploadedBrief(Base):
    __tablename__ = "uploaded_briefs"

    brief_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), default="")
    text_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    analysis: Mapped[dict] = mapped_column(JSON, default=dict)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class QueryLog(Base):
    __tablename__ = "query_logs"

    query_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    project_context: Mapped[dict] = mapped_column(JSON, default=dict)
    brief_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    query_text: Mapped[str] = mapped_column(Text, default="")
    response: Mapped[dict] = mapped_column(JSON, default=dict)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="ok")


class Feedback(Base):
    __tablename__ = "feedback"

    feedback_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    query_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    rating: Mapped[str] = mapped_column(String(32), nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="")
    project_context: Mapped[dict] = mapped_column(JSON, default=dict)
    recommendation: Mapped[dict] = mapped_column(JSON, default=dict)


class DailyIntelligenceReport(Base):
    __tablename__ = "daily_intelligence_reports"

    report_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    sent_at = mapped_column(DateTime(timezone=True), nullable=True)
    recipient: Mapped[str | None] = mapped_column(Text, nullable=True)
    topics: Mapped[list[str]] = mapped_column(JSON, default=list)
    recipients: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="generated")
    report: Mapped[dict] = mapped_column(JSON, default=dict)


class IngestionBatch(Base):
    __tablename__ = "ingestion_batches"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    batch_type: Mapped[str] = mapped_column(String(32), default="daily_intelligence")
    started_at = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="created", index=True)
    total_sources: Mapped[int] = mapped_column(Integer, default=0)
    successful_sources: Mapped[int] = mapped_column(Integer, default=0)
    failed_sources: Mapped[int] = mapped_column(Integer, default=0)
    total_raw_items: Mapped[int] = mapped_column(Integer, default=0)
    unique_items: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_items: Mapped[int] = mapped_column(Integer, default=0)
    summarized_items: Mapped[int] = mapped_column(Integer, default=0)
    approved_items: Mapped[int] = mapped_column(Integer, default=0)
    rejected_items: Mapped[int] = mapped_column(Integer, default=0)
    edited_items: Mapped[int] = mapped_column(Integer, default=0)
    configuration_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    error_summary: Mapped[list] = mapped_column(JSON, default=list)
    created_by: Mapped[str] = mapped_column(String(120), default="system")
    review_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class DailyRawItem(Base):
    __tablename__ = "daily_raw_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("ingestion_batches.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_name: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    external_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    author: Mapped[str] = mapped_column(Text, default="")
    organization: Mapped[str] = mapped_column(Text, default="")
    published_at = mapped_column(DateTime(timezone=True), nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    original_response: Mapped[dict] = mapped_column(JSON, default=dict)
    raw_content: Mapped[str] = mapped_column(Text, default="")
    cleaned_content: Mapped[str] = mapped_column(Text, default="")
    abstract: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    language: Mapped[str] = mapped_column(String(16), default="en")
    content_type: Mapped[str] = mapped_column(String(80), default="text/html")
    relevance_score: Mapped[float] = mapped_column(Float, default=0)
    credibility_score: Mapped[float] = mapped_column(Float, default=0)
    access_status: Mapped[str] = mapped_column(String(32), default="available")
    licence: Mapped[str] = mapped_column(Text, default="")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    duplicate_of: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    processing_status: Mapped[str] = mapped_column(String(32), default="unprocessed")
    review_status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class DailySourceReference(Base):
    __tablename__ = "daily_source_references"
    __table_args__ = (UniqueConstraint("batch_id", "source_name", "external_id", name="uq_daily_source_ref"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("ingestion_batches.id"), index=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("daily_raw_items.id"), index=True)
    source_name: Mapped[str] = mapped_column(String(80), nullable=False)
    external_id: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(Text, default="")
    identifiers_json: Mapped[dict] = mapped_column(JSON, default=dict)


class DailySummary(Base):
    __tablename__ = "summaries"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("ingestion_batches.id"), index=True)
    item_id: Mapped[str | None] = mapped_column(ForeignKey("daily_raw_items.id"), nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_name: Mapped[str] = mapped_column(String(80), default="")
    summary_level: Mapped[str] = mapped_column(String(32), nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, default="")
    structured_summary_json: Mapped[dict] = mapped_column(JSON, default=dict)
    citations_json: Mapped[list] = mapped_column(JSON, default=list)
    model_name: Mapped[str] = mapped_column(String(120), default="deterministic-extractive")
    prompt_version: Mapped[str] = mapped_column(String(40), default="daily-v1")
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    reviewer_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reviewer_notes: Mapped[str] = mapped_column(Text, default="")
    edited_summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    approved_at = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at = mapped_column(DateTime(timezone=True), nullable=True)


class DailySourceRun(Base):
    __tablename__ = "daily_source_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("ingestion_batches.id"), index=True)
    source_name: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="healthy")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    completed_at = mapped_column(DateTime(timezone=True), nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_time_ms: Mapped[int] = mapped_column(Integer, default=0)
    items_returned: Mapped[int] = mapped_column(Integer, default=0)
    quota_consumed: Mapped[int] = mapped_column(Integer, default=0)
    retries: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    circuit_breaker_state: Mapped[str] = mapped_column(String(32), default="closed")


class DailyAuditLog(Base):
    __tablename__ = "daily_audit_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("ingestion_batches.id"), index=True)
    item_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    summary_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(120), nullable=False)
    details_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class ManualReviewQueue(Base):
    __tablename__ = "manual_review_queue"

    review_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    item_type: Mapped[str] = mapped_column(String(32), nullable=False)
    item_id: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="open")


class HistoricalSignal(Base):
    """Historical storage for filter novelty scoring."""
    __tablename__ = "historical_signals"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(64), nullable=False)
    item_id: Mapped[str] = mapped_column(String(64), nullable=False)
    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, default="")
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    published_at = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
