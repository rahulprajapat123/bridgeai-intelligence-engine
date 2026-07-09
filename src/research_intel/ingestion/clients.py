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
    Uses class-level lock to prevent concurrent requests.
    """
    name = "Semantic Scholar"
    route_name = "semantic_scholar"
    source_type = "academic"
    _last_request_time: float = 0.0
    _lock = asyncio.Lock()

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, api_key=settings.semantic_scholar_api_key, enabled_without_key=True)

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        headers = {"x-api-key": self.api_key} if self.api_key else {}
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
                
                # If less than 1.1 seconds have passed, wait
                if time_since_last < 1.1:
                    await asyncio.sleep(1.1 - time_since_last)
                
                response = await self.http.get(
                    "https://api.semanticscholar.org/graph/v1/paper/search",
                    params=params,
                    headers=headers,
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
    Papers with Code client using direct HTTP API.
    No API key required - uses public REST API.
    """
    name = "Papers with Code"
    route_name = "paperswithcode"
    source_type = "academic"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, enabled_without_key=True)
        self.min_year = settings.min_publication_year

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        """
        Fetch papers from Papers with Code using their public REST API.
        API Docs: https://paperswithcode.com/api/v1/docs/
        """
        params = {
            "q": query,
            "items_per_page": min(max_results, 50),
        }
        try:
            response = await self.http.get(
                "https://paperswithcode.com/api/v1/papers/",
                params=params,
                headers={"User-Agent": "Research-Intelligence-Platform/0.1.0"},
            )
            response.raise_for_status()
            data = response.json()
            
            docs: list[RawDocument] = []
            for paper in data.get("results", []):
                # Extract paper details
                title = paper.get("title") or "Untitled Papers with Code paper"
                abstract = paper.get("abstract") or ""
                arxiv_id = paper.get("arxiv_id") or ""
                
                # Build URLs
                paper_id = paper.get("id") or ""
                pwc_url = f"https://paperswithcode.com/paper/{paper_id}" if paper_id else ""
                arxiv_url = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else ""
                url = arxiv_url or pwc_url
                
                # Extract authors
                authors = paper.get("authors", [])
                if isinstance(authors, list):
                    authors = [str(author) for author in authors if author]
                else:
                    authors = []
                
                # Extract publication date/year
                pub_date = paper.get("published") or ""
                if not pub_date and paper.get("year"):
                    pub_date = str(paper.get("year"))
                
                # Check year filter
                if pub_date:
                    year_match = re.search(r'(20\d{2}|19\d{2})', pub_date)
                    if year_match and int(year_match.group(1)) < self.min_year:
                        continue
                
                # Build metadata
                metadata = {"domain": domain}
                
                # Add repository info if available
                if paper.get("url_official"):
                    metadata["repository"] = paper.get("url_official")
                
                # Add GitHub stars if available
                if paper.get("stars"):
                    metadata["stars"] = paper.get("stars")
                    metadata["citation_count"] = paper.get("stars")  # Use stars as proxy for citations
                
                docs.append(
                    RawDocument(
                        title=title,
                        source_url=url,
                        source_type="academic",
                        source_name=self.name,
                        text=f"{title}. {abstract}",
                        authors=authors,
                        publication_date=pub_date,
                        metadata=metadata,
                    )
                )
            
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
    name = "NewsAPI"
    route_name = "newsapi"
    source_type = "news"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, api_key=settings.newsapi_key)
        self.lookback_days = settings.news_lookback_days

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        since = (datetime.now(UTC) - timedelta(days=self.lookback_days)).date().isoformat()
        params = {
            "q": query,
            "from": since,
            "language": "en",
            "sortBy": "relevancy",
            "pageSize": min(max_results, 100),
            "apiKey": self.api_key,
        }
        try:
            response = await self.http.get("https://newsapi.org/v2/everything", params=params)
            response.raise_for_status()
            docs = []
            for item in response.json().get("articles", []):
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

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        params = {"q": query, "lang": "en", "max": min(max_results, 100), "apikey": self.api_key}
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
    name = "Serper"
    route_name = "serper"
    source_type = "web"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, api_key=settings.serper_api_key)

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
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
                        metadata={"domain": domain, "position": item.get("position")},
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


class FirecrawlClient(HttpSourceClient):
    name = "Firecrawl"
    route_name = "firecrawl"
    source_type = "web"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, api_key=settings.firecrawl_api_key)

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        try:
            response = await self.http.post(
                "https://api.firecrawl.dev/v1/search",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
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


class MediaCloudClient(HttpSourceClient):
    name = "MediaCloud"
    route_name = "mediacloud"
    source_type = "news"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, api_key=settings.mediacloud_api_key)

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        try:
            response = await self.http.get(
                "https://api.mediacloud.org/api/v2/search/story-list",
                params={"q": query, "rows": min(max_results, 100), "key": self.api_key},
            )
            response.raise_for_status()
            stories = response.json().get("stories", [])
            docs = [
                RawDocument(
                    title=item.get("title") or "MediaCloud story",
                    source_url=item.get("url"),
                    source_type="news",
                    source_name=self.name,
                    text=f"{item.get('title', '')}. {item.get('description', '')}",
                    publication_date=(item.get("publish_date") or "")[:10],
                    metadata={"publisher": item.get("media_name"), "domain": domain},
                )
                for item in stories
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
                        },
                    )
                )
            
            return FetchResult(source_name=self.name, documents=docs)
            
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))


