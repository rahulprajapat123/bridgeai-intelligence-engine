from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

import httpx

from research_intel.config import Settings
from research_intel.ingestion.base import FetchResult, HttpSourceClient, RawDocument, first_text


class ApifyActorClient(HttpSourceClient):
    actor_id = ""

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, api_key=settings.apify_api_token)
        self.settings = settings
        self.serper_key = settings.serper_api_key

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        try:
            payload = await self.build_input(query, max_results)
            response = await self.http.post(
                f"https://api.apify.com/v2/acts/{self.actor_id.replace('/', '~')}/run-sync-get-dataset-items",
                params={"token": self.api_key, "timeout": min(self.settings.apify_scraper_timeout_secs, 180)},
                json=payload, timeout=min(self.settings.apify_scraper_timeout_secs + 20, 200),
            )
            response.raise_for_status()
            items = response.json()
            if not isinstance(items, list):
                return FetchResult(source_name=self.name, error="Actor returned a non-list dataset")
            docs = [doc for item in items[:max_results] if (doc := self.normalize(item, domain))]
            return FetchResult(source_name=self.name, documents=docs)
        except httpx.HTTPStatusError as exc:
            return FetchResult(source_name=self.name, error=f"Apify actor request failed with HTTP {exc.response.status_code}")
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))

    async def seed_urls(self, query: str, limit: int) -> list[dict[str, str]]:
        if not self.serper_key:
            return []
        response = await self.http.post("https://google.serper.dev/search", headers={"X-API-KEY": self.serper_key, "Content-Type": "application/json"}, json={"q": f"{query} latest news", "num": min(limit, 10)})
        response.raise_for_status()
        return [{"url": row["link"]} for row in response.json().get("organic", []) if row.get("link")][:limit]

    async def build_input(self, query: str, max_results: int) -> dict: raise NotImplementedError
    def normalize(self, item: dict[str, Any], domain: str | None) -> RawDocument | None: raise NotImplementedError


class FastRedditClient(ApifyActorClient):
    """Fast Reddit scraper using cryptosignals/reddit-scraper-fast actor."""
    name = "Apify Reddit Fast"; route_name = "apify_reddit_fast"; source_type = "social"; actor_id = "cryptosignals/reddit-scraper-fast"
    async def build_input(self, query, max_results):
        return {
            "search": query,
            "searchType": "posts",
            "sortBy": "new",
            "timeFilter": "week",
            "maxItems": max_results,
            "includeComments": False
        }
    def normalize(self, item, domain):
        url = item.get("url") or item.get("permalink")
        if not url: return None
        if not url.startswith("http"):
            url = f"https://reddit.com{url}"
        return RawDocument(
            item.get("title") or "Reddit post", 
            url, 
            "social", 
            self.name, 
            first_text(item.get("selftext"), item.get("body"), item.get("description"), item.get("title")), 
            publication_date=item.get("created_utc") or item.get("createdAt"), 
            metadata={
                "domain": domain, 
                "score": item.get("score", 0), 
                "num_comments": item.get("num_comments", 0) or item.get("numComments", 0), 
                "subreddit": item.get("subreddit") or item.get("subreddit_name_prefixed", "").replace("r/", ""),
                "engagement": {"score": item.get("score", 0), "comments": item.get("num_comments", 0) or item.get("numComments", 0)}
            }
        )


class SoonToOpenBusinessesClient(ApifyActorClient):
    name = "Apify Soon-to-Open Businesses"; route_name = "apify_business_leads"; source_type = "news"; actor_id = "xmiso_scrapers/soon-to-open-businesses-leads-scraper-google-maps"
    async def build_input(self, query, max_results):
        return {"business_type": "All", "opening_date": "All", "country": "All", "state": "All", "max_results": max_results}
    def normalize(self, item, domain):
        url = item.get("website") or item.get("googleMapsUrl") or item.get("url")
        if not url: return None
        title = item.get("title") or item.get("name") or "Soon-to-open business"
        text = ". ".join(str(x) for x in (item.get("categoryName"), item.get("address"), item.get("description"), item.get("openingDate")) if x)
        return RawDocument(title, url, "news", self.name, text or title, metadata={"domain": domain, "business_signal": True, **{k: item.get(k) for k in ("city", "state", "countryCode", "phone", "openingDate")}})


