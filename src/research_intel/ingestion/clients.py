from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime, timedelta
from html import unescape
from typing import Any

import feedparser
import httpx
from bs4 import BeautifulSoup

from research_intel.config import Settings
from research_intel.ingestion.base import FetchResult, HttpSourceClient, RawDocument, first_text


def _strip_html(value: str | None) -> str:
    if not value:
        return ""
    return BeautifulSoup(unescape(value), "html.parser").get_text(" ", strip=True)


def _openalex_abstract(inverted_index: dict[str, list[int]] | None) -> str:
    if not inverted_index:
        return ""
    positions: list[tuple[int, str]] = []
    for token, indexes in inverted_index.items():
        for index in indexes:
            positions.append((index, token))
    return " ".join(token for _, token in sorted(positions))


class OpenAlexClient(HttpSourceClient):
    name = "OpenAlex"
    route_name = "openalex"
    source_type = "academic"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, enabled_without_key=True)
        self.email = settings.openalex_contact_email
        self.min_year = settings.min_publication_year

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        params = {
            "search": query,
            "per-page": min(max_results, 100),
            "filter": f"from_publication_date:{self.min_year}-01-01",
        }
        if self.email:
            params["mailto"] = str(self.email)
        try:
            response = await self.http.get("https://api.openalex.org/works", params=params)
            response.raise_for_status()
            payload = response.json()
            docs: list[RawDocument] = []
            for item in payload.get("results", []):
                title = item.get("title") or "Untitled OpenAlex work"
                abstract = _openalex_abstract(item.get("abstract_inverted_index"))
                authors = [
                    authorship.get("author", {}).get("display_name", "")
                    for authorship in item.get("authorships", [])
                ]
                url = (
                    item.get("primary_location", {}).get("landing_page_url")
                    or item.get("doi")
                    or item.get("id")
                )
                docs.append(
                    RawDocument(
                        title=title,
                        source_url=url,
                        source_type="academic",
                        source_name=self.name,
                        text=f"{title}. {abstract}",
                        authors=[author for author in authors if author],
                        publication_date=item.get("publication_date"),
                        metadata={
                            "citation_count": item.get("cited_by_count", 0),
                            "year": item.get("publication_year"),
                            "domain": domain,
                        },
                    )
                )
            return FetchResult(source_name=self.name, documents=docs)
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))


class SemanticScholarClient(HttpSourceClient):
    """
    Semantic Scholar API client.
    Rate limit: 1 request per second (strictly enforced).
    Uses class-level lock with 1.5 second gaps to ensure compliance.
    Subscription tier: 1 request/second, enforced via delays.
    """
    name = "Semantic Scholar"
    route_name = "semantic_scholar"
    source_type = "academic"
    _last_request_time: float = 0.0
    _lock = asyncio.Lock()

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        # Enabled with API key or without (public tier also has 1 req/sec limit)
        super().__init__(http, api_key=settings.semantic_scholar_api_key, enabled_without_key=True)

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        if not self.api_key:
            return FetchResult(
                source_name=self.name,
                error="Semantic Scholar requires API key. Use OpenAlex or arXiv as free alternatives."
            )
        
        headers = {"x-api-key": self.api_key}
        params = {
            "query": query,
            "limit": min(max_results, 100),
            "fields": "title,abstract,url,authors,year,citationCount,publicationDate,venue",
        }
        try:
            # Use class-level lock to ensure only one request at a time
            async with self._lock:
                # Calculate time since last request
                import time
                current_time = time.time()
                time_since_last = current_time - SemanticScholarClient._last_request_time
                
                # If less than 2 seconds have passed, wait (increased buffer)
                if time_since_last < 2.0:
                    await asyncio.sleep(2.0 - time_since_last)
                
                response = await self.http.get(
                    "https://api.semanticscholar.org/graph/v1/paper/search",
                    params=params,
                    headers=headers,
                    timeout=40.0
                )
                
                # Update last request time
                SemanticScholarClient._last_request_time = time.time()
            
            response.raise_for_status()
            docs = []
            for item in response.json().get("data", []):
                title = item.get("title") or "Untitled Semantic Scholar paper"
                abstract = item.get("abstract") or ""
                authors = [author.get("name", "") for author in item.get("authors", [])]
                docs.append(
                    RawDocument(
                        title=title,
                        source_url=item.get("url") or f"https://www.semanticscholar.org/paper/{item.get('paperId')}",
                        source_type="academic",
                        source_name=self.name,
                        text=f"{title}. {abstract}",
                        authors=[author for author in authors if author],
                        publication_date=item.get("publicationDate") or str(item.get("year") or ""),
                        metadata={
                            "citation_count": item.get("citationCount", 0),
                            "venue": item.get("venue"),
                            "domain": domain,
                        },
                    )
                )
            return FetchResult(source_name=self.name, documents=docs)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                return FetchResult(
                    source_name=self.name, 
                    error="Rate limit exceeded (1 req/sec). Consider using OpenAlex or arXiv as alternatives."
                )
            return FetchResult(source_name=self.name, error=str(exc))
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))


class ArxivClient(HttpSourceClient):
    name = "arXiv"
    route_name = "arxiv"
    source_type = "academic"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, enabled_without_key=True)
        self.min_year = settings.min_publication_year

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        search = f'all:"{query}" AND (cat:cs.IR OR cat:cs.CL)'
        params = {
            "search_query": search,
            "start": 0,
            "max_results": min(max_results, 100),
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        try:
            response = await self.http.get("https://export.arxiv.org/api/query", params=params)
            response.raise_for_status()
            feed = feedparser.parse(response.text)
            docs: list[RawDocument] = []
            for entry in feed.entries:
                published = getattr(entry, "published", "")
                year_match = re.search(r"(20\d{2}|19\d{2})", published)
                if year_match and int(year_match.group(1)) < self.min_year:
                    continue
                authors = [author.get("name", "") for author in getattr(entry, "authors", [])]
                docs.append(
                    RawDocument(
                        title=getattr(entry, "title", "Untitled arXiv paper").replace("\n", " "),
                        source_url=getattr(entry, "link", ""),
                        source_type="academic",
                        source_name=self.name,
                        text=f"{getattr(entry, 'title', '')}. {_strip_html(getattr(entry, 'summary', ''))}",
                        authors=[author for author in authors if author],
                        publication_date=published[:10],
                        metadata={"domain": domain, "categories": getattr(entry, "tags", [])},
                    )
                )
            return FetchResult(source_name=self.name, documents=docs)
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))


class PapersWithCodeClient(HttpSourceClient):
    """
    Papers with Code client using arXiv ML categories.
    PapersWithCode.com API is deprecated. Using arXiv ML categories as alternative.
    """
    name = "Papers with Code"
    route_name = "paperswithcode"
    source_type = "academic"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, enabled_without_key=True)
        self.min_year = settings.min_publication_year

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        """
        Fetch ML papers from arXiv (PapersWithCode API deprecated).
        """
        try:
            # Use arXiv with ML categories
            search = f'all:"{query}" AND (cat:cs.LG OR cat:cs.AI OR cat:stat.ML OR cat:cs.CL OR cat:cs.CV)'
            params = {
                "search_query": search,
                "start": 0,
                "max_results": min(max_results, 50),
                "sortBy": "relevance",
                "sortOrder": "descending",
            }
            response = await self.http.get(
                "https://export.arxiv.org/api/query",
                params=params,
                timeout=30.0
            )
            response.raise_for_status()
            feed = feedparser.parse(response.text)
            
            docs: list[RawDocument] = []
            for entry in feed.entries:
                published = getattr(entry, "published", "")
                year_match = re.search(r"(20\d{2}|19\d{2})", published)
                if year_match and int(year_match.group(1)) < self.min_year:
                    continue
                
                authors = [author.get("name", "") for author in getattr(entry, "authors", [])]
                title = getattr(entry, "title", "Untitled ML paper").replace("\n", " ")
                abstract = _strip_html(getattr(entry, "summary", ""))
                
                docs.append(
                    RawDocument(
                        title=title,
                        source_url=getattr(entry, "link", ""),
                        source_type="academic",
                        source_name=self.name,
                        text=f"{title}. {abstract}",
                        authors=[author for author in authors if author],
                        publication_date=published[:10],
                        metadata={
                            "domain": domain,
                            "categories": getattr(entry, "tags", []),
                            "arxiv_id": getattr(entry, "id", "").split("/")[-1] if hasattr(entry, "id") else "",
                        },
                    )
                )
                
                if len(docs) >= max_results:
                    break
            
            return FetchResult(source_name=self.name, documents=docs)
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))


