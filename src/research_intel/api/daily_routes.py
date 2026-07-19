from __future__ import annotations

import asyncio
import uuid
from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from research_intel.db import SessionLocal, get_session
from research_intel.models import DailyAuditLog, DailyRawItem, DailySourceRun, DailySummary, IngestionBatch, now_utc
from research_intel.services.daily_pdf import build_comprehensive_pdf, build_daily_pdf
from research_intel.services.daily_pipeline import DailyIntelligencePipeline
from research_intel.utils import stable_id

router = APIRouter(prefix="/api/daily-intelligence", tags=["Daily Intelligence"])
SessionDep = Annotated[Session, Depends(get_session)]

class RunRequest(BaseModel):
    topics: list[str] | None = None

class SummaryPatch(BaseModel):
    edited_summary_text: str | None = Field(default=None, max_length=20000)
    reviewer_notes: str | None = Field(default=None, max_length=5000)
    restore_original: bool = False

class BulkReview(BaseModel):
    summary_ids: list[str] = Field(min_length=1, max_length=500)
    action: str
    notes: str = ""

def reviewer(x_reviewer_id: str = Header(default="local-reviewer"), x_reviewer_role: str = Header(default="reviewer")) -> str:
    if x_reviewer_role not in {"reviewer", "admin"}: raise HTTPException(403, "Reviewer role required")
    return x_reviewer_id[:120]

def _run_batch(batch_id: str, topics: list[str] | None, settings) -> None:
    session = SessionLocal()
    try: asyncio.run(DailyIntelligencePipeline(settings).run(session, batch_id, topics))
    finally: session.close()

def batch_dict(row):
    return {c.name: getattr(row, c.name) for c in row.__table__.columns if c.name != "approved_snapshot"}

@router.post("/run", status_code=202)
def run_daily(payload: RunRequest, background: BackgroundTasks, request: Request, session: SessionDep, actor: Annotated[str, Depends(reviewer)]):
    pipeline = DailyIntelligencePipeline(request.app.state.services.settings)
    batch = pipeline.create_batch(session, topics=payload.topics, actor=actor)
    background.add_task(_run_batch, batch.id, payload.topics, request.app.state.services.settings)
    return {"batch_id": batch.id, "status": batch.status, "message": "Ingestion queued"}

@router.get("/batches")
def batches(session: SessionDep, limit: int = Query(20, ge=1, le=100)):
    return [batch_dict(x) for x in session.query(IngestionBatch).order_by(IngestionBatch.created_at.desc()).limit(limit)]

@router.get("/batches/{batch_id}")
def batch(batch_id: str, session: SessionDep):
    row = session.get(IngestionBatch, batch_id)
    if not row: raise HTTPException(404, "Batch not found")
    data = batch_dict(row)
    data["source_runs"] = [source_run_dict(x) for x in session.query(DailySourceRun).filter_by(batch_id=batch_id)]
    return data

