from datetime import UTC, datetime, timedelta

import pytest

from research_intel.signal_filter.config import CATEGORY_CAPS, MIN_SCORES, SignalFilterConfig
from research_intel.signal_filter.models import CriterionScore, SignalItem, SignalScores, SourceMetadata, SourceType
from research_intel.signal_filter.pipeline import FilterContext, build_default_pipeline
from research_intel.signal_filter.text import canonicalize_url, cosine_similarity, normalize_text, recency_weight


def score(values=(4, 4, 4, 4, 3), confidence=.9):
    names = list(MIN_SCORES)
    return SignalScores(**{name: CriterionScore(score=value, confidence=confidence, rationale="test", evidence=["source passage"]) for name, value in zip(names, values, strict=True)})


def item(identifier, title="Acme launches workflow automation", body="Acme announced a new workflow automation product for customers.", **kwargs):
    return SignalItem(item_id=identifier, title=title, body=body, metadata=SourceMetadata(source_url=kwargs.pop("url", f"https://example.com/{identifier}"), source_name="Example", published_at=datetime.now(UTC)), scores=kwargs.pop("scores", score()), why_it_matters=kwargs.pop("why_it_matters", "Acme customers can automate invoice review."), the_move=kwargs.pop("the_move", "Product should validate invoice accuracy in a pilot."), overall_confidence=kwargs.pop("confidence", .9), **kwargs)


def test_regression_defaults():
    config = SignalFilterConfig()
    assert config.lexical_duplicate_threshold == .82
    assert config.uniqueness_similarity_threshold == .60
    assert config.min_scores == MIN_SCORES
    assert config.min_total_score == 15
    assert config.category_caps == CATEGORY_CAPS
    assert config.total_item_cap == 20
    assert config.max_pdf_pages == 60
    assert config.max_candidate_items == 40


def test_normalization_url_similarity_and_recency():
    assert normalize_text(" A&nbsp;  B\n") == "A B"
    assert canonicalize_url("HTTPS://Example.COM/a/?utm_source=x&b=2#part") == "https://example.com/a?b=2"
    assert cosine_similarity("alpha beta", "alpha beta") == pytest.approx(1)
    assert recency_weight(datetime.now(UTC)-timedelta(days=7), 7) == pytest.approx(.5, rel=.01)


@pytest.mark.asyncio
async def test_exact_and_lexical_duplicates_are_audited():
    first = item("one", url="https://example.com/story?utm_source=x")
    exact = item("two", url="https://example.com/story")
    lexical = item("three", body="Acme announced its new workflow automation product for enterprise customers today.", url="https://another.example/story")
    result = await build_default_pipeline().run([first, exact, lexical])
    assert exact.status == "duplicate"
    assert lexical.status == "duplicate"
    assert {d.reason_code for d in result.decisions} >= {"EXACT_DUPLICATE", "LEXICAL_DUPLICATE"}


@pytest.mark.asyncio
async def test_individual_minimum_is_non_compensable():
    weak = item("weak", scores=score((2, 5, 5, 5, 5)))
    result = await build_default_pipeline().run([weak])
    assert weak.status == "rejected"
    assert any(d.reason_code == "SCORE_MINIMUM_FAILED" for d in result.decisions)


@pytest.mark.asyncio
async def test_low_confidence_routes_to_review():
    low = item("low", scores=score(confidence=.6), confidence=.6)
    await build_default_pipeline().run([low])
    assert low.status == "review"


@pytest.mark.asyncio
async def test_category_cap_is_not_quality_rejection():
    config = SignalFilterConfig(category_caps={**CATEGORY_CAPS, "news": 1})
    a = item("a"); b = item("b", title="Beta releases customer analytics", body="Beta released customer analytics with new reporting features.")
    a.metadata.source_type = b.metadata.source_type = SourceType.NEWS
    result = await build_default_pipeline(config).run([a, b])
    assert sorted(x.status for x in [a, b]) == ["accepted", "qualified_but_cut_for_volume"]
    assert any(d.decision == "qualified_but_cut_for_volume" for d in result.decisions)


@pytest.mark.asyncio
async def test_deny_list_failure_requires_review_without_provider():
    vague = item("vague", why_it_matters="Important for the AI landscape.")
    await build_default_pipeline().run([vague], FilterContext())
    assert vague.status == "review"
