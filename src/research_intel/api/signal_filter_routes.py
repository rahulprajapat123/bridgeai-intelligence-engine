from __future__ import annotations

from datetime import UTC, datetime, timedelta
from math import ceil
from typing import Literal
from xml.sax.saxutils import escape

from fastapi import APIRouter, Header, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from research_intel.signal_filter.config import SignalFilterConfig
from research_intel.signal_filter.models import FilterRunResult, SignalItem, SourceMetadata, SourceType, SignalScores, CriterionScore
from research_intel.signal_filter.pipeline import FilterContext, build_default_pipeline
from research_intel.intelligence_scope import is_in_intelligence_scope

router = APIRouter(prefix="/api/signal-filter", tags=["Signal Filter"])
_runs: dict[str, FilterRunResult] = {}
_idempotency: dict[str, str] = {}
_editorial_briefs: dict[str, dict] = {}
_config = SignalFilterConfig.from_env()

SECTION_ORDER = (
    "Academic Research", "Blogs", "Coding & Repositories", "News", "Web", "Social Media"
)


def _signal_section(source_type: str | SourceType) -> str:
    value = getattr(source_type, "value", source_type)
    return {
        "academic": "Academic Research",
        "research_paper": "Academic Research",
        "blog": "Blogs",
        "code": "Coding & Repositories",
        "repo": "Coding & Repositories",
        "news": "News",
        "web": "Web",
        "social": "Social Media",
        "community": "Social Media",
    }.get(str(value).lower(), "Web")


def _pdf_text(value: str | None) -> str:
    """Make untrusted source text safe for ReportLab's built-in fonts/XML."""
    normalized = (value or "").translate(str.maketrans({
        "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
        "\u2013": "-", "\u2014": "-", "\u2011": "-", "\u2026": "...",
    }))
    return escape(normalized.encode("latin-1", "replace").decode("latin-1"))


class RunRequest(BaseModel):
    items: list[SignalItem] = Field(min_length=1, max_length=40)
    config_overrides: dict = Field(default_factory=dict)


class ReviewRequest(BaseModel):
    item_id: str
    decision: Literal["accepted", "rejected"]
    notes: str = Field(default="", max_length=5000)


class ItemPatch(BaseModel):
    why_it_matters: str | None = Field(default=None, max_length=5000)
    the_move: str | None = Field(default=None, max_length=5000)
    recommended_action: str | None = Field(default=None, max_length=5000)


class EditorialBriefRequest(BaseModel):
    use_ai: bool = True