class GitHubClient(HttpSourceClient):
    name = "GitHub"
    route_name = "github"
    source_type = "code"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, api_key=settings.github_token, enabled_without_key=True)
        self.max_repos = settings.max_github_repos

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        params = {
            "q": f"{query} in:name,description,readme stars:>10",
            "sort": "stars",
            "order": "desc",
            "per_page": min(max_results, self.max_repos, 100),
        }
        try:
            response = await self.http.get(
                "https://api.github.com/search/repositories", params=params, headers=headers
            )
            response.raise_for_status()
            docs = []
            for item in response.json().get("items", []):
                topics = item.get("topics") or []
                description = item.get("description") or ""
                docs.append(
                    RawDocument(
                        title=item.get("full_name", item.get("name", "GitHub repository")),
                        source_url=item.get("html_url"),
                        source_type="code",
                        source_name=self.name,
                        text=f"{item.get('full_name', '')}. {description}. Topics: {', '.join(topics)}",
                        authors=[item.get("owner", {}).get("login", "")],
                        publication_date=item.get("created_at", "")[:10],
                        metadata={
                            "stars": item.get("stargazers_count", 0),
                            "citation_count": item.get("stargazers_count", 0),
                            "domain": domain,
                            "language": item.get("language"),
                        },
                    )
                )
            return FetchResult(source_name=self.name, documents=docs)
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))


class HuggingFaceClient(HttpSourceClient):
    name = "Hugging Face"
    route_name = "huggingface"
    source_type = "industry"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, api_key=settings.huggingface_token, enabled_without_key=True)

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            response = await self.http.get(
                "https://huggingface.co/api/models",
                params={"search": query, "limit": min(max_results, 100), "sort": "downloads"},
                headers=headers,
            )
            response.raise_for_status()
            docs = []
            for item in response.json():
                model_id = item.get("modelId") or item.get("id") or "Hugging Face model"
                tags = item.get("tags") or []
                docs.append(
                    RawDocument(
                        title=model_id,
                        source_url=f"https://huggingface.co/{model_id}",
                        source_type="industry",
                        source_name=self.name,
                        text=f"{model_id}. Tags: {', '.join(tags)}. Downloads: {item.get('downloads', 0)}",
                        authors=[item.get("author", "")] if item.get("author") else [],
                        publication_date=(item.get("createdAt") or "")[:10],
                        metadata={
                            "downloads": item.get("downloads", 0),
                            "citation_count": item.get("likes", 0),
                            "domain": domain,
                        },
                    )
                )
            return FetchResult(source_name=self.name, documents=docs)
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))


class NewsApiClient(HttpSourceClient):
    """NewsAPI - News articles with automatic fallback to alternate key"""
    name = "NewsAPI"
    route_name = "newsapi"
    source_type = "news"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, api_key=settings.newsapi_key)
        self.alternate_key = settings.newsapi_key_alternate
        self.lookback_days = settings.news_lookback_days

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        # Try primary key first
        result = await self._fetch_with_key(self.api_key, query, max_results, domain)
        
        # If primary fails and we have an alternate, try it
        if result.error and self.alternate_key:
            result = await self._fetch_with_key(self.alternate_key, query, max_results, domain)
        
        return result
    
    async def _fetch_with_key(self, api_key: str | None, query: str, max_results: int, domain: str | None) -> FetchResult:
        if not api_key:
            return FetchResult(source_name=self.name, error="No API key configured")
        
        since = (datetime.now(UTC) - timedelta(days=self.lookback_days)).date().isoformat()
        params = {
            "q": query,
            "from": since,
            "language": "en",
            "sortBy": "relevancy",
            "pageSize": min(max_results, 100),
            "apiKey": api_key,
        }
        try:
            response = await self.http.get("https://newsapi.org/v2/everything", params=params)
            response.raise_for_status()
            data = response.json()
            articles = data.get("articles", [])
            
            # Check if response is null/empty
            if not articles:
                return FetchResult(source_name=self.name, error="No articles returned")
            
            docs = []
            for item in articles:
                docs.append(
                    RawDocument(
                        title=item.get("title") or "News article",
                        source_url=item.get("url"),
                        source_type="news",
                        source_name=self.name,
                        text=" ".join(
                            part
                            for part in (item.get("title"), item.get("description"), item.get("content"))
                            if part
                        ),
                        authors=[item.get("author", "")] if item.get("author") else [],
                        publication_date=(item.get("publishedAt") or "")[:10],
                        metadata={
                            "publisher": (item.get("source") or {}).get("name"),
                            "domain": domain,
                        },
                    )
                )
            return FetchResult(source_name=self.name, documents=docs)
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))


class GNewsClient(HttpSourceClient):
    name = "GNews"
    route_name = "gnews"
    source_type = "news"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, api_key=settings.gnews_api_key)
        self.alternate_key = settings.gnews_api_key_alternate

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        # Try primary key first
        result = await self._fetch_with_key(query, max_results, domain, self.api_key)
        
        # If primary fails and we have an alternate key, try it
        if result.error and self.alternate_key:
            result = await self._fetch_with_key(query, max_results, domain, self.alternate_key)
            if not result.error:
                result.error = None  # Clear error since alternate worked
        
        return result
    
    async def _fetch_with_key(self, query: str, max_results: int, domain: str | None, api_key: str | None) -> FetchResult:
        """Internal method to fetch with a specific API key"""
        params = {"q": query, "lang": "en", "max": min(max_results, 100), "apikey": api_key}
        try:
            response = await self.http.get("https://gnews.io/api/v4/search", params=params)
            response.raise_for_status()
            docs = []
            for item in response.json().get("articles", []):
                docs.append(
                    RawDocument(
                        title=item.get("title") or "GNews article",
                        source_url=item.get("url"),
                        source_type="news",
                        source_name=self.name,
                        text=" ".join(
                            part
                            for part in (item.get("title"), item.get("description"), item.get("content"))
                            if part
                        ),
                        publication_date=(item.get("publishedAt") or "")[:10],
                        metadata={"publisher": (item.get("source") or {}).get("name"), "domain": domain},
                    )
                )
            return FetchResult(source_name=self.name, documents=docs)
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))


class GuardianClient(HttpSourceClient):
    name = "The Guardian"
    route_name = "guardian"
    source_type = "news"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, api_key=settings.guardian_api_key)

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        params = {
            "q": query,
            "page-size": min(max_results, 50),
            "show-fields": "trailText,bodyText",
            "api-key": self.api_key,
        }
        try:
            response = await self.http.get("https://content.guardianapis.com/search", params=params)
            response.raise_for_status()
            docs = []
            for item in response.json().get("response", {}).get("results", []):
                fields = item.get("fields") or {}
                docs.append(
                    RawDocument(
                        title=item.get("webTitle") or "Guardian article",
                        source_url=item.get("webUrl"),
                        source_type="news",
                        source_name=self.name,
                        text=" ".join(
                            part
                            for part in (item.get("webTitle"), fields.get("trailText"), fields.get("bodyText"))
                            if part
                        ),
                        publication_date=(item.get("webPublicationDate") or "")[:10],
                        metadata={"section": item.get("sectionName"), "domain": domain},
                    )
                )
            return FetchResult(source_name=self.name, documents=docs)
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))


