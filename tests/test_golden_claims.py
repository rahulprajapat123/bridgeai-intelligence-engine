from __future__ import annotations

import json
from pathlib import Path

from research_intel.config import Settings
from research_intel.ingestion.base import RawDocument
from research_intel.intelligence.extraction import ClaimExtractor


FIXTURE = Path(__file__).parent / "fixtures" / "golden_claim_documents.json"


def test_golden_claim_documents_extract_expected_signals():
    extractor = ClaimExtractor(Settings(database_connection_string="sqlite:///:memory:"))
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))

    for case in cases:
        doc = RawDocument(
            title=case["title"],
            source_url=case["source_url"],
            source_type=case["source_type"],
            source_name=case["source_name"],
            text=case["text"],
            metadata={"domain": case["domain"]},
        )
        claims = extractor.extract(doc)
        assert claims, case["title"]
        assert any(case["expected_metric"] in claim.metrics for claim in claims), case["title"]
        assert any(case["expected_tag"] in claim.applicability_tags for claim in claims), case["title"]