@router.post("/runs", status_code=status.HTTP_201_CREATED)
async def create_run(payload: RunRequest, response: Response, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    if idempotency_key and idempotency_key in _idempotency:
        response.status_code = status.HTTP_200_OK
        return _runs[_idempotency[idempotency_key]]
    config = SignalFilterConfig.model_validate({**_config.model_dump(), **payload.config_overrides})
    result = await build_default_pipeline(config).run(payload.items, FilterContext())
    _runs[result.run_id] = result
    if idempotency_key: _idempotency[idempotency_key] = result.run_id
    return result


def get_run(run_id: str) -> FilterRunResult:
    run = _runs.get(run_id)
    if not run: raise HTTPException(404, "Signal filter run not found")
    return run


@router.post("/runs/{run_id}/editorial-brief")
async def create_editorial_brief(run_id: str, payload: EditorialBriefRequest):
    from research_intel.config import Settings
    from research_intel.services.editorial_brief import build_editorial_brief

    run = get_run(run_id)
    accepted = [item for item in run.items if item.status == "accepted"]
    if not accepted:
        raise HTTPException(404, "No accepted signals are available for editorial synthesis")
    settings = Settings()
    brief = await build_editorial_brief(
        run_id, accepted, settings.openai_api_key if payload.use_ai else None
    )
    _editorial_briefs[run_id] = brief
    return brief


@router.get("/runs/{run_id}/editorial-brief")
def get_editorial_brief(run_id: str):
    get_run(run_id)
    brief = _editorial_briefs.get(run_id)
    if not brief:
        raise HTTPException(404, "Editorial brief has not been generated for this run")
    return brief


@router.get("/runs/{run_id}/editorial-brief.pdf")
async def export_editorial_brief_pdf(run_id: str):
    from io import BytesIO
    from fastapi.responses import StreamingResponse
    from research_intel.services.editorial_brief import build_editorial_brief_pdf

    get_run(run_id)
    brief = _editorial_briefs.get(run_id)
    if not brief:
        raise HTTPException(404, "Generate the editorial brief before downloading it")
    pdf = build_editorial_brief_pdf(brief)
    filename = f"BridgeAI_Editorial_Brief_{run_id[:8]}.pdf"
    return StreamingResponse(
        BytesIO(pdf), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/runs/{run_id}")
def run(run_id: str): return get_run(run_id)


@router.get("/runs/{run_id}/items")
def items(run_id: str, item_status: str | None = None, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    values = get_run(run_id).items
    if item_status: values = [x for x in values if x.status == item_status]
    return {"total": len(values), "items": values[offset:offset+limit]}


@router.get("/runs/{run_id}/decisions")
def decisions(run_id: str, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500)):
    values = get_run(run_id).decisions
    return {"total": len(values), "decisions": values[offset:offset+limit]}


@router.post("/runs/{run_id}/review")
def review(run_id: str, payload: ReviewRequest):
    run = get_run(run_id); item = next((x for x in run.items if x.item_id == payload.item_id), None)
    if not item: raise HTTPException(404, "Signal item not found")
    if item.status != "review": raise HTTPException(409, "Only review-queue items can receive a review decision")
    item.status = payload.decision
    return item


@router.patch("/items/{item_id}")
def patch_item(item_id: str, payload: ItemPatch):
    item = next((x for run in _runs.values() for x in run.items if x.item_id == item_id), None)
    if not item: raise HTTPException(404, "Signal item not found")
    for key, value in payload.model_dump(exclude_none=True).items(): setattr(item, key, value)
    return item


@router.post("/items/{item_id}/regenerate")
async def regenerate(item_id: str, field: str = Query(..., description="Field to regenerate: why_it_matters, the_move, or recommended_action"), reason: str = Query(default="Generic content", description="Why regeneration is needed")):
    """Regenerate a specific field using AI."""
    from research_intel.config import Settings
    from research_intel.signal_filter.adapters import OpenAIIntelligenceAdapter
    
    # Find the item
    item = next((x for run in _runs.values() for x in run.items if x.item_id == item_id), None)
    if not item: 
        raise HTTPException(404, "Signal item not found")
    
    # Check if OpenAI is configured
    settings = Settings()
    if not settings.openai_api_key:
        raise HTTPException(501, "OpenAI API key not configured. Set OPENAI_API_KEY in .env to enable regeneration.")
    
    # Create provider and regenerate
    provider = OpenAIIntelligenceAdapter(settings)
    
    try:
        new_value = await provider.regenerate_field(item, field, reason, _config.deny_list)
        setattr(item, field, new_value)
        return {field: new_value, "item_id": item_id, "regenerated": True}
    except Exception as e:
        raise HTTPException(500, f"Regeneration failed: {str(e)}")


@router.get("/config")
def config(): return _config


@router.patch("/config")
def patch_config(changes: dict):
    global _config
    _config = SignalFilterConfig.model_validate({**_config.model_dump(), **changes})
    return _config


@router.get("/metrics")
def metrics():
    runs = list(_runs.values())
    return {"runs": len(runs), "candidates": sum(x.metrics.candidate_count for x in runs), "accepted": sum(x.metrics.accepted_count for x in runs), "review": sum(x.metrics.review_count for x in runs), "duplicates": sum(x.metrics.duplicate_count for x in runs), "volume_cuts": sum(x.metrics.volume_cut_count for x in runs)}


# New endpoints for Daily Intelligence batch filtering
class BatchFilterRequest(BaseModel):
    batch_id: str = Field(..., description="Daily Intelligence batch ID to filter")
    novelty_threshold: float = Field(default=7.0, ge=0.0, le=10.0)
    relevance_threshold: float = Field(default=75.0, ge=0.0, le=100.0)
    max_items: int = Field(default=500, ge=5, le=500)
    enable_clustering: bool = Field(default=True)
    enable_qa: bool = Field(default=True)


@router.post("/run")
async def filter_batch(payload: BatchFilterRequest):
    """Filter a Daily Intelligence batch using the signal filter pipeline."""
    from research_intel.db import SessionLocal
    from research_intel.models import IngestionBatch, DailyRawItem, DailySummary
    from research_intel.config import Settings
    from research_intel.signal_filter.adapters import (
        EmbeddingServiceAdapter,
        DatabaseHistoricalRepository,
    )
    from research_intel.intelligence.embeddings import EmbeddingService
    
    session = SessionLocal()
    try:
        # Load the batch
        batch = session.get(IngestionBatch, payload.batch_id)
        if not batch:
            raise HTTPException(404, f"Batch {payload.batch_id} not found")
        
        if not batch.review_locked:
            raise HTTPException(400, "Batch must be submitted/approved before filtering")
        
        # Start with the selected batch, then add approved items from other
        # submitted runs so sparse sections can reach the five-item minimum.
        primary_items = session.query(DailyRawItem).filter(
            DailyRawItem.batch_id == payload.batch_id,
            DailyRawItem.review_status.in_(["approved", "edited"]),
            DailyRawItem.duplicate_of == None
        ).all()
        
        if not primary_items:
            raise HTTPException(404, "No approved items found in this batch")

        approved_batch_ids = [row[0] for row in session.query(IngestionBatch.id).filter(
            IngestionBatch.review_locked.is_(True),
            IngestionBatch.id != payload.batch_id,
        ).all()]
        fallback_items = session.query(DailyRawItem).filter(
            DailyRawItem.batch_id.in_(approved_batch_ids),
            DailyRawItem.review_status.in_(["approved", "edited"]),
            DailyRawItem.duplicate_of == None,
        ).all() if approved_batch_ids else []

        def candidate_rank(item):
            published = item.published_at
            if published and published.tzinfo is None:
                published = published.replace(tzinfo=UTC)
            timestamp = published.timestamp() if published else 0
            return (
                item.batch_id != payload.batch_id,
                -(item.relevance_score or 0),
                -timestamp,
            )

        approved_items = sorted([*primary_items, *fallback_items], key=candidate_rank)
        
        # Get summaries for these items
        summaries = {s.item_id: s for s in session.query(DailySummary).filter(
            DailySummary.item_id.in_([item.id for item in approved_items])
        ).all()}
        
        # Convert to SignalItems
        signal_items = []
        
        # Map daily intelligence source types to signal filter source types
        source_type_map = {
            "academic": SourceType.RESEARCH_PAPER,
            "news": SourceType.NEWS,
            "blog": SourceType.BLOG,
            "repo": SourceType.REPO,
            "research_paper": SourceType.RESEARCH_PAPER,
            "documentation": SourceType.DOCUMENTATION,
            "report": SourceType.REPORT,
            "community": SourceType.COMMUNITY,
            "social": SourceType.COMMUNITY,
            "code": SourceType.REPO,
            "web": SourceType.NEWS,
        }

        excluded_old = 0
        excluded_uninformative = 0
        candidate_section_counts = {section: 0 for section in SECTION_ORDER}
        candidate_pool_per_section = 60
        now = datetime.now(UTC)
        six_month_cutoff = now - timedelta(days=183)
        ten_year_cutoff = now - timedelta(days=3653)

        for item in approved_items:
            summary = summaries.get(item.id)
            if not summary:
                continue

            source_key = (item.source_type or "other").lower()
            section = _signal_section(source_key)
            if candidate_section_counts[section] >= candidate_pool_per_section:
                continue
            published_at = item.published_at
            if published_at and published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=UTC)
            cutoff = ten_year_cutoff if source_key in {"academic", "research_paper", "repo", "code"} else six_month_cutoff
            if published_at and published_at < cutoff:
                excluded_old += 1
                continue

            body = (summary.edited_summary_text or summary.summary_text or "").strip()
            if payload.enable_qa and len(f"{item.title} {body}".split()) < 12:
                excluded_uninformative += 1
                continue
            scoped_text = f"{item.title} {body}".lower()
            if payload.enable_qa and not is_in_intelligence_scope(scoped_text):
                excluded_uninformative += 1
                continue
            if item.relevance_score is not None and item.relevance_score < payload.relevance_threshold:
                excluded_uninformative += 1
                continue
            
            # Map source type
            mapped_source_type = source_type_map.get(
                item.source_type.lower() if item.source_type else "other",
                SourceType.OTHER
            )
                
            signal_item = SignalItem(
                item_id=item.id,
                title=item.title,
                body=body,
                metadata=SourceMetadata(
                    source_url=item.url,
                    source_name=item.source_name,
                    source_type=mapped_source_type,
                    author=item.author or None,
                    published_at=item.published_at,
                    domain=item.metadata_json.get("domain", "general") if item.metadata_json else "general",
                    attributes={
                        "batch_id": item.batch_id,
                        "is_fallback": item.batch_id != payload.batch_id,
                    },
                ),
            )
            signal_item.category = section
            structured = summary.structured_summary_json or {}
            # Archive filtering keeps source summaries and does not run the
            # short-newsletter prose diversity gate on boilerplate fields.
            signal_item.why_it_matters = None
            signal_item.the_move = None
            signal_item.recommended_action = structured.get("business_relevance")
            
            # Add optional fields if available
            if item.relevance_score is not None:
                if not published_at:
                    novelty_value = 3
                else:
                    age_days = max(0, (now - published_at).days)
                    novelty_value = 5 if age_days <= 30 else 4 if age_days <= 183 else 3 if age_days <= 730 else 2
                signal_item.scores = SignalScores(
                    business_relevance=CriterionScore(score=min(5, round(item.relevance_score / 20)), confidence=0.9, rationale="From daily intelligence"),
                    actionability=CriterionScore(score=3, confidence=0.8, rationale="Daily intelligence baseline"),
                    novelty=CriterionScore(score=novelty_value, confidence=0.8, rationale="Recency-based archive novelty; duplicate gates run separately"),
                    credibility=CriterionScore(score=min(5, round((item.credibility_score or 75) / 20)), confidence=0.9, rationale="From credibility assessment"),
                    momentum=CriterionScore(score=3, confidence=0.8, rationale="Daily intelligence baseline"),
                )
            
            signal_items.append(signal_item)
            candidate_section_counts[section] += 1
        
        if not signal_items:
            raise HTTPException(404, "No items with summaries found in this batch")

        per_section_min = 5
        per_section_max = min(20, payload.max_items)
        
        # Apply config overrides
        config_overrides = {
            "min_scores": {
                **{name: 0 for name in _config.min_scores},
                "novelty": min(5, ceil(payload.novelty_threshold / 2)),
            },
            "min_total_score": 0,
            "auto_accept_confidence": 0,
            "human_review_confidence": 0,
            "deny_list": [],
            "total_item_cap": per_section_max * len(SECTION_ORDER),
            "category_caps": {name: per_section_max for name in {
                *_config.category_caps, "news", "blog", "repo", "research_paper",
                "documentation", "report", "community", "other", *SECTION_ORDER,
            }},
            "event_clustering_enabled": payload.enable_clustering,
            "auto_regeneration_enabled": False,
        }
        
        config = SignalFilterConfig.model_validate({**_config.model_dump(), **config_overrides})
        
        # Create adapters for the filter context
        settings = Settings()
        embedding_service = EmbeddingService(settings)
        embedding_adapter = EmbeddingServiceAdapter(embedding_service)
        historical_repo = DatabaseHistoricalRepository(session)
        # Create context with adapters
        context = FilterContext(
            repository=historical_repo,
            embedding_provider=embedding_adapter,
            intelligence_provider=None,
        )
        
        result = await build_default_pipeline(config).run(signal_items, context)
        _runs[result.run_id] = result
        
        # Prepare response
        filtered_items = [item for item in result.items if item.status == "accepted"]
        filtered_items.sort(key=lambda item: (
            SECTION_ORDER.index(item.category) if item.category in SECTION_ORDER else len(SECTION_ORDER),
            item.title.lower(),
        ))

        def response_item(item: SignalItem) -> dict:
            return {
                "item_id": item.item_id,
                "title": item.title,
                "summary": item.body,
                "why_it_matters": item.why_it_matters,
                "the_move": item.the_move,
                "recommended_action": item.recommended_action,
                "url": item.canonical_url or item.metadata.source_url,
                "source_type": item.metadata.source_type.value,
                "source_name": item.metadata.source_name,
                "section": item.category or _signal_section(item.metadata.source_type),
                "novelty_score": item.scores.novelty.score * 2 if item.scores else None,
                "relevance_score": item.scores.business_relevance.score * 20 if item.scores else None,
                "published_at": item.metadata.published_at.isoformat() if item.metadata.published_at else None,
                "origin_batch_id": item.metadata.attributes.get("batch_id"),
                "is_fallback": bool(item.metadata.attributes.get("is_fallback")),
            }

        grouped_sections = [
            {
                "section": section,
                "count": sum(item.category == section for item in filtered_items),
                "minimum": per_section_min,
                "maximum": per_section_max,
                "shortage": max(0, per_section_min - sum(item.category == section for item in filtered_items)),
                "items": [response_item(item) for item in filtered_items if item.category == section],
            }
            for section in SECTION_ORDER
        ]

        fallback_count = sum(bool(item.metadata.attributes.get("is_fallback")) for item in filtered_items)
        
        return {
            "run_id": result.run_id,
            "batch_id": payload.batch_id,
            "summary": {
                "input_items": len(signal_items),
                "output_items": len(filtered_items),
                "removed_duplicates": result.metrics.duplicate_count,
                "removed_low_quality": result.metrics.volume_cut_count,
                "removed_too_old": excluded_old,
                "removed_uninformative": excluded_uninformative,
                "clustering_applied": payload.enable_clustering,
                "qa_checks_applied": payload.enable_qa,
                "per_section_minimum": per_section_min,
                "per_section_maximum": per_section_max,
                "fallback_items_used": fallback_count,
                "section_shortages": {
                    group["section"]: group["shortage"] for group in grouped_sections if group["shortage"]
                },
            },
            "sections": grouped_sections,
            "filtered_items": [response_item(item) for item in filtered_items],
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"ERROR in filter_batch: {e}")
        print(traceback.format_exc())
        raise HTTPException(500, f"Filter error: {str(e)}")
    finally:
        session.close()


@router.get("/runs/{run_id}/export.pdf")
async def export_filtered_pdf(run_id: str):
    """Export filtered signals as PDF."""
    from io import BytesIO
    from fastapi.responses import StreamingResponse
    from research_intel.services.daily_pdf import build_daily_pdf
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import PageBreak, SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    
    run = get_run(run_id)
    filtered_items = [item for item in run.items if item.status == "accepted"]
    
    if not filtered_items:
        raise HTTPException(404, "No filtered items to export")
    
    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    story = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor='#17324d',
        spaceAfter=12,
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor='#2f6f9f',
        spaceAfter=6,
    )

    section_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading1'],
        fontSize=17,
        textColor='#17324d',
        spaceAfter=8,
        keepWithNext=True,
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['BodyText'],
        fontSize=10,
        leading=14,
    )
    
    # Title
    story.append(Paragraph(f"Filtered Intelligence Signals - Run {run_id[:8]}", title_style))
    story.append(Paragraph(f"{len(filtered_items)} High-Quality Signals", body_style))
    for section in SECTION_ORDER:
        count = sum((item.category or _signal_section(item.metadata.source_type)) == section for item in filtered_items)
        if count:
            story.append(Paragraph(f"<b>{_pdf_text(section)}:</b> {count}", body_style))
    story.append(Spacer(1, 0.3*inch))

    grouped_items = {
        section: [
            item for item in filtered_items
            if (item.category or _signal_section(item.metadata.source_type)) == section
        ]
        for section in SECTION_ORDER
    }

    # Items grouped into stable source sections.
    for section in SECTION_ORDER:
        section_items = grouped_items[section]
        if not section_items:
            continue
        story.append(PageBreak())
        story.append(Paragraph(_pdf_text(section), section_style))
        story.append(Paragraph(f"{len(section_items)} filtered signals", body_style))
        story.append(Spacer(1, 0.2*inch))
        for idx, item in enumerate(section_items, 1):
            story.append(Paragraph(f"{idx}. {_pdf_text(item.title)}", heading_style))
            source_name = _pdf_text(item.metadata.source_name or "Unknown")
            source_type = _pdf_text(item.metadata.source_type.value)
            story.append(Paragraph(f"<b>Source:</b> {source_name} ({source_type})", body_style))
            if item.scores:
                novelty = item.scores.novelty.score * 2
                relevance = item.scores.business_relevance.score * 20
                story.append(Paragraph(f"<b>Novelty:</b> {novelty:.1f}/10 | <b>Relevance:</b> {relevance}", body_style))
            story.append(Spacer(1, 0.1*inch))
        
            if item.body:
                story.append(Paragraph(f"<b>Summary:</b> {_pdf_text(item.body)}", body_style))
        
            if item.why_it_matters:
                story.append(Paragraph(f"<b>Why It Matters:</b> {_pdf_text(item.why_it_matters)}", body_style))
        
            if item.the_move:
                story.append(Paragraph(f"<b>The Move:</b> {_pdf_text(item.the_move)}", body_style))
        
            if item.recommended_action:
                story.append(Paragraph(f"<b>Recommended Action:</b> {_pdf_text(item.recommended_action)}", body_style))
        
            item_url = item.canonical_url or item.metadata.source_url
            if item_url:
                safe_url = _pdf_text(item_url)
                story.append(Paragraph(f"<b>URL:</b> <link href='{safe_url}'>{safe_url}</link>", body_style))
        
            story.append(Spacer(1, 0.3*inch))
    
    doc.build(story)
    buffer.seek(0)
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="BridgeAI_Filtered_Signals_{run_id[:8]}.pdf"',
            "Cache-Control": "no-store",
        }
    )