class NyTimesClient(HttpSourceClient):
    name = "New York Times"
    route_name = "nytimes"
    source_type = "news"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, api_key=settings.nytimes_api_key)

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        params = {"q": query, "api-key": self.api_key}
        try:
            response = await self.http.get(
                "https://api.nytimes.com/svc/search/v2/articlesearch.json", params=params
            )
            response.raise_for_status()
            docs = []
            for item in response.json().get("response", {}).get("docs", [])[:max_results]:
                headline = item.get("headline") or {}
                title = headline.get("main") or "NYTimes article"
                docs.append(
                    RawDocument(
                        title=title,
                        source_url=item.get("web_url"),
                        source_type="news",
                        source_name=self.name,
                        text=" ".join(
                            part
                            for part in (title, item.get("abstract"), item.get("lead_paragraph"), item.get("snippet"))
                            if part
                        ),
                        authors=[(item.get("byline") or {}).get("original", "")],
                        publication_date=(item.get("pub_date") or "")[:10],
                        metadata={"section": item.get("section_name"), "domain": domain},
                    )
                )
            return FetchResult(source_name=self.name, documents=docs)
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))


class SerperClient(HttpSourceClient):
    """Serper - Primary Google Search API with SerpAPI fallback"""
    name = "Serper"
    route_name = "serper"
    source_type = "web"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, api_key=settings.serper_api_key)
        self.serpapi_key = settings.serpapi_api_key  # Fallback for specialized searches

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        # Try Serper first (primary)
        result = await self._fetch_with_serper(query, max_results, domain)
        
        # If Serper fails and we have SerpAPI key, try it as fallback
        if result.error and self.serpapi_key:
            result = await self._fetch_with_serpapi(query, max_results, domain)
            if not result.error:
                result.error = None  # Clear error since fallback worked
        
        return result
    
    async def _fetch_with_serper(self, query: str, max_results: int, domain: str | None) -> FetchResult:
        """Primary: Serper.dev Google Search"""
        try:
            response = await self.http.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": self.api_key or "", "Content-Type": "application/json"},
                json={"q": query, "num": min(max_results, 20)},
            )
            response.raise_for_status()
            docs = []
            for item in response.json().get("organic", []):
                docs.append(
                    RawDocument(
                        title=item.get("title") or "Search result",
                        source_url=item.get("link"),
                        source_type="web",
                        source_name=self.name,
                        text=f"{item.get('title', '')}. {item.get('snippet', '')}",
                        publication_date=item.get("date"),
                        metadata={"domain": domain, "position": item.get("position"), "provider": "serper"},
                    )
                )
            return FetchResult(source_name=self.name, documents=docs)
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))
    
    async def _fetch_with_serpapi(self, query: str, max_results: int, domain: str | None) -> FetchResult:
        """Fallback: SerpAPI for specialized searches"""
        try:
            response = await self.http.get(
                "https://serpapi.com/search",
                params={
                    "engine": "google",
                    "q": query,
                    "api_key": self.serpapi_key,
                    "num": min(max_results, 20),
                },
            )
            response.raise_for_status()
            data = response.json()
            docs = []
            for item in data.get("organic_results", []):
                docs.append(
                    RawDocument(
                        title=item.get("title") or "Search result",
                        source_url=item.get("link"),
                        source_type="web",
                        source_name=self.name,
                        text=f"{item.get('title', '')}. {item.get('snippet', '')}",
                        publication_date=item.get("date"),
                        metadata={"domain": domain, "position": item.get("position"), "provider": "serpapi_fallback"},
                    )
                )
            return FetchResult(source_name=self.name, documents=docs)
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))


class ExaClient(HttpSourceClient):
    name = "Exa"
    route_name = "exa"
    source_type = "web"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, api_key=settings.exa_api_key)

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        try:
            response = await self.http.post(
                "https://api.exa.ai/search",
                headers={"x-api-key": self.api_key or "", "Content-Type": "application/json"},
                json={"query": query, "numResults": min(max_results, 25), "type": "neural"},
            )
            response.raise_for_status()
            docs = []
            for item in response.json().get("results", []):
                docs.append(
                    RawDocument(
                        title=item.get("title") or "Exa result",
                        source_url=item.get("url"),
                        source_type="web",
                        source_name=self.name,
                        text=first_text(item.get("text"), item.get("summary"), item.get("title")),
                        publication_date=item.get("publishedDate"),
                        metadata={"domain": domain, "score": item.get("score")},
                    )
                )
            return FetchResult(source_name=self.name, documents=docs)
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))


class TavilyClient(HttpSourceClient):
    name = "Tavily"
    route_name = "tavily"
    source_type = "web"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, api_key=settings.tavily_api_key)

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        try:
            response = await self.http.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self.api_key,
                    "query": query,
                    "max_results": min(max_results, 20),
                    "search_depth": "advanced",
                },
            )
            response.raise_for_status()
            docs = []
            for item in response.json().get("results", []):
                docs.append(
                    RawDocument(
                        title=item.get("title") or "Tavily result",
                        source_url=item.get("url"),
                        source_type="web",
                        source_name=self.name,
                        text=first_text(item.get("content"), item.get("raw_content"), item.get("title")),
                        metadata={"domain": domain, "score": item.get("score")},
                    )
                )
            return FetchResult(source_name=self.name, documents=docs)
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))


# Note: FirecrawlClient is currently not functional because Firecrawl v1 API doesn't have a search endpoint.
# Firecrawl is designed for scraping specific URLs, not for general search queries.
# The working scrape functionality is available via DocumentParserService._firecrawl_scrape()
# which correctly uses the v1/scrape endpoint for enriching individual documents.
class FirecrawlClient(HttpSourceClient):
    name = "Firecrawl"
    route_name = "firecrawl"
    source_type = "web"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, api_key=settings.firecrawl_api_key)
        self.alternate_key = settings.firecrawl_api_key_alternate

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        # Try primary key first
        result = await self._fetch_with_key(query, max_results, domain, self.api_key)
        
        # If primary fails and we have an alternate key, try it
        if result.error and self.alternate_key:
            result = await self._fetch_with_key(query, max_results, domain, self.alternate_key)
            if not result.error:
                result.error = None  # Clear error since alternate worked
        
        return result
    
    async def _fetch_with_key(self, query: str, max_results: int, domain: str | None, api_key: str | None) -> FetchResult:
        """Internal method to fetch with a specific API key"""
        try:
            response = await self.http.post(
                "https://api.firecrawl.dev/v1/search",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"query": query, "limit": min(max_results, 20)},
            )
            response.raise_for_status()
            payload = response.json()
            results = payload.get("data") or payload.get("results") or []
            docs = [
                RawDocument(
                    title=item.get("title") or "Firecrawl result",
                    source_url=item.get("url"),
                    source_type="web",
                    source_name=self.name,
                    text=first_text(item.get("markdown"), item.get("description"), item.get("title")),
                    metadata={"domain": domain},
                )
                for item in results
            ]
            return FetchResult(source_name=self.name, documents=docs)
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))