@router.get("/batches/{batch_id}/items")
def items(batch_id: str, session: SessionDep, source_type: str | None = None, source_name: str | None = None,
          review_status: str | None = None, keyword: str | None = None, min_relevance: float | None = None,
          min_credibility: float | None = None, sort: str = "newest", page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
    q = session.query(DailyRawItem).filter_by(batch_id=batch_id, duplicate_of=None)
    if source_type: q = q.filter(DailyRawItem.source_type == source_type)
    if source_name: q = q.filter(DailyRawItem.source_name == source_name)
    if review_status: q = q.filter(DailyRawItem.review_status == review_status)
    if keyword: q = q.filter(or_(DailyRawItem.title.ilike(f"%{keyword}%"), DailyRawItem.cleaned_content.ilike(f"%{keyword}%")))
    if min_relevance is not None: q = q.filter(DailyRawItem.relevance_score >= min_relevance)
    if min_credibility is not None: q = q.filter(DailyRawItem.credibility_score >= min_credibility)
    ordering = {"highest_relevance": DailyRawItem.relevance_score.desc(), "highest_credibility": DailyRawItem.credibility_score.desc(), "source_name": DailyRawItem.source_name.asc()}.get(sort, DailyRawItem.published_at.desc())
    total = q.count(); rows = q.order_by(ordering).offset((page-1)*page_size).limit(page_size).all()
    summary_map = {s.item_id: s for s in session.query(DailySummary).filter(DailySummary.item_id.in_([x.id for x in rows]), DailySummary.summary_level == "item")}
    return {"total": total, "page": page, "page_size": page_size, "items": [item_dict(x, summary_map.get(x.id)) for x in rows]}

@router.get("/batches/{batch_id}/summaries")
def summaries(batch_id: str, session: SessionDep, level: str | None = None):
    q = session.query(DailySummary).filter_by(batch_id=batch_id)
    if level: q = q.filter_by(summary_level=level)
    return [summary_dict(x) for x in q.order_by(DailySummary.source_type, DailySummary.created_at)]

@router.patch("/summaries/{summary_id}")
def edit_summary(summary_id: str, payload: SummaryPatch, session: SessionDep, actor: Annotated[str, Depends(reviewer)]):
    row = mutable_summary(session, summary_id)
    row.edited_summary_text = None if payload.restore_original else payload.edited_summary_text
    row.reviewer_notes = payload.reviewer_notes or row.reviewer_notes
    row.reviewer_id = actor; row.status = "pending" if payload.restore_original else "edited"
    item = session.get(DailyRawItem, row.item_id); item.review_status = row.status
    audit(session, row.batch_id, actor, "restore_original" if payload.restore_original else "edit", row)
    session.commit(); return summary_dict(row)

@router.post("/summaries/{summary_id}/approve")
def approve(summary_id: str, session: SessionDep, actor: Annotated[str, Depends(reviewer)]): return review_one(session, summary_id, "approved", actor)

@router.post("/summaries/{summary_id}/reject")
def reject(summary_id: str, session: SessionDep, actor: Annotated[str, Depends(reviewer)]): return review_one(session, summary_id, "rejected", actor)

@router.post("/summaries/bulk-review")
def bulk_review(payload: BulkReview, session: SessionDep, actor: Annotated[str, Depends(reviewer)]):
    if payload.action not in {"approve", "reject"}: raise HTTPException(400, "action must be approve or reject")
    target_status = "approved" if payload.action == "approve" else "rejected"
    rows = session.query(DailySummary).filter(DailySummary.id.in_(payload.summary_ids)).all()
    by_id = {row.id: row for row in rows}
    missing = [summary_id for summary_id in payload.summary_ids if summary_id not in by_id]
    updated = []
    skipped = []
    for summary_id in payload.summary_ids:
        row = by_id.get(summary_id)
        if not row or row.summary_level != "item":
            continue
        batch = session.get(IngestionBatch, row.batch_id)
        item = session.get(DailyRawItem, row.item_id)
        if not batch or batch.review_locked or not item:
            skipped.append(summary_id)
            continue
        row.status = target_status
        row.reviewer_id = actor
        row.approved_at = now_utc() if target_status == "approved" else None
        row.rejected_at = now_utc() if target_status == "rejected" else None
        item.review_status = "edited" if target_status == "approved" and row.edited_summary_text else target_status
        audit(session, row.batch_id, actor, target_status, row)
        updated.append(summary_dict(row))
    session.commit()
    return {"updated": updated, "updated_count": len(updated), "missing": missing, "skipped": skipped}

@router.post("/batches/{batch_id}/submit-review")
def submit(batch_id: str, session: SessionDep, actor: Annotated[str, Depends(reviewer)]):
    row = session.get(IngestionBatch, batch_id)
    if not row: raise HTTPException(404, "Batch not found")
    if row.review_locked: raise HTTPException(409, "Batch review is already locked")
    pending = session.query(DailyRawItem).filter_by(batch_id=batch_id, duplicate_of=None, review_status="pending").count()
    if pending: raise HTTPException(409, f"{pending} items still require a review decision")
    approved = session.query(DailyRawItem).filter(DailyRawItem.batch_id == batch_id, DailyRawItem.review_status.in_(["approved", "edited"])).all()
    summaries = {x.item_id: x for x in session.query(DailySummary).filter(DailySummary.item_id.in_([i.id for i in approved]))}
    row.approved_snapshot = jsonable_encoder({"contract_version": "1.0", "batch_id": batch_id, "items": [item_dict(i, summaries.get(i.id)) for i in approved]})
    row.review_locked = True; row.status = "approved"; row.approved_items = len(approved)
    row.rejected_items = session.query(DailyRawItem).filter_by(batch_id=batch_id, review_status="rejected").count()
    row.edited_items = session.query(DailySummary).filter_by(batch_id=batch_id, status="edited").count()
    audit(session, batch_id, actor, "submit_review"); session.commit()
    return {"batch_id": batch_id, "status": row.status, "approved_items": len(approved), "downstream_contract": row.approved_snapshot}

@router.get("/batches/{batch_id}/approved-data")
def approved_data(batch_id: str, session: SessionDep):
    row = session.get(IngestionBatch, batch_id)
    if not row or not row.review_locked: raise HTTPException(409, "Approved snapshot is not available")
    return row.approved_snapshot

@router.get("/batches/{batch_id}/export.pdf")
def export_pdf(batch_id: str, session: SessionDep, include_pending: bool = False, include_rejected: bool = False):
    row = session.get(IngestionBatch, batch_id)
    if not row: raise HTTPException(404, "Batch not found")
    content = build_daily_pdf(session, row, include_pending, include_rejected)
    return pdf_response(content, f"BridgeAI_Daily_Intelligence_{batch_id}.pdf")

@router.get("/export-all.pdf")
def export_all_pdf(session: SessionDep):
    """Export every canonical Daily Intelligence record persisted in the database."""
    content = build_comprehensive_pdf(session)
    return pdf_response(content, f"BridgeAI_Comprehensive_Daily_Intelligence_{now_utc().date()}.pdf")

def pdf_response(content: bytes, filename: str) -> StreamingResponse:
    if not content.startswith(b"%PDF") or len(content) < 1000:
        raise HTTPException(500, "PDF generation did not produce a valid document")
    return StreamingResponse(
        BytesIO(content),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(content)),
            "Cache-Control": "no-store",
        },
    )

