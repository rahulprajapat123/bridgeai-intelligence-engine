"""Shared discovery and relevance taxonomy for Daily Intelligence."""
from __future__ import annotations

import re


TOPIC_FAMILIES: dict[str, tuple[str, ...]] = {
    "buyers_and_operators": (
        "chief revenue officer", "vp sales", "vp marketing", "head of ai",
        "product manager", "solutions architect", "customer success manager",
        "sales engineer", "growth manager", "consulting firm", "mckinsey",
        "deloitte", "accenture",
    ),
    "sales_and_revenue": (
        "sales enablement", "revenue operations", "sales automation", "crm",
        "pipeline management", "sales forecasting", "lead scoring",
        "lead qualification", "account based selling", "enterprise sales",
        "solution selling", "consultative selling", "sales intelligence",
        "revenue intelligence", "customer acquisition", "customer retention",
        "renewal", "upsell", "cross sell",
    ),
    "marketing_and_growth": (
        "go to market strategy", "product marketing", "growth marketing",
        "demand generation", "lead generation", "content marketing",
        "performance marketing", "brand strategy", "digital marketing",
        "marketing automation", "customer journey", "customer segmentation",
        "personalization", "customer engagement", "product led growth",
        "growth strategy", "campaign analytics", "conversion optimization",
        "marketing analytics", "competitive intelligence",
    ),
    "customer_and_product_intelligence": (
        "customer analytics", "customer intelligence", "customer 360",
        "voice of customer", "customer success", "customer experience",
        "customer health score", "net promoter score", "customer lifetime value",
        "churn prediction", "behavior analytics", "product analytics",
        "feature adoption", "usage analytics", "predictive analytics",
        "customer insights", "journey analytics", "retention analytics",
        "sentiment analysis", "recommendation engine",
    ),
    "enterprise_technology": (
        "digital transformation", "cloud computing", "saas", "api economy",
        "business intelligence", "data analytics", "enterprise automation",
        "workflow automation", "process automation", "hyperautomation",
        "business process management", "enterprise search",
        "knowledge management", "data governance", "cybersecurity",
        "identity management", "low code", "no code", "platform engineering",
        "digital workplace",
    ),
    "ai_and_automation": (
        "artificial intelligence", "machine learning", "generative ai",
        "agentic ai", "ai agent", "multi agent", "large language model", "llm",
        "retrieval augmented generation", "rag", "enterprise ai",
        "ai infrastructure", "developer tools", "open source",
    ),
    "strategic_companies": (
        "microsoft", "salesforce", "hubspot", "aws", "amazon web services",
        "google cloud", "openai", "saas company",
    ),
}

DEFAULT_DAILY_TOPICS = [term for values in TOPIC_FAMILIES.values() for term in values]

# Spread one-query connectors across commercial topic families instead of making
# every source search for the same AI phrase.
ROUTE_QUERY_FAMILY = {
    "arxiv": "customer_and_product_intelligence",
    "semantic_scholar": "sales_and_revenue",
    "openalex": "marketing_and_growth",
    "paperswithcode": "ai_and_automation",
    "core": "enterprise_technology",
    "github": "enterprise_technology",
    "huggingface": "customer_and_product_intelligence",
    "npm": "sales_and_revenue",
    "pypi": "marketing_and_growth",
    "newsapi": "sales_and_revenue",
    "gnews": "marketing_and_growth",
    "google_news_rss": "customer_and_product_intelligence",
    "serpapi_news": "buyers_and_operators",
    "guardian": "enterprise_technology",
    "nytimes": "strategic_companies",
    "hackernews": "enterprise_technology",
    "gdelt": "sales_and_revenue",
    "producthunt": "marketing_and_growth",
    "devto": "enterprise_technology",
    "rss": "buyers_and_operators",
    "towardsdatascience": "customer_and_product_intelligence",
    "kdnuggets": "sales_and_revenue",
    "importai": "ai_and_automation",
    "serper": "strategic_companies",
    "exa": "buyers_and_operators",
    "tavily": "marketing_and_growth",
    "jina": "customer_and_product_intelligence",
    "you": "sales_and_revenue",
    "apify_reddit": "sales_and_revenue",
    "apify_reddit_fast": "marketing_and_growth",
    "stackexchange": "enterprise_technology",
    "apify_news": "enterprise_technology",
    "apify_business_leads": "buyers_and_operators",
}


def query_for_route(route_name: str, fallback_topics: list[str], max_terms: int = 4) -> str:
    family = ROUTE_QUERY_FAMILY.get(route_name, "ai_and_automation")
    terms = TOPIC_FAMILIES[family][:max_terms]
    return " ".join(terms)[:180] or " ".join(fallback_topics[:2])[:180]


def matched_scope_terms(text: str) -> set[str]:
    normalized = re.sub(r"[-_/]+", " ", (text or "").lower())
    normalized = re.sub(r"\s+", " ", normalized)
    tokens = set(re.findall(r"[a-z0-9]+", normalized))
    matches: set[str] = set()
    for term in DEFAULT_DAILY_TOPICS:
        if (term in normalized) if " " in term else (term in tokens):
            matches.add(term)
    return matches


def is_in_intelligence_scope(text: str) -> bool:
    return bool(matched_scope_terms(text))


def relevance_score(text: str) -> float:
    matches = matched_scope_terms(text)
    # One specific phrase is meaningful; additional independent matches raise
    # confidence without requiring "AI" in the headline.
    return float(min(100, 20 + max(0, len(matches) - 1) * 12)) if matches else 0.0