class ApifyWebScraperClient(HttpSourceClient):
    name = "Apify Web Scraper"
    route_name = "apify"
    source_type = "web"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, api_key=settings.apify_api_token)
        self.settings = settings
        self.timeout = settings.apify_scraper_timeout_secs
        self.max_pages = settings.apify_max_pages_per_scrape
        self.enable_js = settings.apify_enable_javascript

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        try:
            start_urls = await self._build_start_urls(query, domain, max_results)
            if not start_urls:
                return FetchResult(source_name=self.name, error="No seed URLs available for Apify scrape.")
            items = await self._run_scrape(start_urls, max_results)
            docs = []
            for item in items[:max_results]:
                docs.append(
                    RawDocument(
                        title=item.get("title") or "Scraped content",
                        source_url=item.get("url"),
                        source_type="web",
                        source_name=self.name,
                        text=first_text(item.get("text"), ""),
                        metadata={
                            "domain": domain,
                            "scraped_at": item.get("crawledAt"),
                        },
                    )
                )
            return FetchResult(source_name=self.name, documents=docs)
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))

    async def _build_start_urls(
        self, query: str, domain: str | None, max_results: int
    ) -> list[dict[str, str]]:
        if query.startswith("http://") or query.startswith("https://"):
            return [{"url": query}]
        if self.settings.serper_api_key:
            try:
                response = await self.http.post(
                    "https://google.serper.dev/search",
                    headers={
                        "X-API-KEY": self.settings.serper_api_key,
                        "Content-Type": "application/json",
                    },
                    json={"q": query, "num": min(max_results, self.max_pages, 10)},
                )
                response.raise_for_status()
                organic = response.json().get("organic", [])
                urls = [{"url": item.get("link")} for item in organic if item.get("link")]
                if urls:
                    return urls
            except Exception:
                pass
        search_urls = [{"url": f"https://www.google.com/search?q={query}"}]
        if domain and domain.lower() in {"partner_ecosystem", "competitive_intelligence", "market_research"}:
            search_urls.extend(
                [
                    {"url": f"https://www.gartner.com/en/search?keywords={query}"},
                    {"url": f"https://www.forrester.com/search?q={query}"},
                ]
            )
        return search_urls

    async def _run_scrape(self, start_urls: list[dict[str, str]], max_results: int) -> list[dict[str, Any]]:
        # Use configured timeout (up to 600 seconds / 10 minutes for complex scraping)
        apify_timeout = min(self.timeout, 600)
        http_timeout = min(float(self.timeout) + 30.0, 630.0)
        
        response = await self.http.post(
            "https://api.apify.com/v2/acts/apify~website-content-crawler/run-sync-get-dataset-items",
            params={"token": self.api_key, "timeout": apify_timeout},
            json={
                "startUrls": start_urls[: self.max_pages],
                "maxCrawlPages": min(max_results, self.max_pages),
                "crawlerType": "playwright:adaptive",
                "renderJavaScript": self.enable_js,
                "maxResults": min(max_results, self.max_pages),
                "saveMarkdown": True,
                "removeCookiesWarnings": True,
            },
            timeout=http_timeout,
        )
        
        # Apify returns 201 Created on success, not 200
        if response.status_code not in [200, 201]:
            response.raise_for_status()
        
        items = response.json()
        return items if isinstance(items, list) else []


class ApifyGoogleSearchScraperClient(HttpSourceClient):
    """
    Enhanced Google Search using Apify's infrastructure.
    Falls back to direct Serper API if Apify unavailable.
    """
    name = "Apify Google Search"
    route_name = "apify_google"
    source_type = "web"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, api_key=settings.apify_api_token)
        self.serper_key = settings.serper_api_key

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        """Fetch Google search results using available methods."""
        try:
            # Use Serper as reliable alternative
            if self.serper_key:
                return await self._fetch_via_serper(query, max_results, domain)
            else:
                return FetchResult(
                    source_name=self.name,
                    error="No search API configured (Serper recommended)"
                )
                
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))
    
    async def _fetch_via_serper(self, query: str, max_results: int, domain: str | None) -> FetchResult:
        """Use Serper API for Google search."""
        response = await self.http.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": self.serper_key or "", "Content-Type": "application/json"},
            json={"q": query, "num": min(max_results, 20)},
        )
        response.raise_for_status()
        
        docs = []
        for item in response.json().get("organic", []):
            docs.append(
                RawDocument(
                    title=item.get("title") or "Search result",
                    source_url=item.get("link"),
                    source_type="web",
                    source_name=self.name,
                    text=f"{item.get('title', '')}. {item.get('snippet', '')}",
                    publication_date=item.get("date"),
                    metadata={"domain": domain, "position": item.get("position")},
                )
            )
        
        return FetchResult(source_name=self.name, documents=docs)


class ApifyLinkedInScraperClient(HttpSourceClient):
    """
    LinkedIn company data scraper.
    Note: LinkedIn scraping requires special Apify actors and may have restrictions.
    This is a placeholder for future implementation.
    """
    name = "Apify LinkedIn"
    route_name = "apify_linkedin"
    source_type = "business"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, api_key=settings.apify_api_token)

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        """
        LinkedIn scraping is complex and requires specific setup.
        This is a placeholder for custom implementation.
        """
        return FetchResult(
            source_name=self.name,
            error="LinkedIn scraping requires custom Apify actor configuration. "
                  "Please set up a LinkedIn scraper actor in your Apify account and update this client."
        )


class ApifyRedditScraperClient(HttpSourceClient):
    """
    Reddit scraper using Google Search + Reddit domain filtering.
    Free alternative that doesn't require renting specialized actors.
    """
    name = "Apify Reddit"
    route_name = "apify_reddit"
    source_type = "social"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, api_key=settings.apify_api_token)
        self.timeout = settings.apify_scraper_timeout_secs
        self.serper_key = settings.serper_api_key

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        """Fetch Reddit posts using Google search with site:reddit.com filter."""
        try:
            # Fallback to Serper API for Reddit search
            if not self.serper_key:
                return FetchResult(
                    source_name=self.name,
                    error="Reddit search requires Serper API key"
                )
            
            reddit_query = f"site:reddit.com {query}"
            response = await self.http.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": self.serper_key, "Content-Type": "application/json"},
                json={"q": reddit_query, "num": min(max_results, 20)},
            )
            response.raise_for_status()
            
            docs = []
            for item in response.json().get("organic", []):
                # Extract subreddit from URL
                url = item.get("link", "")
                subreddit = "unknown"
                if "/r/" in url:
                    subreddit = url.split("/r/")[1].split("/")[0]
                
                docs.append(
                    RawDocument(
                        title=item.get("title") or "Reddit post",
                        source_url=url,
                        source_type="social",
                        source_name=self.name,
                        text=f"{item.get('title', '')}. {item.get('snippet', '')}",
                        publication_date=item.get("date"),
                        metadata={
                            "domain": domain,
                            "subreddit": subreddit,
                            "position": item.get("position"),
                            "engagement": {"search_position": item.get("position")},
                        },
                    )
                )
            
            return FetchResult(source_name=self.name, documents=docs)
            
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))


# Removed ApifyYouTubeScraperClient and ApifyTwitterScraperClient
# YouTube scraper was using Serper API incorrectly
# Twitter scraper was using deprecated apidojo~tweet-scraper actor
# For social media scraping, use alternative Apify actors or RSS feeds


class ApifyNewsScraperClient(HttpSourceClient):
    """
    News scraper using SerpAPI Google News endpoint.
    Aggregates news from multiple sources.
    """
    name = "Apify News"
    route_name = "apify_news"
    source_type = "news"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, api_key=settings.apify_api_token)
        self.serpapi_key = settings.serpapi_api_key

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        """Fetch news articles using SerpAPI."""
        try:
            if not self.serpapi_key:
                return FetchResult(
                    source_name=self.name,
                    error="News search requires SerpAPI key"
                )
            
            response = await self.http.get(
                "https://serpapi.com/search",
                params={
                    "engine": "google_news",
                    "q": query,
                    "api_key": self.serpapi_key,
                    "num": min(max_results, 20),
                },
            )
            response.raise_for_status()
            data = response.json()
            
            docs = []
            for item in data.get("news_results", [])[:max_results]:
                source_info = item.get("source", {})
                docs.append(
                    RawDocument(
                        title=item.get("title") or "News article",
                        source_url=item.get("link", ""),
                        source_type="news",
                        source_name=self.name,
                        text=f"{item.get('title', '')}. {item.get('snippet', '')}",
                        publication_date=item.get("date"),
                        metadata={
                            "domain": domain,
                            "publisher": source_info.get("name") if isinstance(source_info, dict) else source_info,
                            "position": item.get("position"),
                        },
                    )
                )
            
            return FetchResult(source_name=self.name, documents=docs)
            
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))


