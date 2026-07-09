from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urlparse

import httpx


@dataclass(slots=True)
class RawDocument:
    title: str
    source_url: str
    source_type: str
    source_name: str
    text: str
    authors: list[str] = field(default_factory=list)
    publication_date: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass(slots=True)
class FetchResult:
    source_name: str
    documents: list[RawDocument] = field(default_factory=list)
    error: str | None = None


class SourceClient(Protocol):
    name: str
    route_name: str
    source_type: str

    def enabled(self) -> bool: ...

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        ...


class SourcePolicy:
    excluded_hosts = ("linkedin.com", "twitter.com", "x.com", "youtube.com", "youtu.be")

    def allowed(self, document: RawDocument) -> bool:
        host = urlparse(document.source_url).netloc.lower()
        if any(excluded in host for excluded in self.excluded_hosts):
            return False
        if not document.title or not document.source_url:
            return False
        return True


class HttpSourceClient:
    name = "base"
    route_name = "base"
    source_type = "web"

    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        api_key: str | None = None,
        enabled_without_key: bool = False,
    ) -> None:
        self.http = http
        self.api_key = api_key
        self.enabled_without_key = enabled_without_key

    def enabled(self) -> bool:
        return bool(self.api_key or self.enabled_without_key)

    async def fetch(self, query: str, *, max_results: int, domain: str | None = None) -> FetchResult:
        raise NotImplementedError


def first_text(*values: str | None) -> str:
    for value in values:
        if value:
            return value
    return ""

