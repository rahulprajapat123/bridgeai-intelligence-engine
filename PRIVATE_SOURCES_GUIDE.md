# Private Source Integration Guide

## Overview

This system now supports scraping and extracting information from private, authenticated sources including:

✅ **Analyst Firms:**
- Gartner
- Forrester
- IDC
- McKinsey

✅ **Marketing Platforms:**
- BrightEdge (SEO analytics)
- Sprinklr (Social media management)
- Adbeat (Competitive advertising intelligence)

✅ **Web Scraping:**
- Apify Web Scraper (authenticated sites)
- Apify Google Search Scraper
- Apify LinkedIn Scraper
- FireCrawl (web content extraction)

✅ **Document Formats:**
- PDF (with metadata & layout preservation)
- DOCX (with tables and headings)
- HTML (cleaned text extraction)
- RTF (basic support)
- TXT, MD

---

## Configuration

### 1. Update .env File

Add credentials for private sources:

```bash
# Apify (Required for authenticated scraping)
APIFY_API_TOKEN=your_apify_token_here
APIFY_SCRAPER_TIMEOUT_SECS=300
APIFY_MAX_PAGES_PER_SCRAPE=10
APIFY_ENABLE_JAVASCRIPT=true

# Analyst Firms (Optional - requires subscriptions)
GARTNER_USERNAME=your_gartner_email
GARTNER_PASSWORD=your_gartner_password
FORRESTER_USERNAME=your_forrester_email
FORRESTER_PASSWORD=your_forrester_password

# Marketing Platforms (Optional)
BRIGHTEDGE_API_KEY=your_brightedge_key
SPRINKLR_API_KEY=your_sprinklr_key
ADBEAT_API_KEY=your_adbeat_key
```

### 2. Available Scrapers

The system now includes these scraping clients:

**Academic:**
- Semantic Scholar
- OpenAlex
- arXiv

**Industry:**
- GitHub
- Hugging Face

**News:**
- NewsAPI
- GNews
- The Guardian
- New York Times
- MediaCloud

**Web Search:**
- Serper (Google search)
- Exa.ai (neural search)
- Tavily (advanced web search)
- FireCrawl (web content)

**Apify Scrapers (NEW):**
- ApifyWebScraperClient - General authenticated scraping
- ApifyGoogleSearchScraperClient - High-quality search results
- ApifyLinkedInScraperClient - Company intelligence

---

## Usage Examples

### Example 1: Scrape Authenticated Gartner Content

```python
from research_intel.ingestion.private_sources import GartnerIntegration, PrivateSourceConfig
from research_intel.config import get_settings
import httpx
import asyncio

async def scrape_gartner():
    settings = get_settings()
    config = PrivateSourceConfig(settings)
    
    async with httpx.AsyncClient() as http:
        gartner = GartnerIntegration(http, config)
        result = await gartner.scrape_research("AI in healthcare")
        
        print(f"Found {len(result.documents)} Gartner documents")
        for doc in result.documents:
            print(f"- {doc.title}")
            print(f"  URL: {doc.source_url}")
            print(f"  Preview: {doc.text[:200]}...")

asyncio.run(scrape_gartner())
```

### Example 2: Use Apify for Custom Web Scraping

```python
from research_intel.ingestion.clients import ApifyWebScraperClient
from research_intel.config import get_settings
import httpx
import asyncio

async def scrape_custom_site():
    settings = get_settings()
    
    async with httpx.AsyncClient() as http:
        scraper = ApifyWebScraperClient(http, settings)
        
        # Scrape any website (even complex JS sites)
        result = await scraper.fetch(
            query="machine learning trends 2026",
            max_results=5,
            domain="AI/ML"
        )
        
        for doc in result.documents:
            print(f"\n{doc.title}")
            print(f"URL: {doc.source_url}")
            print(f"Content: {doc.text[:300]}...")

asyncio.run(scrape_custom_site())
```

### Example 3: Enhanced Document Parsing

```python
from research_intel.services.file_parser import BriefFileParser, DocumentExtractor

# Parse a PDF with enhanced extraction
with open("research_paper.pdf", "rb") as f:
    content = f.read()

parser = BriefFileParser()
text = parser.parse("research_paper.pdf", content)

# Extract metadata
extractor = DocumentExtractor()
metadata = extractor.extract_metadata_from_pdf(content)
print(f"Title: {metadata.get('title')}")
print(f"Author: {metadata.get('author')}")
print(f"Pages: {metadata.get('page_count')}")

# Extract sections
sections = extractor.extract_sections(text)
if 'abstract' in sections:
    print(f"\nAbstract: {sections['abstract'][:500]}...")
```

### Example 4: Workflow with Private Sources

```bash
# Via API
POST /api/workflow/analyze
{
  "brief_id": "your_brief_id",
  "auto_fetch": true,
  "max_per_source": 20,
  "top_k": 10
}
```

The system will automatically:
1. Analyze the brief and determine domain
2. Route to appropriate sources (including Apify if configured)
3. Scrape authenticated content if credentials are available
4. Extract claims and generate embeddings
5. Return ranked evidence with recommendations

---

## Apify Actor Recommendations

