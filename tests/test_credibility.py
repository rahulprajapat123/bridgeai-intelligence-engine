from __future__ import annotations

from research_intel.ingestion.base import RawDocument
from research_intel.intelligence.credibility import CredibilityScorer, usage_bucket
from research_intel.schemas import ClaimCreate


def test_credibility_scoring_uses_required_framework():
    doc = RawDocument(
        title="Hybrid retrieval benchmark",
        source_url="https://arxiv.org/abs/2601.00001",
        source_type="academic",
        source_name="arXiv",
        text="A benchmark experiment reports +18% recall with clear dataset metrics and reproducible code.",
        publication_date="2026-01-01",
        metadata={"citation_count": 42},
    )
    claims = [
        ClaimCreate(
            claim_text="Hybrid retrieval improves recall by +18% in the benchmark.",
            evidence_summary="Benchmark evidence with metric.",
            evidence_type="benchmark",
            evidence_location="Table 2",
            metrics=["+18%"],
            applicability_tags=["retrieval", "evaluation"],
            confidence=0.9,
        )
    ]

    score = CredibilityScorer().score(doc, claims)

    assert score >= 80
    assert usage_bucket(score) == "strong_recommendation_candidate"


def test_low_evidence_vendor_content_is_background_only():
    doc = RawDocument(
        title="Product announcement",
        source_url="https://vendor.example.com/blog/new-product",
        source_type="vendor",
        source_name="Vendor",
        text="Our tool is best in class and customers love it.",
        publication_date="2026-01-01",
        metadata={},
    )
    claims = [
        ClaimCreate(
            claim_text="The tool is best in class.",
            evidence_type="anecdotal",
            confidence=0.2,
        )
    ]

    score = CredibilityScorer().score(doc, claims)

    assert score < 60
    assert usage_bucket(score) == "background_only"

