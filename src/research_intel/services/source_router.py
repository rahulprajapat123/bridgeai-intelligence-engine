from __future__ import annotations


DOMAIN_SOURCE_ROUTING: dict[str, list[str]] = {
    "AI/ML": [
        "semantic_scholar",
        "openalex",
        "github",
        "huggingface",
        "arxiv",
        "paperswithcode",
        "exa",
        "tavily",
        "serper",
        "news",
        "social",
        "video",
    ],
    "Developer Tooling": ["github", "technical_blogs", "hackernews", "exa", "tavily", "serper", "social", "video"],
    "Competitive Intelligence": [
        "news",
        "exa",
        "tavily",
        "serper",
        "guardian",
        "nytimes",
        "industry_blogs",
        "social",
    ],
    "Market Research": ["news", "guardian", "nytimes", "exa", "tavily", "serper", "social"],
    "Partner Programs": ["news", "channel_futures", "crn", "g2", "exa", "tavily", "serper"],
    "Healthcare": ["pubmed", "semantic_scholar", "openalex", "news"],
    "Finance": ["news", "market_sources", "papers", "exa", "tavily", "serper", "social"],
    "Marketing": ["news", "martech_blogs", "case_studies", "exa", "tavily", "serper", "social", "video"],
    "Sales": ["sales_tech_blogs", "news", "case_studies", "exa", "tavily", "serper", "social"],
    "Insights/Analytics": ["analytics_blogs", "news", "papers", "github", "exa", "tavily", "serper", "social"],
}


SOURCE_ALIASES: dict[str, set[str]] = {
    "news": {"newsapi", "gnews", "google_news_rss", "serpapi_news", "guardian", "nytimes", "apify_news"},
    "papers": {"semantic_scholar", "openalex", "arxiv", "paperswithcode"},
    "social": {"apify_reddit", "apify_twitter"},
    "video": {"apify_youtube"},
    "technical_blogs": {"exa", "tavily", "serper", "firecrawl", "apify"},
    "industry_blogs": {"exa", "tavily", "serper", "firecrawl", "apify"},
    "martech_blogs": {"exa", "tavily", "serper", "firecrawl", "apify"},
    "sales_tech_blogs": {"exa", "tavily", "serper", "firecrawl", "apify"},
    "analytics_blogs": {"exa", "tavily", "serper", "firecrawl", "apify"},
    "case_studies": {"exa", "tavily", "serper", "firecrawl"},
    "market_sources": {"newsapi", "gnews", "google_news_rss", "serpapi_news", "exa", "tavily", "serper"},
    "arxiv": {"arxiv"},
    "github": {"github"},
    "huggingface": {"huggingface"},
    "openalex": {"openalex"},
    "semantic_scholar": {"semantic_scholar"},
    "exa": {"exa"},
    "tavily": {"tavily"},
    "serper": {"serper", "apify_google"},
    "guardian": {"guardian"},
    "nytimes": {"nytimes"},
}


class SourceRouter:
    def route_names(
        self,
        domain: str,
        *,
        include_papers: bool,
        include_github: bool,
        include_blogs: bool,
        include_news: bool,
    ) -> list[str]:
        normalized = self._normalize_domain(domain)
        route_groups = DOMAIN_SOURCE_ROUTING.get(normalized, DOMAIN_SOURCE_ROUTING["AI/ML"])
        routes: list[str] = []
        for group in route_groups:
            routes.extend(sorted(SOURCE_ALIASES.get(group, {group})))

        if include_papers:
            routes.extend(["semantic_scholar", "openalex", "arxiv"])
        if include_github:
            routes.append("github")
        if include_blogs:
            routes.extend(["exa", "tavily", "serper", "firecrawl"])
        if include_news:
            routes.extend(["newsapi", "gnews", "google_news_rss", "serpapi_news", "guardian", "nytimes"])

        routes = self._filter_by_include_flags(
            routes,
            include_papers=include_papers,
            include_github=include_github,
            include_blogs=include_blogs,
            include_news=include_news,
        )
        return self._unique(routes)

    def _normalize_domain(self, domain: str) -> str:
        lowered = (domain or "").strip().lower()
        if any(term in lowered for term in ("ai", "ml", "rag", "llm", "machine learning")):
            return "AI/ML"
        if "developer" in lowered or "tool" in lowered:
            return "Developer Tooling"
        if "competitive" in lowered:
            return "Competitive Intelligence"
        if "market" in lowered:
            return "Market Research"
        if "partner" in lowered or "channel" in lowered:
            return "Partner Programs"
        if "health" in lowered:
            return "Healthcare"
        if "finance" in lowered:
            return "Finance"
        if "marketing" in lowered:
            return "Marketing"
        if "sales" in lowered:
            return "Sales"
        if "insight" in lowered or "analytic" in lowered:
            return "Insights/Analytics"
        return domain if domain in DOMAIN_SOURCE_ROUTING else "AI/ML"

    def _filter_by_include_flags(
        self,
        routes: list[str],
        *,
        include_papers: bool,
        include_github: bool,
        include_blogs: bool,
        include_news: bool,
    ) -> list[str]:
        papers = {"semantic_scholar", "openalex", "arxiv", "pubmed", "paperswithcode"}
        github = {"github"}
        news = {"newsapi", "gnews", "google_news_rss", "serpapi_news", "guardian", "nytimes", "news"}
        blogs = {"exa", "tavily", "serper", "firecrawl", "apify", "apify_google"}
        filtered = []
        for route in routes:
            if route in papers and not include_papers:
                continue
            if route in github and not include_github:
                continue
            if route in news and not include_news:
                continue
            if route in blogs and not include_blogs:
                continue
            filtered.append(route)
        return filtered

    def _unique(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for value in values:
            if value not in seen:
                output.append(value)
                seen.add(value)
        return output
