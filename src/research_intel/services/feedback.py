from __future__ import annotations

from sqlalchemy.orm import Session

from research_intel.models import Feedback
from research_intel.schemas import FeedbackRequest, FeedbackResponse
from research_intel.utils import stable_id, utc_now


class FeedbackService:
    def record(self, session: Session, request: FeedbackRequest) -> FeedbackResponse:
        feedback_id = stable_id("feedback", request.query_id or "", utc_now().isoformat(), request.rating)
        session.add(
            Feedback(
                feedback_id=feedback_id,
                query_id=request.query_id,
                rating=request.rating,
                notes=request.notes,
                project_context=request.project_context,
                recommendation=request.recommendation,
            )
        )
        session.commit()
        return FeedbackResponse(feedback_id=feedback_id, status="recorded")