class GoogleNewsRSSClient(HttpSourceClient):
    """
    Free Google News RSS client using google-news-api library.
    Provides direct access to Google News without API costs.
    Supports topic-based feeds and time-based filtering.
    """
    name = "Google News RSS"
    route_name = "google_news_rss"
    source_type = "news"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        # Enabled without API key - uses free Google News RSS
        super().__init__(http, enabled_without_key=True)

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        try:
            # Import here to avoid issues if package isn't installed yet
            from google_news_api import GoogleNewsClient as GNAPIClient
            
            # Create sync client (library handles both sync/async)
            with GNAPIClient(language="en", country="US") as client:
                # Search with 7-day window for fresh results
                articles = client.search(query, when="7d", max_results=min(max_results, 50))
                
                docs = []
                for article in articles:
                    # Decode Google News URLs to original publisher URLs
                    original_url = article.get("link", "")
                    try:
                        original_url = client.decode_url(original_url)
                    except Exception:
                        pass  # Use Google News URL if decoding fails
                    
                    docs.append(
                        RawDocument(
                            title=article.get("title") or "Google News article",
                            source_url=original_url,
                            source_type="news",
                            source_name=self.name,
                            text=f"{article.get('title', '')}. {article.get('summary', '')}",
                            publication_date=article.get("published"),
                            metadata={
                                "domain": domain,
                                "publisher": article.get("source", ""),
                                "google_news_link": article.get("link", ""),
                            },
                        )
                    )
                
                return FetchResult(source_name=self.name, documents=docs)
                
        except ImportError:
            return FetchResult(
                source_name=self.name,
                error="google-news-api package not installed. Run: pip install google-news-api"
            )
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))


class SerpApiGoogleNewsClient(HttpSourceClient):
    """
    SerpAPI Google News scraper - comprehensive news search with structured data.
    Provides richer results than RSS including story clustering and related topics.
    """
    name = "SerpAPI News"
    route_name = "serpapi_news"
    source_type = "news"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, api_key=settings.serpapi_api_key)

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        try:
            # Use SerpAPI's Google News engine
            response = await self.http.get(
                "https://serpapi.com/search",
                params={
                    "engine": "google_news",
                    "q": query,
                    "api_key": self.api_key or "",
                    "num": min(max_results, 50),
                    "hl": "en",
                    "gl": "us",
                },
            )
            response.raise_for_status()
            data = response.json()
            
            docs = []
            for item in data.get("news_results", []):
                # Handle both single articles and story clusters
                if "stories" in item:
                    # This is a story cluster - get the highlight article
                    highlight = item.get("highlight", {})
                    if highlight:
                        docs.append(self._create_document(highlight, domain))
                else:
                    # Single article
                    docs.append(self._create_document(item, domain))
                
                # Stop when we reach max_results
                if len(docs) >= max_results:
                    break
            
            return FetchResult(source_name=self.name, documents=docs)
            
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))
    
    def _create_document(self, item: dict, domain: str | None) -> RawDocument:
        """Helper to create a RawDocument from SerpAPI news result."""
        source_info = item.get("source", {})
        return RawDocument(
            title=item.get("title") or "SerpAPI News article",
            source_url=item.get("link", ""),
            source_type="news",
            source_name=self.name,
            text=f"{item.get('title', '')}. {item.get('snippet', '')}",
            publication_date=item.get("date"),
            metadata={
                "domain": domain,
                "publisher": source_info.get("name", "") if isinstance(source_info, dict) else source_info,
                "thumbnail": item.get("thumbnail"),
                "position": item.get("position"),
            },
        )


class JinaAIClient(HttpSourceClient):
    """Jina AI Search & Reader - Search web + convert URLs to markdown (1M requests/month FREE)"""
    name = "Jina AI"
    route_name = "jina"
    source_type = "web"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, api_key=settings.jina_api_key, enabled_without_key=True)

    async def fetch(self, query: str, *, max_results: int = 1, domain: str | None = None) -> FetchResult:
        """Search with Jina for topics, or use Reader for a concrete URL."""
        try:
            # Prepare headers with API key if available
            headers = {
                "Accept": "application/json",
                "X-Return-Format": "markdown",
            }
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            if not query.startswith(("http://", "https://")):
                # Search mode
                response = await self.http.get(
                    "https://s.jina.ai/", 
                    params={"q": query},
                    headers=headers,
                )
                response.raise_for_status()
                payload = response.json()
                results = payload.get("data", payload if isinstance(payload, list) else [])
                docs = []
                for item in results[:max_results]:
                    source_url = item.get("url", "")
                    if not source_url:
                        continue
                    docs.append(RawDocument(
                        title=item.get("title") or "Jina search result", source_url=source_url,
                        source_type="web", source_name=self.name,
                        text=item.get("content") or item.get("description") or item.get("snippet") or "",
                        metadata={"domain": domain, "search_provider": "jina_ai"},
                    ))
                return FetchResult(source_name=self.name, documents=docs)
            
            # Reader mode for specific URL
            reader_headers = {"Accept": "text/markdown"}
            if self.api_key:
                reader_headers["Authorization"] = f"Bearer {self.api_key}"
            
            response = await self.http.get(
                f"https://r.jina.ai/{query}",
                headers=reader_headers,
            )
            response.raise_for_status()
            content = response.text
            
            # Extract title from first line or use URL
            lines = content.split('\n')
            title = lines[0].strip('#').strip() if lines else query
            
            doc = RawDocument(
                title=title,
                source_url=query,
                source_type="web",
                source_name=self.name,
                text=content,
                metadata={"domain": domain, "converted_by": "jina_ai"},
            )
            return FetchResult(source_name=self.name, documents=[doc])
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))


class HackerNewsClient(HttpSourceClient):
    """HackerNews API - Tech news and discussions (Unlimited FREE)"""
    name = "Hacker News"
    route_name = "hackernews"
    source_type = "news"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, enabled_without_key=True)

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        """Fetch top stories from Hacker News."""
        try:
            # Get top story IDs
            response = await self.http.get("https://hacker-news.firebaseio.com/v0/topstories.json")
            response.raise_for_status()
            story_ids = response.json()[: max(50, max_results * 10)]
            
            docs = []
            for story_id in story_ids:
                try:
                    story_response = await self.http.get(
                        f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
                    )
                    story_response.raise_for_status()
                    story = story_response.json()
                    
                    if story and story.get("type") == "story":
                        # Simple keyword filtering
                        title_text = story.get("title", "").lower()
                        query_terms = {term for term in query.lower().split() if len(term) > 2}
                        if not query_terms or query_terms & set(title_text.replace("-", " ").split()):
                            docs.append(
                                RawDocument(
                                    title=story.get("title") or "HN Story",
                                    source_url=story.get("url") or f"https://news.ycombinator.com/item?id={story_id}",
                                    source_type="news",
                                    source_name=self.name,
                                    text=f"{story.get('title', '')}. {story.get('text', '')}",
                                    metadata={
                                        "domain": domain,
                                        "score": story.get("score", 0),
                                        "comments": story.get("descendants", 0),
                                        "author": story.get("by", ""),
                                        "hn_id": story_id,
                                    },
                                )
                            )
                            if len(docs) >= max_results:
                                break
                except Exception:
                    continue  # Skip failed stories
                    
            return FetchResult(source_name=self.name, documents=docs)
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))


class StackExchangeClient(HttpSourceClient):
    """Public Stack Overflow discussions as a stable, keyless community signal."""
    name = "Stack Overflow Community"
    route_name = "stackexchange"
    source_type = "social"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, enabled_without_key=True)

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        try:
            response = await self.http.get(
                "https://api.stackexchange.com/2.3/search/advanced",
                params={
                    "site": "stackoverflow", "q": query, "order": "desc", "sort": "activity",
                    "pagesize": min(max_results, 30), "filter": "default",
                },
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("backoff"):
                return FetchResult(source_name=self.name, error=f"Rate limit backoff requested for {payload['backoff']} seconds")
            docs = []
            for item in payload.get("items", []):
                link = item.get("link")
                if not link:
                    continue
                title = unescape(item.get("title") or "Stack Overflow discussion")
                tags = item.get("tags") or []
                docs.append(RawDocument(
                    title=title, source_url=link, source_type="social", source_name=self.name,
                    text=f"{title}. Tags: {', '.join(tags)}",
                    publication_date=datetime.fromtimestamp(item.get("creation_date", 0), UTC).date().isoformat() if item.get("creation_date") else None,
                    metadata={
                        "domain": domain, "score": item.get("score", 0),
                        "view_count": item.get("view_count", 0), "answer_count": item.get("answer_count", 0),
                        "is_answered": item.get("is_answered", False), "tags": tags,
                        "engagement": {"score": item.get("score", 0), "views": item.get("view_count", 0), "answers": item.get("answer_count", 0)},
                    },
                ))
            return FetchResult(source_name=self.name, documents=docs)
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))


