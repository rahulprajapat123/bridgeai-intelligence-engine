"""
Private Source Integration for Authenticated Scraping.

This module provides integration templates for private sources like:
- Gartner
- Forrester
- Sprinklr
- BrightEdge
- Adbeat
- Private CRMs
- Authenticated dashboards

Uses Apify for complex scraping with authentication.
"""
from __future__ import annotations

from typing import Any
import httpx
from research_intel.config import Settings
from research_intel.ingestion.base import FetchResult, RawDocument


class PrivateSourceConfig:
    """Configuration for private source authentication."""
    
    def __init__(self, settings: Settings):
        self.gartner_username = settings.gartner_username
        self.gartner_password = settings.gartner_password
        self.forrester_username = settings.forrester_username
        self.forrester_password = settings.forrester_password
        self.brightedge_api_key = settings.brightedge_api_key
        self.sprinklr_api_key = settings.sprinklr_api_key
        self.adbeat_api_key = settings.adbeat_api_key
        self.apify_token = settings.apify_api_token


class ApifyAuthenticatedScraper:
    """
    Base class for authenticated scraping using Apify.
    Handles login flows and authenticated content extraction.
    """
    
    def __init__(self, http: httpx.AsyncClient, config: PrivateSourceConfig):
        self.http = http
        self.config = config
        self.apify_token = config.apify_token
    
    async def scrape_with_auth(
        self,
        start_url: str,
        login_config: dict[str, Any],
        scrape_config: dict[str, Any],
    ) -> list[RawDocument]:
        """
        Scrape authenticated content using Apify's Web Scraper.
        
        Args:
            start_url: The URL to scrape after login
            login_config: Authentication configuration
            scrape_config: Scraping configuration
        """
        try:
            # Use Apify's Web Scraper with authentication
            actor_id = "apify/web-scraper"
            
            run_input = {
                "startUrls": [{"url": start_url}],
                "proxyConfiguration": {"useApifyProxy": True},
                **scrape_config,
            }
            
            # Add authentication if provided
            if login_config:
                run_input["preNavigationHooks"] = [
                    {
                        "type": "function",
                        "code": self._generate_login_script(login_config),
                    }
                ]
            
            # Run the scraper
            response = await self.http.post(
                f"https://api.apify.com/v2/acts/{actor_id}/run-sync",
                params={"token": self.apify_token, "timeout": 300},
                json=run_input,
                timeout=330.0,
            )
            response.raise_for_status()
            
            items = response.json()
            return self._parse_items(items)
            
        except Exception as e:
            raise Exception(f"Authenticated scraping failed: {str(e)}")
    
    def _generate_login_script(self, login_config: dict[str, Any]) -> str:
        """Generate Playwright login script."""
        username = login_config.get("username", "")
        password = login_config.get("password", "")
        username_selector = login_config.get("username_selector", "#username")
        password_selector = login_config.get("password_selector", "#password")
        submit_selector = login_config.get("submit_selector", "button[type='submit']")
        
        return f"""
        async function pageFunction(context) {{
            const {{ page }} = context;
            
            // Wait for login form
            await page.waitForSelector('{username_selector}');
            
            // Fill in credentials
            await page.fill('{username_selector}', '{username}');
            await page.fill('{password_selector}', '{password}');
            
            // Submit
            await page.click('{submit_selector}');
            
            // Wait for navigation
            await page.waitForNavigation();
        }}
        """
    
    def _parse_items(self, items: list[dict]) -> list[RawDocument]:
        """Parse Apify results into RawDocuments."""
        documents = []
        for item in items:
            if item.get("text") or item.get("html"):
                documents.append(
                    RawDocument(
                        title=item.get("title", "Scraped document"),
                        source_url=item.get("url", ""),
                        source_type="private",
                        source_name="Authenticated Source",
                        text=item.get("text") or "",
                        metadata={
                            "scraped_at": item.get("crawledAt"),
                            "authenticated": True,
                        },
                    )
                )
        return documents