class GoogleTrendsScraperClient(ApifyActorClient):
    """Google Trends scraper - DISABLED (Apify actor returns 404)"""
    name = "Google Trends"; route_name = "google_trends"; source_type = "news"; actor_id = "trudax/google-trends-scraper"
    
    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        # Disabled: Actor returns 404 - may be deprecated or removed
        super().__init__(http, settings)
        self.api_key = None  # Force disabled
    async def build_input(self, query, max_results):
        return {
            "searchTerms": [query],
            "timeRange": "now 7-d",  # Last 7 days
            "geo": "",  # Worldwide
            "maxItems": max_results,
            "isMultipleTerms": False
        }
    def normalize(self, item, domain):
        # Google Trends returns interest over time and related queries
        # Create a synthetic document from the trend data
        title = item.get("searchTerm") or query
        if item.get("relatedQuery"):
            title = f"Trending: {item.get('relatedQuery')}"
        
        # Build text content from trend data
        text_parts = []
        if item.get("searchTerm"):
            text_parts.append(f"Search term: {item.get('searchTerm')}")
        if item.get("value"):
            text_parts.append(f"Interest level: {item.get('value')}")
        if item.get("formattedValue"):
            text_parts.append(f"Trend: {item.get('formattedValue')}")
        if item.get("relatedQuery"):
            text_parts.append(f"Related: {item.get('relatedQuery')}")
        
        text = ". ".join(text_parts) if text_parts else title
        
        # Use Google Trends URL
        url = item.get("url") or f"https://trends.google.com/trends/explore?q={item.get('searchTerm', query)}"
        
        return RawDocument(
            title, 
            url, 
            "news", 
            self.name, 
            text,
            metadata={
                "domain": domain,
                "trend_value": item.get("value"),
                "geo": item.get("geo", "Worldwide")
            }
        )


class DeepWebsiteCrawlerClient(ApifyActorClient):
    name = "Apify Deep Website Crawler"; route_name = "apify_deep_crawler"; source_type = "web"; actor_id = "6sigmag/deep-website-content-crawler"
    async def build_input(self, query, max_results):
        # This community actor's schema explicitly expects bare website domains
        # (example.com), not Apify Request objects or protocol-prefixed URLs.
        domains = []
        for row in await self.seed_urls(query, max_results):
            host = urlsplit(row["url"]).netloc.lower()
            if host and host not in domains: domains.append(host)
        return {"startUrls": domains}
    def normalize(self, item, domain): return normalize_web_item(item, domain, self.name)


class PlaywrightActorClient(ApifyActorClient):
    name = "Apify Playwright Scraper"; route_name = "apify_playwright"; source_type = "web"; actor_id = "apify/playwright-scraper"
    async def build_input(self, query, max_results):
        return {"startUrls": await self.seed_urls(query, max_results), "proxyConfiguration": {"useApifyProxy": True}, "maxPagesPerCrawl": max_results, "maxResultsPerCrawl": max_results, "maxCrawlingDepth": 0, "maxConcurrency": 2, "pageLoadTimeoutSecs": 30, "waitUntil": "domcontentloaded", "downloadMedia": False, "downloadCss": False, "pageFunction": "async function pageFunction(context) { const { page, request } = context; return { url: request.loadedUrl || request.url, title: await page.title(), text: await page.locator('body').innerText().catch(() => '') }; }"}
    def normalize(self, item, domain): return normalize_web_item(item, domain, self.name)


def normalize_web_item(item: dict[str, Any], domain: str | None, source_name: str) -> RawDocument | None:
    url = item.get("url") or item.get("loadedUrl") or item.get("canonicalUrl")
    if not url: return None
    title = item.get("title") or item.get("metadata", {}).get("title") or "Web content"
    text = first_text(item.get("text"), item.get("markdown"), item.get("content"), item.get("html"), title)
    return RawDocument(title, url, "web", source_name, text, publication_date=item.get("publishedAt") or item.get("date"), metadata={"domain": domain, "actor_output": {k: v for k, v in item.items() if k not in {"text", "markdown", "content", "html"}}})


def build_apify_actor_clients(http: httpx.AsyncClient, settings: Settings):
    return [
        FastRedditClient(http, settings), 
        GoogleTrendsScraperClient(http, settings),
        SoonToOpenBusinessesClient(http, settings), 
        DeepWebsiteCrawlerClient(http, settings), 
        PlaywrightActorClient(http, settings)
    ]