class DevToClient(HttpSourceClient):
    """Dev.to API - Developer blogs and tutorials (Unlimited FREE)"""
    name = "Dev.to"
    route_name = "devto"
    source_type = "blog"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, enabled_without_key=True)

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        """Fetch articles from Dev.to by tag or search."""
        try:
            # Try to use query as tag, or use popular tech tags
            params = {"per_page": min(max_results, 100)}
            
            # If query looks like a tag (single word), use tag endpoint
            if query and " " not in query.strip():
                params["tag"] = query.lower()
            
            response = await self.http.get("https://dev.to/api/articles", params=params)
            response.raise_for_status()
            articles = response.json()
            
            docs = []
            for article in articles[:max_results]:
                # Filter by query in title/description if not using tag
                if " " in query:
                    searchable = f"{article.get('title', '')} {article.get('description', '')}".lower()
                    if query.lower() not in searchable:
                        continue
                
                docs.append(
                    RawDocument(
                        title=article.get("title") or "Dev.to Article",
                        source_url=article.get("url", ""),
                        source_type="blog",
                        source_name=self.name,
                        text=f"{article.get('title', '')}. {article.get('description', '')}",
                        authors=[article.get("user", {}).get("name", "")],
                        publication_date=article.get("published_at", "")[:10] if article.get("published_at") else None,
                        metadata={
                            "domain": domain,
                            "tags": article.get("tag_list", []),
                            "reactions": article.get("public_reactions_count", 0),
                            "comments": article.get("comments_count", 0),
                        },
                    )
                )
            
            return FetchResult(source_name=self.name, documents=docs)
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))


class RSSFeedClient(HttpSourceClient):
    """RSS Feed Aggregator - Company blogs and news feeds (FREE)"""
    name = "RSS Feeds"
    route_name = "rss"
    source_type = "blog"

    # Curated list of high-quality tech/AI/ML RSS feeds
    FEED_URLS = [
        # Tech News
        "https://techcrunch.com/feed/",
        "https://www.theverge.com/rss/index.xml",
        "https://www.wired.com/feed/rss",
        "https://feeds.arstechnica.com/arstechnica/index",
        "https://venturebeat.com/feed/",
        # AI/ML Blogs
        "https://openai.com/blog/rss/",
        "https://blog.google/technology/ai/rss/",
        "https://ai.meta.com/blog/rss/",
        "https://www.microsoft.com/en-us/research/feed/",
        "https://huggingface.co/blog/feed.xml",
        # Developer Tools
        "https://github.blog/feed/",
        "https://vercel.com/blog/rss.xml",
        "https://www.netlify.com/blog/index.xml",
    ]

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, enabled_without_key=True)

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        """Fetch and aggregate articles from RSS feeds."""
        try:
            all_docs = []
            query_lower = query.lower()
            
            for feed_url in self.FEED_URLS:
                try:
                    response = await self.http.get(feed_url, timeout=10.0)
                    feed = feedparser.parse(response.text)
                    
                    for entry in feed.entries[:20]:  # Max 20 per feed
                        # Filter by query
                        searchable = f"{entry.get('title', '')} {entry.get('summary', '')}".lower()
                        if query and query_lower not in searchable:
                            continue
                        
                        pub_date = entry.get("published") or entry.get("updated")
                        if pub_date:
                            # Parse date
                            try:
                                from email.utils import parsedate_to_datetime
                                dt = parsedate_to_datetime(pub_date)
                                pub_date = dt.strftime("%Y-%m-%d")
                            except Exception:
                                pub_date = None
                        
                        all_docs.append(
                            RawDocument(
                                title=entry.get("title") or "RSS Article",
                                source_url=entry.get("link", ""),
                                source_type="blog",
                                source_name=self.name,
                                text=f"{entry.get('title', '')}. {_strip_html(entry.get('summary', ''))}",
                                publication_date=pub_date,
                                metadata={
                                    "domain": domain,
                                    "feed_source": feed.feed.get("title", feed_url),
                                    "author": entry.get("author", ""),
                                },
                            )
                        )
                        
                        if len(all_docs) >= max_results:
                            break
                    
                    if len(all_docs) >= max_results:
                        break
                        
                except Exception:
                    continue  # Skip failed feeds
            
            return FetchResult(source_name=self.name, documents=all_docs[:max_results])
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))


class TowardsDataScienceClient(HttpSourceClient):
    """Towards Data Science (Medium) - AI/ML/Data Science blog (~3 free articles/month, then paywalled)"""
    name = "Towards Data Science"
    route_name = "towardsdatascience"
    source_type = "blog"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, enabled_without_key=True)

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        """Fetch articles from Towards Data Science via Medium RSS."""
        try:
            # Towards Data Science RSS feed
            response = await self.http.get(
                "https://towardsdatascience.com/feed",
                timeout=15.0,
                follow_redirects=True
            )
            response.raise_for_status()
            feed = feedparser.parse(response.text)
            
            docs = []
            query_lower = query.lower() if query else ""
            
            for entry in feed.entries:
                # Loose filter - only skip if very specific query doesn't match
                if query and len(query.split()) > 2:
                    searchable = f"{entry.get('title', '')} {entry.get('summary', '')}".lower()
                    if query_lower not in searchable:
                        continue
                
                # Parse publication date
                pub_date = entry.get("published") or entry.get("updated")
                if pub_date:
                    try:
                        from email.utils import parsedate_to_datetime
                        dt = parsedate_to_datetime(pub_date)
                        pub_date = dt.strftime("%Y-%m-%d")
                    except Exception:
                        pub_date = None
                
                # Extract author from Medium format
                author = entry.get("author", "")
                
                docs.append(
                    RawDocument(
                        title=entry.get("title") or "TDS Article",
                        source_url=entry.get("link", ""),
                        source_type="blog",
                        source_name=self.name,
                        text=f"{entry.get('title', '')}. {_strip_html(entry.get('summary', ''))}",
                        authors=[author] if author else [],
                        publication_date=pub_date,
                        metadata={
                            "domain": domain,
                            "platform": "Medium",
                            "paywall": "3_free_per_month",
                            "categories": entry.get("tags", []),
                        },
                    )
                )
                
                if len(docs) >= max_results:
                    break
            
            return FetchResult(source_name=self.name, documents=docs)
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))


class KDnuggetsClient(HttpSourceClient):
    """KDnuggets - Data Science and ML blog (Fully FREE)"""
    name = "KDnuggets"
    route_name = "kdnuggets"
    source_type = "blog"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, enabled_without_key=True)

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        """Fetch articles from KDnuggets RSS feed."""
        try:
            # KDnuggets RSS feed
            response = await self.http.get(
                "https://www.kdnuggets.com/feed",
                timeout=15.0,
                follow_redirects=True
            )
            response.raise_for_status()
            feed = feedparser.parse(response.text)
            
            docs = []
            query_lower = query.lower() if query else ""
            
            for entry in feed.entries:
                # Loose filter - only skip if very specific query doesn't match
                if query and len(query.split()) > 2:
                    searchable = f"{entry.get('title', '')} {entry.get('summary', '')}".lower()
                    if query_lower not in searchable:
                        continue
                
                # Parse publication date
                pub_date = entry.get("published") or entry.get("updated")
                if pub_date:
                    try:
                        from email.utils import parsedate_to_datetime
                        dt = parsedate_to_datetime(pub_date)
                        pub_date = dt.strftime("%Y-%m-%d")
                    except Exception:
                        pub_date = None
                
                # Extract categories/tags
                categories = [tag.get("term", "") for tag in entry.get("tags", [])]
                
                docs.append(
                    RawDocument(
                        title=entry.get("title") or "KDnuggets Article",
                        source_url=entry.get("link", ""),
                        source_type="blog",
                        source_name=self.name,
                        text=f"{entry.get('title', '')}. {_strip_html(entry.get('summary', ''))}",
                        authors=[entry.get("author", "")] if entry.get("author") else [],
                        publication_date=pub_date,
                        metadata={
                            "domain": domain,
                            "categories": categories,
                            "paywall": "free",
                        },
                    )
                )
                
                if len(docs) >= max_results:
                    break
            
            return FetchResult(source_name=self.name, documents=docs)
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))


