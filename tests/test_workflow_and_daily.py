from __future__ import annotations

from datetime import date

import pytest

from research_intel.config import Settings
from research_intel.intelligence.embeddings import EmbeddingService
from research_intel.models import Claim, ResearchItem, UploadedBrief
from research_intel.services.daily_intelligence import DailyIntelligenceService
from research_intel.services.factory import build_services
from research_intel.services.file_parser import BriefFileParser
from research_intel.services.workflow import WorkflowService
from research_intel.utils import stable_id, text_hash

from conftest import make_session


def test_file_parser_supports_txt_and_md():
    parser = BriefFileParser()

    assert parser.parse("brief.txt", b"Legal RAG requirements for 50K PDFs") == "Legal RAG requirements for 50K PDFs"
    assert parser.parse("brief.md", b"# Partner Program\nMDF and enablement") == "# Partner Program\nMDF and enablement"


@pytest.mark.asyncio
async def test_workflow_analysis_returns_ranked_technology_recommendations():
    session = make_session()
    settings = Settings(database_connection_string="sqlite:///:memory:")
    services = build_services(settings)
    embeddings = EmbeddingService(settings)
    research_id = stable_id("research", "https://example.org/hybrid")
    session.add(
        ResearchItem(
            research_id=research_id,
            source_url="https://example.org/hybrid",
            source_type="academic",
            source_name="Example",
            credibility_score=84,
            raw_text_hash=text_hash("hybrid retrieval benchmark"),
            title="Hybrid Retrieval Benchmark",
            publication_date=date(2026, 1, 1),
            domain_tags=["AI/ML", "retrieval"],
            raw_text="Hybrid retrieval and reranking improved precision.",
        )
    )
    session.add(
        Claim(
            claim_id=stable_id("claim", research_id, "hybrid"),
            research_id=research_id,
            claim_text="Hybrid retrieval with reranking improved precision by +18% in a benchmark.",
            evidence_summary="Benchmark evidence.",
            evidence_type="benchmark",
            evidence_location="Table 1",
            metrics=["+18%"],
            applicability_tags=["retrieval", "reranking", "evaluation"],
            confidence=0.9,
            embedding=embeddings.embed("hybrid retrieval reranking precision benchmark"),
        )
    )
    session.commit()

    result = await WorkflowService(services).analyze_workflow(
        session,
        brief_id=None,
        text="We need a RAG system with hybrid retrieval and reranking for PDF QA.",
        auto_fetch=False,
        max_per_source=3,
        top_k=5,
    )

    assert result.recommendations
    assert result.citations
    assert result.recommendations[0].technology_name in {"Hybrid Search", "Cross-Encoder Reranking"}


@pytest.mark.asyncio
async def test_daily_intelligence_report_uses_stored_sources_and_briefs():
    session = make_session()
    session.add(
        ResearchItem(
            research_id="paper1",
            source_url="https://example.org/paper",
            source_type="academic",
            source_name="OpenAlex",
            credibility_score=81,
            raw_text_hash="hash",
            title="Latest RAG Paper",
            domain_tags=["AI/ML"],
            raw_text="A recent paper about RAG.",
        )
    )
    session.add(
        UploadedBrief(
            brief_id="brief1",
            filename="brief.txt",
            content_type="text/plain",
            text_hash="briefhash",
            extracted_text="AI/ML RAG brief",
            analysis={"domain": {"domain": "AI/ML"}},
        )
    )
    session.commit()

    report_id, sent, report = await DailyIntelligenceService(
        Settings(database_connection_string="sqlite:///:memory:")
    ).generate(session, send_email=False)

    assert report_id
    assert sent is False
    assert report["latest_research_papers"][0]["title"] == "Latest RAG Paper"