### For Different Use Cases:

**1. General Web Scraping:**
- `apify/web-scraper` - Best for authenticated sites
- `apify/website-content-crawler` - Best for documentation

**2. Search Results:**
- `apify/google-search-scraper` - Google results
- `apify/bing-search-scraper` - Bing results

**3. Social Media:**
- `apify/linkedin-company-scraper` - Company profiles
- `apify/twitter-scraper` - Twitter/X content
- `apify/instagram-scraper` - Instagram posts

**4. E-commerce (for competitive analysis):**
- `apify/amazon-product-scraper` - Amazon data
- `apify/google-shopping-scraper` - Shopping data

**5. Documentation:**
- `apify/cheerio-scraper` - Fast static content
- `apify/puppeteer-scraper` - Dynamic content

---

## Adding New Private Sources

### Template for Custom Integration:

```python
# In private_sources.py

class YourCustomSource(ApifyAuthenticatedScraper):
    """Scrape your custom private source."""
    
    async def scrape_research(self, query: str) -> FetchResult:
        if not self.config.your_custom_username:
            return FetchResult(
                source_name="YourSource",
                error="Credentials not configured"
            )
        
        login_config = {
            "username": self.config.your_custom_username,
            "password": self.config.your_custom_password,
            "username_selector": "#username",  # CSS selector
            "password_selector": "#password",
            "submit_selector": "button[type='submit']",
        }
        
        search_url = f"https://yoursource.com/search?q={query}"
        
        scrape_config = {
            "maxCrawlPages": 10,
            "waitForSelector": ".content",  # Wait for content to load
        }
        
        docs = await self.scrape_with_auth(
            search_url, 
            login_config, 
            scrape_config
        )
        
        return FetchResult(source_name="YourSource", documents=docs)
```

### Then add to config.py:

```python
class Settings(BaseSettings):
    # ... existing settings ...
    your_custom_username: str | None = None
    your_custom_password: str | None = None
```

### And update .env:

```bash
YOUR_CUSTOM_USERNAME=username
YOUR_CUSTOM_PASSWORD=password
```

---

## Best Practices

### 1. Rate Limiting
- Apify has built-in rate limiting
- Configure `APIFY_SCRAPER_TIMEOUT_SECS` appropriately
- Use `max_results` to limit scraping volume

### 2. Authentication Security
- Store credentials in `.env` file (never commit)
- Use environment variables in production
- Consider using secret management services

### 3. Scraping Ethics
- Respect robots.txt
- Only scrape sources you have access to
- Follow terms of service
- Use proxies when appropriate

### 4. Error Handling
- All scrapers return `FetchResult` with error field
- Check `result.error` for failures
- Implement retry logic for transient failures

### 5. Content Quality
- Apify returns cleaned text/markdown
- Use `DocumentExtractor` for structured data
- Validate extracted content before storage

---

## Troubleshooting

### Apify Timeouts
```bash
# Increase timeout in .env
APIFY_SCRAPER_TIMEOUT_SECS=600
```

### Authentication Failures
- Verify credentials in `.env`
- Check if login selectors are correct
- Try manual login to verify process
- Consider using Apify's browser extension to record flow

### No Results
- Check if source requires subscription
- Verify API keys are valid
- Check scraping quotas/limits
- Enable JavaScript if needed: `APIFY_ENABLE_JAVASCRIPT=true`

### Rate Limits
- Reduce `max_per_source` in requests
- Increase delays between requests
- Use Apify's proxy rotation

---

## Testing

Test your Apify integration:

```bash
python scripts/test_apify.py
```

Test a specific scraper:

```python
# Create a test script
from research_intel.ingestion.clients import ApifyGoogleSearchScraperClient
from research_intel.config import get_settings
import httpx
import asyncio

async def test():
    settings = get_settings()
    async with httpx.AsyncClient() as http:
        client = ApifyGoogleSearchScraperClient(http, settings)
        result = await client.fetch("RAG systems", max_results=5)
        print(f"Results: {len(result.documents)}")
        for doc in result.documents:
            print(f"- {doc.title}")

asyncio.run(test())
```

---

## API Endpoints

All new scraping capabilities are automatically available through existing endpoints:

**Full Workflow:**
```bash
POST /api/workflow/analyze
{
  "text": "Build a competitive intelligence system for healthcare",
  "auto_fetch": true
}
```

**Direct Ingestion:**
```bash
POST /api/ingest
{
  "topic": "healthcare AI trends",
  "domain": "Business Intelligence",
  "max_per_source": 10
}
```

The system will automatically use Apify scrapers when:
- Domain requires authenticated sources
- Topic matches Gartner/Forrester keywords
- Standard sources return insufficient results

---

## Monitoring

Check source health:
```bash
GET /api/sources
```

View ingestion runs:
```bash
GET /api/ingestion-runs?limit=20
```

---

## Next Steps

1. **Configure credentials** for sources you need
2. **Test individual scrapers** with sample queries
3. **Run full workflow** to see integrated results
4. **Monitor performance** through API endpoints
5. **Add custom sources** following templates above

For questions or issues, check the Apify documentation:
https://docs.apify.com/