@router.get("/source-health")
def source_health(session: SessionDep):
    latest = session.query(DailySourceRun).order_by(DailySourceRun.started_at.desc()).all(); seen = set(); output = []
    for row in latest:
        if row.source_name in seen: continue
        seen.add(row.source_name); output.append(source_run_dict(row))
    return output

def mutable_summary(session, summary_id):
    row = session.get(DailySummary, summary_id)
    if not row or row.summary_level != "item": raise HTTPException(404, "Item summary not found")
    batch = session.get(IngestionBatch, row.batch_id)
    if batch.review_locked: raise HTTPException(409, "Batch review is locked")
    return row

def review_one(session, summary_id, status, actor):
    row = mutable_summary(session, summary_id); row.status = status; row.reviewer_id = actor
    row.approved_at = now_utc() if status == "approved" else None; row.rejected_at = now_utc() if status == "rejected" else None
    item = session.get(DailyRawItem, row.item_id); item.review_status = "edited" if status == "approved" and row.edited_summary_text else status
    audit(session, row.batch_id, actor, status, row); session.commit(); return summary_dict(row)

def audit(session, batch_id, actor, action, summary=None):
    # Include summary_id in stable_id to prevent collisions when bulk-approving
    summary_part = summary.id if summary else str(uuid.uuid4())
    session.add(DailyAuditLog(id=stable_id("audit", batch_id, action, actor, now_utc().isoformat(), summary_part), batch_id=batch_id, item_id=summary.item_id if summary else None, summary_id=summary.id if summary else None, action=action, actor_id=actor))

def item_dict(x, summary=None):
    return {"id": x.id, "batch_id": x.batch_id, "title": x.title, "source_name": x.source_name, "source_type": x.source_type, "publication_date": x.published_at, "url": x.url, "author": x.author, "relevance_score": x.relevance_score, "credibility_score": x.credibility_score, "processing_status": x.processing_status, "review_status": x.review_status, "metadata": x.metadata_json, "raw_content": x.raw_content, "summary": summary_dict(summary) if summary else None}

def summary_dict(x):
    if not x: return None
    return {"id": x.id, "batch_id": x.batch_id, "item_id": x.item_id, "source_type": x.source_type, "source_name": x.source_name, "summary_level": x.summary_level, "summary_text": x.summary_text, "edited_summary_text": x.edited_summary_text, "display_summary_text": x.edited_summary_text or x.summary_text, "structured_summary": x.structured_summary_json, "citations": x.citations_json, "model_name": x.model_name, "prompt_version": x.prompt_version, "status": x.status, "reviewer_id": x.reviewer_id, "reviewer_notes": x.reviewer_notes, "created_at": x.created_at, "updated_at": x.updated_at}

def source_run_dict(x):
    lowered = (x.error_message or "").lower()
    error_kind = None
    if x.error_message:
        if "429" in lowered or "rate limit" in lowered: error_kind = "rate_limited"
        elif any(term in lowered for term in ("401", "403", "api key", "authentication", "forbidden")): error_kind = "authentication"
        elif any(term in lowered for term in ("timeout", "timed out")): error_kind = "timeout"
        else: error_kind = "provider_error"
    safe_error = {
        "rate_limited": "Provider rate limit reached; retry after its reset window.",
        "authentication": "Provider authentication or API-key check failed.",
        "timeout": "Provider did not respond before the configured timeout.",
        "provider_error": "Provider request failed; see server logs.",
    }.get(error_kind)
    detail = "Source reachable, but no items matched this run's query." if x.status in {"degraded", "no_results"} and not x.error_message else safe_error
    return {"source_name": x.source_name, "source_type": x.source_type, "status": x.status, "last_fetch": x.completed_at, "response_time_ms": x.response_time_ms, "items_returned": x.items_returned, "quota_consumed": x.quota_consumed, "retries": x.retries, "error": detail, "error_kind": error_kind, "circuit_breaker_state": x.circuit_breaker_state}