class AIWeeklyClient(HttpSourceClient):
    """Import AI - Weekly AI/ML newsletter digest (by Jack Clark)"""
    name = "Import AI"
    route_name = "importai"
    source_type = "blog"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, enabled_without_key=True)

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        """Fetch articles from Import AI newsletter archive."""
        try:
            # Import AI Newsletter RSS feed
            response = await self.http.get(
                "https://jack-clark.net/feed/",
                timeout=15.0,
                follow_redirects=True
            )
            response.raise_for_status()
            feed = feedparser.parse(response.text)
            
            docs = []
            query_lower = query.lower() if query else ""
            
            for entry in feed.entries:
                # Loose filter - only skip if very specific query doesn't match
                if query and len(query.split()) > 2:
                    searchable = f"{entry.get('title', '')} {entry.get('summary', '')}".lower()
                    if query_lower not in searchable:
                        continue
                
                # Parse publication date
                pub_date = entry.get("published") or entry.get("updated")
                if pub_date:
                    try:
                        from email.utils import parsedate_to_datetime
                        dt = parsedate_to_datetime(pub_date)
                        pub_date = dt.strftime("%Y-%m-%d")
                    except Exception:
                        pub_date = None
                
                docs.append(
                    RawDocument(
                        title=entry.get("title") or "AI Weekly Digest",
                        source_url=entry.get("link", ""),
                        source_type="blog",
                        source_name=self.name,
                        text=f"{entry.get('title', '')}. {_strip_html(entry.get('summary', ''))}",
                        publication_date=pub_date,
                        metadata={
                            "domain": domain,
                            "type": "newsletter_digest",
                            "paywall": "free",
                        },
                    )
                )
                
                if len(docs) >= max_results:
                    break
            
            return FetchResult(source_name=self.name, documents=docs)
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))


class GDELTClient(HttpSourceClient):
    """GDELT - Global news events and trends (Unlimited FREE)"""
    name = "GDELT"
    route_name = "gdelt"
    source_type = "news"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, enabled_without_key=True)

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        """Search GDELT for news articles."""
        try:
            params = {
                "query": query,
                "mode": "artlist",
                "maxrecords": min(max_results, 250),
                "format": "json",
            }
            
            response = await self.http.get(
                "https://api.gdeltproject.org/api/v2/doc/doc",
                params=params,
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            
            docs = []
            for article in data.get("articles", [])[:max_results]:
                docs.append(
                    RawDocument(
                        title=article.get("title") or "GDELT Article",
                        source_url=article.get("url", ""),
                        source_type="news",
                        source_name=self.name,
                        text=f"{article.get('title', '')}. {article.get('seendate', '')}",
                        publication_date=article.get("seendate", "")[:10] if article.get("seendate") else None,
                        metadata={
                            "domain": domain,
                            "source_country": article.get("sourcecountry", ""),
                            "language": article.get("language", ""),
                            "domain_name": article.get("domain", ""),
                        },
                    )
                )
            
            return FetchResult(source_name=self.name, documents=docs)
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))


class NpmClient(HttpSourceClient):
    """npm Registry API - JavaScript packages (Unlimited FREE)"""
    name = "npm"
    route_name = "npm"
    source_type = "code"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, enabled_without_key=True)

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        """Search npm packages."""
        try:
            # Search npm registry
            params = {
                "text": query,
                "size": min(max_results, 250),
            }
            
            response = await self.http.get(
                "https://registry.npmjs.org/-/v1/search",
                params=params
            )
            response.raise_for_status()
            data = response.json()
            
            docs = []
            for item in data.get("objects", [])[:max_results]:
                package = item.get("package", {})
                docs.append(
                    RawDocument(
                        title=package.get("name") or "npm package",
                        source_url=package.get("links", {}).get("npm", ""),
                        source_type="code",
                        source_name=self.name,
                        text=f"{package.get('name', '')}. {package.get('description', '')}",
                        authors=[package.get("publisher", {}).get("username", "")],
                        metadata={
                            "domain": domain,
                            "version": package.get("version", ""),
                            "keywords": package.get("keywords", []),
                            "repository": package.get("links", {}).get("repository", ""),
                            "homepage": package.get("links", {}).get("homepage", ""),
                        },
                    )
                )
            
            return FetchResult(source_name=self.name, documents=docs)
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))


class PyPIClient(HttpSourceClient):
    """PyPI API - Python packages (Unlimited FREE)"""
    name = "PyPI"
    route_name = "pypi"
    source_type = "code"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, enabled_without_key=True)

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        """Search PyPI packages."""
        try:
            # PyPI removed its general-purpose search API. For broad Daily
            # Intelligence topics, query a curated set of relevant package
            # metadata endpoints and preserve each official PyPI URL.
            broad_terms = {"ai", "openai", "artificial intelligence", "machine learning"}
            if query.strip().lower() in broad_terms and max_results > 1:
                package_names = ["openai", "langchain", "llama-index", "transformers", "crewai", "autogen-agentchat", "litellm", "chromadb"]
                docs = []
                for package_name in package_names[:max_results]:
                    pkg_response = await self.http.get(f"https://pypi.org/pypi/{package_name}/json")
                    if pkg_response.status_code != 200:
                        continue
                    info = pkg_response.json().get("info", {})
                    docs.append(RawDocument(
                        title=info.get("name") or package_name,
                        source_url=info.get("package_url") or f"https://pypi.org/project/{package_name}/",
                        source_type="code", source_name=self.name,
                        text=f"{info.get('name', '')}. {info.get('summary', '')}",
                        authors=[info.get("author", "")],
                        metadata={"domain": domain, "version": info.get("version", ""), "keywords": info.get("keywords", ""), "home_page": info.get("home_page", ""), "project_url": info.get("project_url", "")},
                    ))
                return FetchResult(source_name=self.name, documents=docs)
            # PyPI XML-RPC search (simple method)
            # Note: PyPI doesn't have a great search API, so we use a workaround
            # Search via the HTML endpoint and parse
            response = await self.http.get(
                f"https://pypi.org/search/?q={query}",
                headers={"Accept": "application/json"}
            )
            
            # Try JSON API for specific package if query is a single word
            if " " not in query.strip():
                try:
                    pkg_response = await self.http.get(f"https://pypi.org/pypi/{query}/json")
                    if pkg_response.status_code == 200:
                        data = pkg_response.json()
                        info = data.get("info", {})
                        doc = RawDocument(
                            title=info.get("name") or query,
                            source_url=info.get("package_url") or f"https://pypi.org/project/{query}/",
                            source_type="code",
                            source_name=self.name,
                            text=f"{info.get('name', '')}. {info.get('summary', '')}",
                            authors=[info.get("author", "")],
                            metadata={
                                "domain": domain,
                                "version": info.get("version", ""),
                                "keywords": info.get("keywords", ""),
                                "home_page": info.get("home_page", ""),
                                "project_url": info.get("project_url", ""),
                            },
                        )
                        return FetchResult(source_name=self.name, documents=[doc])
                except Exception:
                    pass
            
            # Fallback: return empty result with note
            # PyPI's search is limited without XML-RPC
            return FetchResult(
                source_name=self.name,
                documents=[],
                error="PyPI search requires package name. Try specific package names like 'fastapi' or 'numpy'"
            )
            
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))


