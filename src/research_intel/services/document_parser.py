from __future__ import annotations

import base64
import io
import re
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader

from research_intel.config import Settings
from research_intel.ingestion.base import RawDocument


class DocumentParserService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def enrich_documents(
        self, http: httpx.AsyncClient, documents: list[RawDocument]
    ) -> list[RawDocument]:
        return await self._gather(http, documents)

    async def _gather(self, http: httpx.AsyncClient, documents: list[RawDocument]) -> list[RawDocument]:
        import asyncio

        tasks = [self.enrich_document(http, document) for document in documents]
        enriched = await asyncio.gather(*tasks, return_exceptions=True)
        output: list[RawDocument] = []
        for document, result in zip(documents, enriched, strict=False):
            output.append(document if isinstance(result, Exception) else result)
        return output

    async def enrich_document(self, http: httpx.AsyncClient, document: RawDocument) -> RawDocument:
        if self._is_sufficient(document):
            return document

        if "github.com" in document.source_url:
            github = await self._github_readme(http, document)
            if github:
                return github

        if "huggingface.co" in document.source_url:
            huggingface = await self._huggingface_card(http, document)
            if huggingface:
                return huggingface

        direct = await self._direct_fetch(http, document)
        if direct and len(direct.text) > len(document.text or "") + 300:
            return direct

        firecrawl = await self._firecrawl_scrape(http, document)
        if firecrawl and len(firecrawl.text) > len(document.text or "") + 300:
            return firecrawl

        apify = await self._apify_scrape(http, document)
        if apify and len(apify.text) > len(document.text or "") + 300:
            return apify

        return document

    def _is_sufficient(self, document: RawDocument) -> bool:
        text_length = len((document.text or "").strip())
        if document.source_type == "academic":
            return text_length >= 350
        if document.source_type == "news":
            return text_length >= 1600
        if document.source_type in {"web", "code", "industry", "vendor", "blog"}:
            return text_length >= 1200
        return text_length >= 800

    async def _github_readme(self, http: httpx.AsyncClient, document: RawDocument) -> RawDocument | None:
        match = re.search(r"github\.com/([^/]+)/([^/?#]+)", document.source_url)
        if not match:
            return None
        owner, repo = match.group(1), match.group(2).removesuffix(".git")
        headers = {}
        if self.settings.github_token:
            headers["Authorization"] = f"Bearer {self.settings.github_token}"
        try:
            response = await http.get(
                f"https://api.github.com/repos/{owner}/{repo}/readme",
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()
            encoded = payload.get("content", "")
            text = base64.b64decode(encoded).decode("utf-8", errors="ignore")
            if not text.strip():
                return None
            return self._copy(
                document,
                text=f"{document.text}\n\nREADME:\n{text[:20000]}",
                parser="github_readme",
            )
        except Exception:
            return None

    async def _huggingface_card(self, http: httpx.AsyncClient, document: RawDocument) -> RawDocument | None:
        match = re.search(r"huggingface\.co/([^/?#]+/[^/?#]+)", document.source_url)
        if not match:
            return None
        model_id = match.group(1)
        headers = {}
        if self.settings.huggingface_token:
            headers["Authorization"] = f"Bearer {self.settings.huggingface_token}"
        try:
            response = await http.get(f"https://huggingface.co/api/models/{model_id}", headers=headers)
            response.raise_for_status()
            payload = response.json()
            card_data = payload.get("cardData") or {}
            text_parts = [
                document.text,
                payload.get("pipeline_tag", ""),
                payload.get("library_name", ""),
                " ".join(payload.get("tags") or []),
                str(card_data),
            ]
            text = "\n".join(part for part in text_parts if part).strip()[:20000]
            if len(text) <= len(document.text or ""):
                return None
            return self._copy(document, text=text, parser="huggingface_model_api")
        except Exception:
            return None

    async def _direct_fetch(self, http: httpx.AsyncClient, document: RawDocument) -> RawDocument | None:
        try:
            response = await http.get(document.source_url, timeout=self.settings.request_timeout_seconds)
            response.raise_for_status()
        except Exception:
            return None

        content_type = (response.headers.get("content-type") or "").lower()
        if "pdf" in content_type or document.source_url.lower().endswith(".pdf"):
            return self._parse_pdf_response(document, response.content)
        if "text/html" in content_type or "<html" in response.text[:500].lower():
            text = self._extract_html_text(response.text)
            if text:
                return self._copy(document, text=text[:25000], parser="direct_html")
            return None
        text = response.text.strip()
        if text:
            return self._copy(document, text=text[:25000], parser="direct_text")
        return None

    async def _firecrawl_scrape(self, http: httpx.AsyncClient, document: RawDocument) -> RawDocument | None:
        if not self.settings.firecrawl_api_key:
            return None
        try:
            response = await http.post(
                "https://api.firecrawl.dev/v1/scrape",
                headers={
                    "Authorization": f"Bearer {self.settings.firecrawl_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "url": document.source_url,
                    "formats": ["markdown"],
                    "onlyMainContent": True,
                },
            )
            response.raise_for_status()
            payload = response.json()
            data = payload.get("data") or {}
            text = (data.get("markdown") or data.get("content") or "").strip()
            if not text:
                return None
            return self._copy(document, text=text[:25000], parser="firecrawl_scrape")
        except Exception:
            return None

    async def _apify_scrape(self, http: httpx.AsyncClient, document: RawDocument) -> RawDocument | None:
        if not self.settings.apify_api_token:
            return None
        try:
            response = await http.post(
                "https://api.apify.com/v2/acts/apify~website-content-crawler/run-sync-get-dataset-items",
                params={"token": self.settings.apify_api_token, "timeout": min(120, self.settings.apify_scraper_timeout_secs)},
                json={
                    "startUrls": [{"url": document.source_url}],
                    "maxCrawlPages": 1,
                    "crawlerType": "playwright:adaptive",
                    "renderJavaScript": self.settings.apify_enable_javascript,
                    "maxResults": 1,
                },
                timeout=min(130.0, float(self.settings.apify_scraper_timeout_secs) + 10.0),
            )
            response.raise_for_status()
            items = response.json()
            if not items:
                return None
            first = items[0]
            text = (
                first.get("text")
                or first.get("markdown")
                or first.get("description")
                or ""
            ).strip()
            if not text:
                return None
            return self._copy(document, text=text[:25000], parser="apify_scrape")
        except Exception:
            return None

    def _parse_pdf_response(self, document: RawDocument, content: bytes) -> RawDocument | None:
        try:
            reader = PdfReader(io.BytesIO(content))
            pages = [page.extract_text() or "" for page in reader.pages]
            text = "\n\n".join(page for page in pages if page).strip()
            if not text:
                return None
            return self._copy(document, text=text[:25000], parser="direct_pdf")
        except Exception:
            return None

    def _extract_html_text(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()
        main = soup.find("main") or soup.find("article") or soup.body or soup
        text = main.get_text("\n", strip=True)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)

    def _copy(self, document: RawDocument, *, text: str, parser: str) -> RawDocument:
        metadata = {**document.metadata, "enrichment_parser": parser}
        return RawDocument(
            title=document.title,
            source_url=document.source_url,
            source_type=document.source_type,
            source_name=document.source_name,
            text=text,
            authors=document.authors,
            publication_date=document.publication_date,
            metadata=metadata,
        )
