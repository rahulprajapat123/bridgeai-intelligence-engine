from __future__ import annotations

import pytest
import httpx

from research_intel.config import Settings
from research_intel.ingestion.base import RawDocument
from research_intel.services.document_parser import DocumentParserService


@pytest.mark.asyncio
async def test_document_parser_enriches_short_html_documents():
    async def handler(request: httpx.Request) -> httpx.Response:
        html = """
        <html><body><article>
        <h1>Deep page</h1>
        <p>This page contains detailed analysis.</p>
        <p>""" + ("Evidence rich content. " * 120) + """</p>
        </article></body></html>
        """
        return httpx.Response(200, text=html, headers={"content-type": "text/html"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        parser = DocumentParserService(Settings(database_connection_string="sqlite:///:memory:"))
        enriched = await parser.enrich_document(
            http,
            RawDocument(
                title="Short result",
                source_url="https://example.org/deep-page",
                source_type="web",
                source_name="Search",
                text="short snippet",
            ),
        )

    assert len(enriched.text) > 1000
    assert enriched.metadata["enrichment_parser"] == "direct_html"