class ProductHuntClient(HttpSourceClient):
    """ProductHunt API - Daily tech product launches (FREE)"""
    name = "Product Hunt"
    route_name = "producthunt"
    source_type = "news"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, api_key=settings.producthunt_token)

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        """Fetch products from Product Hunt using GraphQL API."""
        try:
            # ProductHunt uses GraphQL
            graphql_query = """
            query($first: Int!) {
              posts(first: $first, order: VOTES) {
                edges {
                  node {
                    id
                    name
                    tagline
                    description
                    url
                    votesCount
                    commentsCount
                    createdAt
                    featuredAt
                    website
                    topics {
                      edges {
                        node {
                          name
                        }
                      }
                    }
                  }
                }
              }
            }
            """
            
            response = await self.http.post(
                "https://api.producthunt.com/v2/api/graphql",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "query": graphql_query,
                    "variables": {"first": min(max_results, 20)}
                }
            )
            response.raise_for_status()
            data = response.json()
            
            docs = []
            edges = data.get("data", {}).get("posts", {}).get("edges", [])
            
            for edge in edges:
                node = edge.get("node", {})
                
                # Filter by query if provided
                if query:
                    searchable = f"{node.get('name', '')} {node.get('tagline', '')} {node.get('description', '')}".lower()
                    if query.lower() not in searchable:
                        continue
                
                topics = [t.get("node", {}).get("name", "") for t in node.get("topics", {}).get("edges", [])]
                
                docs.append(
                    RawDocument(
                        title=node.get("name") or "Product Hunt Product",
                        source_url=node.get("url") or node.get("website", ""),
                        source_type="news",
                        source_name=self.name,
                        text=f"{node.get('name', '')}. {node.get('tagline', '')}. {node.get('description', '')}",
                        publication_date=node.get("createdAt", "")[:10] if node.get("createdAt") else None,
                        metadata={
                            "domain": domain,
                            "votes": node.get("votesCount", 0),
                            "comments": node.get("commentsCount", 0),
                            "topics": topics,
                            "website": node.get("website", ""),
                        },
                    )
                )
            
            return FetchResult(source_name=self.name, documents=docs[:max_results])
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))


class COREClient(HttpSourceClient):
    """CORE API - Open access research papers (10k/day FREE)"""
    name = "CORE"
    route_name = "core"
    source_type = "academic"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, api_key=settings.core_api_key)
        self.min_year = settings.min_publication_year

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        """Search CORE for open access papers."""
        try:
            response = await self.http.post(
                "https://api.core.ac.uk/v3/search/works",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "q": query,
                    "limit": min(max_results, 100),
                }
            )
            response.raise_for_status()
            data = response.json()
            
            docs = []
            results = data.get("results", [])
            
            if not results:
                return FetchResult(source_name=self.name, documents=[])
            
            for item in results:
                # Extract authors
                authors = []
                for author in item.get("authors", []):
                    if isinstance(author, dict):
                        authors.append(author.get("name", ""))
                    elif isinstance(author, str):
                        authors.append(author)
                
                # Get URL - CORE has multiple possible URL fields
                source_url = (
                    item.get("downloadUrl") or 
                    item.get("doi") or
                    (item.get("sourceFulltextUrls", [""])[0] if item.get("sourceFulltextUrls") else "") or
                    ""
                )
                
                docs.append(
                    RawDocument(
                        title=item.get("title") or "CORE Paper",
                        source_url=source_url,
                        source_type="academic",
                        source_name=self.name,
                        text=f"{item.get('title', '')}. {item.get('abstract', '')}",
                        authors=[a for a in authors if a],
                        publication_date=str(item.get("yearPublished")) if item.get("yearPublished") else None,
                        metadata={
                            "domain": domain,
                            "year": item.get("yearPublished"),
                            "doi": item.get("doi", ""),
                            "publisher": item.get("publisher", ""),
                            "citations": item.get("citationCount", 0),
                        },
                    )
                )
            
            return FetchResult(source_name=self.name, documents=docs)
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))


class YouComClient(HttpSourceClient):
    """You.com API - AI-powered search (FREE tier)"""
    name = "You.com"
    route_name = "you"
    source_type = "web"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, api_key=settings.you_api_key)

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        """Search using You.com API v1."""
        try:
            # Correct You.com API v1 endpoint and parameters
            headers = {
                "X-API-Key": self.api_key,
                "Accept": "application/json",
            }
            
            params = {
                "query": query,
                "count": min(max_results, 20),
                "offset": 0,
                "language": "EN",
                "safesearch": "moderate",
            }
            
            response = await self.http.get(
                "https://ydc-index.io/v1/search",
                headers=headers,
                params=params,
                timeout=30.0
            )
            
            # Check for authentication errors
            if response.status_code == 403:
                return FetchResult(
                    source_name=self.name,
                    error="Authentication failed. You.com API key may be invalid or expired."
                )
            
            response.raise_for_status()
            data = response.json()
            
            docs = []
            # You.com v1 returns results in nested structure: response["results"]["web"]
            web_results = data.get("results", {}).get("web", [])
            
            for hit in web_results[:max_results]:
                snippets = hit.get("snippets", [])
                snippet_text = " ".join(snippets) if snippets else ""
                
                docs.append(
                    RawDocument(
                        title=hit.get("title") or "You.com Result",
                        source_url=hit.get("url", ""),
                        source_type="web",
                        source_name=self.name,
                        text=f"{hit.get('title', '')}. {hit.get('description', '')} {snippet_text}",
                        metadata={
                            "domain": domain,
                            "thumbnail": hit.get("thumbnail_url", ""),
                            "favicon": hit.get("favicon_url", ""),
                        },
                    )
                )
            
            return FetchResult(source_name=self.name, documents=docs)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 403:
                return FetchResult(
                    source_name=self.name,
                    error="You.com API authentication failed. Verify API key."
                )
            return FetchResult(source_name=self.name, error=f"HTTP {exc.response.status_code}: {str(exc)}")
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))


def build_clients(http: httpx.AsyncClient, settings: Settings):
    from research_intel.ingestion.apify_actors import build_apify_actor_clients
    return [
        # Academic sources
        ArxivClient(http, settings),
        SemanticScholarClient(http, settings),
        OpenAlexClient(http, settings),
        PapersWithCodeClient(http, settings),
        COREClient(http, settings),  # NEW - FREE 10k/day (240M papers)
        
        # Industry sources
        HuggingFaceClient(http, settings),
        GitHubClient(http, settings),
        
        # Code package registries (NEW - FREE)
        NpmClient(http, settings),
        PyPIClient(http, settings),
        
        # News sources
        NewsApiClient(http, settings),
        GNewsClient(http, settings),
        GoogleNewsRSSClient(http, settings),
        SerpApiGoogleNewsClient(http, settings),
        GuardianClient(http, settings),
        NyTimesClient(http, settings),
        HackerNewsClient(http, settings),  # NEW - FREE unlimited
        StackExchangeClient(http, settings),  # Keyless community/social fallback
        GDELTClient(http, settings),  # NEW - FREE unlimited
        ProductHuntClient(http, settings),  # NEW - FREE (product launches)
        
        # Blog sources (NEW - FREE)
        DevToClient(http, settings),
        RSSFeedClient(http, settings),
        TowardsDataScienceClient(http, settings),  # NEW - Medium/TDS (3 free/month)
        KDnuggetsClient(http, settings),  # NEW - FREE blog
        AIWeeklyClient(http, settings),  # NEW - FREE newsletter
        
        # Web search & scraping
        SerperClient(http, settings),
        ExaClient(http, settings),
        TavilyClient(http, settings),
        JinaAIClient(http, settings),  # NEW - FREE 1M/month
        YouComClient(http, settings),  # NEW - FREE tier
        # Note: FirecrawlClient removed - Firecrawl is for scraping specific URLs, not search
        # It's still used in document_parser for enriching individual documents
        
        # Apify scrapers (Premium subscription - multiple sources)
        ApifyWebScraperClient(http, settings),
        ApifyGoogleSearchScraperClient(http, settings),
        ApifyRedditScraperClient(http, settings),
        ApifyNewsScraperClient(http, settings),
        *build_apify_actor_clients(http, settings),
    ]
