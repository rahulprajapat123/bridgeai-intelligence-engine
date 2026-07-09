from __future__ import annotations

import json
from pathlib import Path

from research_intel.intelligence.brief import BriefUnderstandingService
from research_intel.ingestion.base import RawDocument, SourcePolicy


FIXTURE = Path(__file__).parent / "fixtures" / "golden_briefs.json"


def test_golden_briefs_classification_and_routes():
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))
    service = BriefUnderstandingService()

    for case in cases:
        analysis = service.analyze(case["text"])
        assert analysis.primary_domain == case["primary_domain"], case["id"]
        for domain in case.get("secondary_domains", []):
            assert domain in analysis.secondary_domains, case["id"]
        for route in case["required_routes"]:
            assert route in analysis.retrieval_routes, case["id"]
        for route in case["forbidden_routes"]:
            assert route not in analysis.retrieval_routes, case["id"]


def test_source_policy_rejects_known_low_signal_hosts():
    policy = SourcePolicy()
    blocked = [
        "https://www.linkedin.com/company/example",
        "https://x.com/example/status/123",
        "https://youtube.com/watch?v=123",
    ]

    for url in blocked:
        assert not policy.allowed(
            RawDocument(
                title="blocked",
                source_url=url,
                source_type="web",
                source_name="Test",
                text="blocked",
            )
        )