class ApifyYouTubeScraperClient(HttpSourceClient):
    """
    YouTube search using Google Search with site:youtube.com filter.
    Free alternative that doesn't require specialized actors.
    """
    name = "Apify YouTube"
    route_name = "apify_youtube"
    source_type = "video"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, api_key=settings.apify_api_token)
        self.serper_key = settings.serper_api_key

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        """Fetch YouTube videos using Google search with site:youtube.com filter."""
        try:
            if not self.serper_key:
                return FetchResult(
                    source_name=self.name,
                    error="YouTube search requires Serper API key"
                )
            
            youtube_query = f"site:youtube.com {query}"
            response = await self.http.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": self.serper_key, "Content-Type": "application/json"},
                json={"q": youtube_query, "num": min(max_results, 20)},
            )
            response.raise_for_status()
            
            docs = []
            for item in response.json().get("organic", []):
                url = item.get("link", "")
                # Only include actual video URLs
                if "watch?v=" in url or "youtu.be/" in url:
                    docs.append(
                        RawDocument(
                            title=item.get("title") or "YouTube video",
                            source_url=url,
                            source_type="video",
                            source_name=self.name,
                            text=f"{item.get('title', '')}. {item.get('snippet', '')}",
                            publication_date=item.get("date"),
                            metadata={
                                "domain": domain,
                                "position": item.get("position"),
                            },
                        )
                    )
            
            return FetchResult(source_name=self.name, documents=docs)
            
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))


class ApifyTwitterScraperClient(HttpSourceClient):
    """
    Twitter/X scraper using Apify's tweet-scraper actor.
    Scrapes tweets, profiles, and trends.
    """
    name = "Apify Twitter"
    route_name = "apify_twitter"
    source_type = "social"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        super().__init__(http, api_key=settings.apify_api_token)
        self.timeout = settings.apify_scraper_timeout_secs

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        """Fetch tweets matching search query."""
        try:
            response = await self.http.post(
                "https://api.apify.com/v2/acts/apidojo~tweet-scraper/run-sync-get-dataset-items",
                params={"token": self.api_key, "timeout": min(self.timeout, 120)},
                json={
                    "queries": [query],
                    "maxItems": min(max_results, 100),
                    "sort": "Latest",
                    "tweetLanguage": "en",
                },
                timeout=min(float(self.timeout) + 10.0, 130.0),
            )
            
            # Apify returns 201 Created on success, not 200
            if response.status_code not in [200, 201]:
                response.raise_for_status()
            
            items = response.json()
            
            docs = []
            for item in items[:max_results]:
                # Handle both direct tweet objects and nested structures
                author_info = item.get("author", {})
                if isinstance(author_info, dict):
                    author = author_info.get("userName", "unknown")
                else:
                    author = str(author_info) if author_info else "unknown"
                
                tweet_id = item.get("id", "")
                tweet_url = item.get("url") or f"https://twitter.com/status/{tweet_id}" if tweet_id else ""
                
                docs.append(
                    RawDocument(
                        title=f"Tweet by @{author}",
                        source_url=tweet_url,
                        source_type="social",
                        source_name=self.name,
                        text=item.get("text", "") or item.get("fullText", ""),
                        publication_date=item.get("createdAt"),
                        metadata={
                            "domain": domain,
                            "author": author,
                            "retweets": item.get("retweetCount", 0),
                            "likes": item.get("likeCount", 0),
                            "replies": item.get("replyCount", 0),
                        },
                    )
                )
            
            return FetchResult(source_name=self.name, documents=docs)
            
        except Exception as exc:
            return FetchResult(source_name=self.name, error=str(exc))


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


def build_clients(http: httpx.AsyncClient, settings: Settings):
    return [
        # Academic sources
        ArxivClient(http, settings),
        SemanticScholarClient(http, settings),
        OpenAlexClient(http, settings),
        PapersWithCodeClient(http, settings),
        
        # Industry sources
        HuggingFaceClient(http, settings),
        GitHubClient(http, settings),
        
        # News sources
        NewsApiClient(http, settings),
        GNewsClient(http, settings),
        GoogleNewsRSSClient(http, settings),
        SerpApiGoogleNewsClient(http, settings),
        GuardianClient(http, settings),
        NyTimesClient(http, settings),
        
        # Web search & scraping
        SerperClient(http, settings),
        ExaClient(http, settings),
        TavilyClient(http, settings),
        FirecrawlClient(http, settings),
        
        # Apify scrapers (Premium subscription - multiple sources)
        ApifyWebScraperClient(http, settings),
        ApifyGoogleSearchScraperClient(http, settings),
        ApifyRedditScraperClient(http, settings),
        ApifyYouTubeScraperClient(http, settings),
        ApifyTwitterScraperClient(http, settings),
        ApifyNewsScraperClient(http, settings),
    ]
