from __future__ import annotations

from research_intel.intelligence.brief import BriefUnderstandingService


INTEL_BRIEF = """
Intel Partner Program Study: analyze Intel Partner Alliance against Microsoft, Nvidia, and AMD.
Scope includes Partner Program Analysis, Audience Matrix, Competitive Benchmarking, Partner Feedback
and Sentiment, BrightEdge Search Analytics, Sprinklr Social Listening, Adbeat Competitive Ad Analysis,
Co-Marketing, MDF, Enablement, Training, and Deal Registration. Deliverables are an Executive Report,
Detailed Report, PPT, Static RAG Dashboard, and Intel vs Competitor Comparison. Primary research is
out of scope and portal access is required for some partner data exports.
"""


def test_intel_partner_brief_routes_to_partner_programs_not_ai():
    result = BriefUnderstandingService().analyze(INTEL_BRIEF)

    assert result.domain.domain == "Partner Programs"
    assert "serper" in result.retrieval_routes
    assert "arxiv" not in result.retrieval_routes
    assert "Executive Report" in result.deliverables
    assert "PowerPoint Deck" in result.deliverables
    assert result.structured_constraints["requires_brightedge_export"] is True
    assert result.structured_constraints["requires_sprinklr_export"] is True
    assert result.structured_constraints["requires_adbeat_export"] is True
    assert result.structured_constraints["primary_research_out_of_scope"] is True

