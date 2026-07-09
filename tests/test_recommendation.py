from __future__ import annotations

from datetime import date

from research_intel.config import Settings
from research_intel.intelligence.embeddings import EmbeddingService
from research_intel.intelligence.recommendation import RecommendationService
from research_intel.intelligence.retrieval import RetrievalService
from research_intel.models import Claim, ResearchItem
from research_intel.schemas import ProjectContextInput
from research_intel.utils import stable_id, text_hash

from conftest import make_session


def _seed_claim(session):
    settings = Settings(database_connection_string="sqlite:///:memory:")
    embeddings = EmbeddingService(settings)
    research_id = stable_id("research", "https://example.org/legal-rag")
    session.add(
        ResearchItem(
            research_id=research_id,
            source_url="https://example.org/legal-rag",
            source_type="academic",
            source_name="Example Research",
            credibility_score=82,
            raw_text_hash=text_hash("hybrid retrieval reranking legal precision benchmark"),
            title="Legal RAG Hybrid Retrieval Benchmark",
            authors=["A. Researcher"],
            publication_date=date(2026, 1, 1),
            domain_tags=["legal", "retrieval", "evaluation"],
            metadata_json={"citation_count": 30},
            raw_text="Hybrid retrieval with reranking improved precision on legal contract QA benchmarks.",
        )
    )
    session.add(
        Claim(
            claim_id=stable_id("claim", research_id, "hybrid"),
            research_id=research_id,
            claim_text="Hybrid retrieval with reranking improved precision on legal contract QA benchmarks by +18%.",
            evidence_summary="Benchmark evidence reports +18% precision improvement.",
            evidence_type="benchmark",
            evidence_location="Table 2",
            metrics=["+18%"],
            conditions="for legal contract QA",
            limitations="requires reranker latency budget",
            applicability_tags=["retrieval", "reranking", "evaluation"],
            confidence=0.86,
            embedding=embeddings.embed("legal contract QA hybrid retrieval reranking precision +18%"),
        )
    )
    session.commit()
    return settings


def test_recommendation_returns_insufficient_evidence_for_missing_context():
    session = make_session()
    settings = Settings(database_connection_string="sqlite:///:memory:")
    service = RecommendationService(settings, RetrievalService(EmbeddingService(settings)))

    result = service.recommend(session, ProjectContextInput(problem_type="QA"))

    assert result.status == "insufficient_evidence"
    assert "data_modality" in result.data.missing_fields


def test_recommendation_contract_is_generated_from_claim_evidence():
    session = make_session()
    settings = _seed_claim(session)
    service = RecommendationService(settings, RetrievalService(EmbeddingService(settings)))

    result = service.recommend(
        session,
        ProjectContextInput(
            problem_type="QA",
            data_modality="PDFs",
            corpus_scale="50K documents",
            latency_constraint="3-5s",
            accuracy_cost_tradeoff="accuracy_first",
            deployment_env="GCP",
            domain="legal",
        ),
    )

    assert result.status == "ok"
    assert result.data.evidence[0].credibility_score >= 80
    assert result.data.recommendation.technique
    assert result.data.techniques_to_avoid
