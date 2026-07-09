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

        cleaned = [self._clean_query(item) for item in base if item]
        return unique_keep_order([item for item in cleaned if len(item) >= 3])[: max(3, min(top_k, 12))]

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
