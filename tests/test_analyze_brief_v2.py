from research_intel.config import Settings
from research_intel.ingestion.base import RawDocument
from research_intel.services.analyze_brief_service import AnalyzeBriefService
from research_intel.services.factory import build_services
from research_intel.services.query_planner import QueryPlanner
from research_intel.services.source_router import SourceRouter


BRIEF = """Build a secure revenue intelligence assistant. It must analyze CRM opportunities,
call transcripts, marketing engagement, product usage and customer success signals; predict
pipeline and churn risk; recommend next-best actions; integrate with Salesforce, HubSpot,
Snowflake and Slack; preserve citations; enforce human approval, role-based access, audit logs
and PII controls. Compare build versus buy, current open-source frameworks, evaluation metrics,
costs, risks, a 90-day pilot and measurable success criteria."""


def test_brief_analysis_extracts_project_aspects_and_queries():
    services = build_services(Settings(database_connection_string="sqlite:///:memory:"))
    analyzer = AnalyzeBriefService(services)
    analysis = services.brief.analyze(BRIEF)
    understanding = analyzer._brief_understanding(analysis, "Sales", ["query"], BRIEF)

    assert len(understanding["requirements"]) >= 4
    assert understanding["integrations"]
    assert understanding["governance_requirements"]
    assert understanding["evaluation_requirements"]
    assert "Salesforce" in analysis.tools_or_platforms
    queries = QueryPlanner().plan(BRIEF, analysis, "Sales", 20)
    assert any("revenue intelligence" in query.lower() for query in queries)


def test_source_routing_and_ranking_preserve_multi_source_coverage():
    routes = SourceRouter().route_names(
        "Sales", include_papers=True, include_github=True, include_blogs=True, include_news=True
    )
    assert {"semantic_scholar", "github", "devto", "google_news_rss"} <= set(routes)

    services = build_services(Settings(database_connection_string="sqlite:///:memory:"))
    analyzer = AnalyzeBriefService(services)
    documents = []
    for source_type, source_name in [
        ("academic", "OpenAlex"), ("code", "GitHub"), ("blog", "Dev.to"), ("news", "GNews")
    ]:
        for index in range(5):
            documents.append(RawDocument(
                title=f"Revenue intelligence {source_name} {index}",
                source_url=f"https://example.com/{source_name}/{index}",
                source_type=source_type,
                source_name=source_name,
                text="Revenue intelligence CRM pipeline risk implementation benchmark case study",
                publication_date="2026-07-01",
            ))
    ranked = analyzer.ranker.rank(documents, BRIEF, ["revenue intelligence"], "Sales")
    selected = analyzer._balanced_selection(
        ranked, 12, include_papers=True, include_github=True, include_blogs=True, include_news=True
    )
    groups = analyzer._evidence_groups(selected)
    assert all(len(groups[name]) >= 1 for name in ("papers", "github_repositories", "blogs", "news"))


def test_sales_solution_solves_the_uploaded_project_not_the_research_pipeline():
    services = build_services(Settings(database_connection_string="sqlite:///:memory:"))
    analysis = services.brief.analyze(BRIEF).model_copy(update={"primary_domain": "Sales"})
    solution = AnalyzeBriefService(services).implementation_planner.build(BRIEF, analysis, [], [])

    assert "revenue-intelligence decision layer" in solution["recommended_approach"]
    assert "Salesforce/HubSpot" in solution["architecture"]
    assert "90" in " ".join(solution["timeline"])