class GartnerIntegration(ApifyAuthenticatedScraper):
    """
    Scrape Gartner reports and research (requires subscription).
    
    Example usage:
        gartner = GartnerIntegration(http, config)
        docs = await gartner.scrape_research("AI in healthcare")
    """
    
    async def scrape_research(self, query: str) -> FetchResult:
        """Scrape Gartner research on a topic."""
        if not self.config.gartner_username or not self.config.gartner_password:
            return FetchResult(
                source_name="Gartner",
                error="Gartner credentials not configured",
            )
        
        try:
            login_config = {
                "username": self.config.gartner_username,
                "password": self.config.gartner_password,
                "username_selector": "input[name='username']",
                "password_selector": "input[name='password']",
                "submit_selector": "button[type='submit']",
            }
            
            search_url = f"https://www.gartner.com/en/search?keywords={query}"
            
            scrape_config = {
                "maxCrawlPages": 10,
                "pageFunction": """
                async function pageFunction(context) {
                    const { page } = context;
                    const title = await page.title();
                    const text = await page.textContent('body');
                    return { title, text, url: page.url() };
                }
                """
            }
            
            docs = await self.scrape_with_auth(search_url, login_config, scrape_config)
            
            return FetchResult(source_name="Gartner", documents=docs)
            
        except Exception as e:
            return FetchResult(source_name="Gartner", error=str(e))


class ForresterIntegration(ApifyAuthenticatedScraper):
    """
    Scrape Forrester research (requires subscription).
    """
    
    async def scrape_research(self, query: str) -> FetchResult:
        """Scrape Forrester research on a topic."""
        if not self.config.forrester_username or not self.config.forrester_password:
            return FetchResult(
                source_name="Forrester",
                error="Forrester credentials not configured",
            )
        
        try:
            login_config = {
                "username": self.config.forrester_username,
                "password": self.config.forrester_password,
                "username_selector": "#email",
                "password_selector": "#password",
                "submit_selector": "button[type='submit']",
            }
            
            search_url = f"https://www.forrester.com/search?q={query}"
            
            scrape_config = {
                "maxCrawlPages": 10,
            }
            
            docs = await self.scrape_with_auth(search_url, login_config, scrape_config)
            
            return FetchResult(source_name="Forrester", documents=docs)
            
        except Exception as e:
            return FetchResult(source_name="Forrester", error=str(e))


class BrightEdgeExporter:
    """
    Export data from BrightEdge SEO platform.
    Requires API key or can scrape authenticated dashboard.
    """
    
    def __init__(self, api_key: str | None):
        self.api_key = api_key
    
    async def export_search_data(self, http: httpx.AsyncClient, query: str) -> FetchResult:
        """Export search analytics data."""
        if not self.api_key:
            return FetchResult(
                source_name="BrightEdge",
                error="BrightEdge API key not configured",
            )
        
        # BrightEdge API implementation would go here
        # This is a placeholder for the actual API integration
        return FetchResult(
            source_name="BrightEdge",
            error="BrightEdge API integration pending - API documentation needed",
        )


class SprinklrExporter:
    """
    Export data from Sprinklr social media management platform.
    """
    
    def __init__(self, api_key: str | None):
        self.api_key = api_key
    
    async def export_social_data(self, http: httpx.AsyncClient, query: str) -> FetchResult:
        """Export social listening data."""
        if not self.api_key:
            return FetchResult(
                source_name="Sprinklr",
                error="Sprinklr API key not configured",
            )
        
        # Sprinklr API implementation would go here
        return FetchResult(
            source_name="Sprinklr",
            error="Sprinklr API integration pending - API documentation needed",
        )


class AdbeatExporter:
    """
    Export competitive advertising intelligence from Adbeat.
    """
    
    def __init__(self, api_key: str | None):
        self.api_key = api_key
    
    async def export_ad_intelligence(self, http: httpx.AsyncClient, competitor: str) -> FetchResult:
        """Export competitor advertising data."""
        if not self.api_key:
            return FetchResult(
                source_name="Adbeat",
                error="Adbeat API key not configured",
            )
        
        # Adbeat API implementation would go here
        return FetchResult(
            source_name="Adbeat",
            error="Adbeat API integration pending - API documentation needed",
        )


# Template for adding more private sources
class CustomPrivateSource(ApifyAuthenticatedScraper):
    """
    Template for integrating custom private sources.
    
    To add a new source:
    1. Inherit from ApifyAuthenticatedScraper
    2. Implement scrape_* methods
    3. Configure authentication in login_config
    4. Add to private_sources.py registration
    """
    
    async def scrape_custom(self, url: str, auth_config: dict) -> FetchResult:
        """Scrape custom authenticated source."""
        try:
            docs = await self.scrape_with_auth(url, auth_config, {})
            return FetchResult(source_name="Custom Source", documents=docs)
        except Exception as e:
            return FetchResult(source_name="Custom Source", error=str(e))
