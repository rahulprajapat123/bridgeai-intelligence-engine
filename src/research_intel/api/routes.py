from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from research_intel.db import get_session
from research_intel.models import (
    Claim,
    DailyIntelligenceReport,
    Feedback,
    IngestionRun,
    QueryLog,
    ResearchItem,
    SourceHealth,
    UploadedBrief,
)
from research_intel.schemas import (
    BriefAnalysis,
    BriefUploadResponse,
    ClaimSearchRequest,
    DailyIntelligenceRequest,
    DailyIntelligenceResponse,
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
    IngestRequest,
    IngestResponse,
    RecommendationRequest,
    RecommendationResponse,
    WorkflowAnalyzeRequest,
    WorkflowAnalyzeResponse,
)
from research_intel.services.factory import AppServices
from research_intel.services.analyze_brief_service import AnalyzeBriefService
from research_intel.services.feedback import FeedbackService
from research_intel.services.file_parser import UnsupportedBriefFile
from research_intel.services.workflow import WorkflowService


router = APIRouter(prefix="/api")


class BriefRequest(BaseModel):
    text: str = Field(min_length=20)


class StatsResponse(BaseModel):
    research_items: int
    claims: int
    query_logs: int
    feedback: int
    avg_credibility: float
    insufficient_evidence_rate: float


def services(request: Request) -> AppServices:
    return request.app.state.services


SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    app_services = services(request)
    return HealthResponse(
        status="ok",
        generated_at=datetime.now(UTC),
        connectors=app_services.settings.masked_connectors(),
        database="configured",
    )


@router.get("/stats", response_model=StatsResponse)
def stats(session: SessionDep) -> StatsResponse:
    total_queries = session.query(QueryLog).count()
    insufficient = session.query(QueryLog).filter(QueryLog.status == "insufficient_evidence").count()
    avg_cred = session.query(func.avg(ResearchItem.credibility_score)).scalar() or 0
    return StatsResponse(
        research_items=session.query(ResearchItem).count(),
        claims=session.query(Claim).count(),
        query_logs=total_queries,
        feedback=session.query(Feedback).count(),
        avg_credibility=round(float(avg_cred), 2),
        insufficient_evidence_rate=round(insufficient / total_queries, 3) if total_queries else 0,
    )


@router.post("/brief/analyze", response_model=BriefAnalysis)
def analyze_brief(
    request: BriefRequest,
    app_services: Annotated[AppServices, Depends(services)],
) -> BriefAnalysis:
    return app_services.brief.analyze(request.text)


@router.post("/analyze-brief")
async def analyze_brief_full(
    app_services: Annotated[AppServices, Depends(services)],
    file: UploadFile | None = File(default=None),
    brief_text: str | None = Form(default=None),
    domain_override: str | None = Form(default=None),
    top_k: int = Form(default=10),
    include_papers: bool = Form(default=True),
    include_github: bool = Form(default=True),
    include_blogs: bool = Form(default=True),
    include_news: bool = Form(default=True),
):
    try:
        if top_k < 1 or top_k > 50:
            raise ValueError("Top K Sources must be between 1 and 50.")
        return await AnalyzeBriefService(app_services).analyze(
            file=file,
            brief_text=brief_text,
            domain_override=domain_override,
            top_k=top_k,
            include_papers=include_papers,
            include_github=include_github,
            include_blogs=include_blogs,
            include_news=include_news,
        )
    except UnsupportedBriefFile as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/brief/upload", response_model=BriefUploadResponse)
async def upload_brief(
    session: SessionDep,
    app_services: Annotated[AppServices, Depends(services)],
    file: UploadFile = File(...),
) -> BriefUploadResponse:
    try:
        return await WorkflowService(app_services).upload_brief(session, file)
    except UnsupportedBriefFile as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/brief/{brief_id}")
def get_brief(
    brief_id: str,
    session: SessionDep,
    app_services: Annotated[AppServices, Depends(services)],
):
    brief = session.get(UploadedBrief, brief_id)
    if brief is None:
        raise HTTPException(status_code=404, detail="Brief not found")
    return {
        "brief_id": brief.brief_id,
        "filename": brief.filename,
        "extracted_text": brief.extracted_text,
        "analysis": brief.analysis,
        "uploaded_at": brief.uploaded_at,
    }


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    request: IngestRequest,
    session: SessionDep,
    app_services: Annotated[AppServices, Depends(services)],
) -> IngestResponse:
    return await app_services.ingestion.ingest_topic(
        session,
        topic=request.topic,
        domain=request.domain,
        max_per_source=request.max_per_source,
        dry_run=request.dry_run,
    )


