from __future__ import annotations

from research_intel.schemas import BriefAnalysis
from research_intel.utils import unique_keep_order


class QueryPlanner:
    def plan(self, brief_text: str, analysis: BriefAnalysis, domain: str, top_k: int) -> list[str]:
        base: list[str] = []
        base.extend(analysis.query_decomposition)
        base.extend(analysis.research_questions)
        base.extend(analysis.keywords[:8])
        base.extend(
            [
                analysis.intent,
                analysis.objective,
                f"{domain} implementation architecture tools risks cost",
                f"{domain} case study benchmark best practices",
            ]
        )
        if analysis.technologies:
            base.append(" ".join(analysis.technologies + ["implementation", "benchmark"]))
        if analysis.companies:
            base.append(" ".join(analysis.companies[:5] + ["comparison", "market", "strategy"]))
        base.extend(self._aspect_queries(brief_text, domain))

        cleaned = [self._clean_query(item) for item in base if item]
        return unique_keep_order([item for item in cleaned if len(item) >= 3])[: max(3, min(top_k, 12))]

    def _aspect_queries(self, text: str, domain: str) -> list[str]:
        lowered = text.lower()
        queries = [
            f"{domain} solution architecture implementation case study",
            f"{domain} latest research evaluation benchmark",
            f"{domain} open source tools GitHub production",
            f"{domain} market news vendor product developments",
        ]
        if any(term in lowered for term in ("revenue", "sales", "crm", "pipeline", "revops")):
            queries.extend([
                "revenue intelligence CRM pipeline risk forecasting next best action",
                "sales AI churn prediction customer success product usage signals",
                "Salesforce HubSpot Snowflake revenue intelligence architecture",
            ])
        if any(term in lowered for term in ("security", "pii", "audit", "role-based", "governance")):
            queries.append(f"{domain} AI security PII RBAC audit human approval governance")
        if any(term in lowered for term in ("build versus buy", "build vs buy", "cost")):
            queries.append(f"{domain} build versus buy TCO vendor open source comparison")
        return queries

    def expand(self, queries: list[str], domain: str) -> list[str]:
        expansions: list[str] = []
        domain_terms = {
            "AI/ML": ["evaluation", "RAG", "LLM", "architecture", "benchmark"],
            "Marketing": ["martech", "customer journey", "campaign performance", "case study"],
            "Sales": ["sales automation", "CRM", "revenue operations", "case study"],
            "Insights/Analytics": ["analytics workflow", "dashboard", "insight generation", "measurement"],
        }
        terms = domain_terms.get(domain, ["implementation", "business value", "case study"])
        for query in queries:
            expansions.append(query)
            expansions.append(f"{query} {' '.join(terms[:3])}")
        return unique_keep_order(expansions)[:16]

    def _clean_query(self, value: str) -> str:
        return " ".join(str(value).replace("\n", " ").split())[:220]
