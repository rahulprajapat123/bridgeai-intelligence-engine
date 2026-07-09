from __future__ import annotations

from research_intel.config import Settings
from research_intel.ingestion.base import RawDocument
from research_intel.intelligence.extraction import ClaimExtractor


def test_heuristic_claim_extraction_links_metrics_and_tags():
    doc = RawDocument(
        title="RAG benchmark",
        source_url="https://example.org/rag",
        source_type="academic",
        source_name="Example",
        text=(
            "The benchmark found that hybrid retrieval improved recall by +18% on question answering. "
            "However, reranking added 240ms latency under production traffic."
        ),
        metadata={"domain": "AI/ML"},
    )

    claims = ClaimExtractor(Settings(database_connection_string="sqlite:///:memory:")).extract(doc)

    assert claims
    assert any("+18%" in claim.metrics for claim in claims)
    assert any("retrieval" in claim.applicability_tags for claim in claims)
    assert any(claim.limitations for claim in claims)