@router.post("/workflow/analyze", response_model=WorkflowAnalyzeResponse)
async def analyze_workflow(
    request: WorkflowAnalyzeRequest,
    session: SessionDep,
    app_services: Annotated[AppServices, Depends(services)],
) -> WorkflowAnalyzeResponse:
    try:
        return await WorkflowService(app_services).analyze_workflow(
            session,
            brief_id=request.brief_id,
            text=request.text,
            auto_fetch=request.auto_fetch,
            max_per_source=request.max_per_source,
            top_k=request.top_k,
            min_credibility=request.min_credibility,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/claims/search")
def search_claims(
    request: ClaimSearchRequest,
    session: SessionDep,
    app_services: Annotated[AppServices, Depends(services)],
):
    return app_services.retrieval.search(
        session,
        request.query,
        domain=request.domain,
        top_k=request.top_k,
        min_credibility=request.min_credibility,
    )


@router.post("/recommend", response_model=RecommendationResponse)
def recommend(
    request: RecommendationRequest,
    session: SessionDep,
    app_services: Annotated[AppServices, Depends(services)],
) -> RecommendationResponse:
    return app_services.recommendation.recommend(
        session,
        request.project_context,
        top_k=request.top_k,
        min_credibility=request.min_credibility,
    )


@router.post("/feedback", response_model=FeedbackResponse)
def feedback(request: FeedbackRequest, session: SessionDep) -> FeedbackResponse:
    return FeedbackService().record(session, request)


@router.post("/daily-intelligence")
@router.post("/daily-intelligence/generate")
async def daily_intelligence_generate(
    request: DailyIntelligenceRequest,
    session: SessionDep,
    app_services: Annotated[AppServices, Depends(services)],
) -> dict:
    report_id, sent, report = await app_services.daily_intelligence.generate(
        session,
        max_items=request.max_items,
        send_email=request.send_email,
        recipient=request.recipient_email or request.recipient,
        topics=request.topics,
    )
    report["developer_details"]["report_id"] = report_id
    report["developer_details"]["status"] = "sent" if sent else "generated"
    return report


@router.post("/daily-intelligence/send", response_model=DailyIntelligenceResponse)
async def daily_intelligence_send(
    request: DailyIntelligenceRequest,
    session: SessionDep,
    app_services: Annotated[AppServices, Depends(services)],
) -> DailyIntelligenceResponse:
    report_id, sent, report = await app_services.daily_intelligence.generate(
        session,
        max_items=request.max_items,
        send_email=True,
        recipient=request.recipient_email or request.recipient,
        topics=request.topics,
    )
    return DailyIntelligenceResponse(
        report_id=report_id,
        status="sent" if sent else "generated",
        sent=sent,
        report=report,
    )


@router.get("/daily-intelligence/history")
def daily_intelligence_history(session: SessionDep, limit: int = 20):
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
    rows = (
        session.query(DailyIntelligenceReport)
        .order_by(DailyIntelligenceReport.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "report_id": row.report_id,
            "created_at": row.created_at,
            "sent_at": row.sent_at,
            "recipient": row.recipient,
            "status": row.status,
            "report": row.report,
        }
        for row in rows
    ]


@router.get("/sources")
def sources(session: SessionDep):
    rows = session.query(SourceHealth).order_by(SourceHealth.source_name.asc()).all()
    return [
        {
            "source_name": row.source_name,
            "enabled": row.enabled,
            "last_checked_at": row.last_checked_at,
            "last_success_at": row.last_success_at,
            "last_error": row.last_error,
            "success_count": row.success_count,
            "failure_count": row.failure_count,
        }
        for row in rows
    ]


@router.get("/ingestion-runs")
def ingestion_runs(session: SessionDep, limit: int = 20):
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
    rows = session.query(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(limit).all()
    return [
        {
            "run_id": row.run_id,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
            "topic": row.topic,
            "domain": row.domain,
            "status": row.status,
            "documents_seen": row.documents_seen,
            "documents_inserted": row.documents_inserted,
            "claims_inserted": row.claims_inserted,
            "errors": row.errors,
        }
        for row in rows
    ]
