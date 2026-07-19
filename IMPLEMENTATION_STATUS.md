# Implementation Status & Integration Guide
## Data Sources Analysis for Intelligence Engine

---

## ✅ ALREADY IMPLEMENTED (Working)

### **Academic/Research Papers**
| Source | Status | API Key | Implementation |
|--------|--------|---------|----------------|
| OpenAlex | ✅ Working | No key needed | `OpenAlexClient` |
| Semantic Scholar | ✅ Working | `SEMANTIC_SCHOLAR_API_KEY` | `SemanticScholarClient` |
| arXiv | ✅ Working | No key needed | `ArxivClient` |
| Papers with Code | ✅ Working | No key needed | `PapersWithCodeClient` |

### **Code Repositories**
| Source | Status | API Key | Implementation |
|--------|--------|---------|----------------|
| GitHub | ✅ Working | `GITHUB_TOKEN` | `GitHubClient` |
| Hugging Face | ✅ Working | `HUGGINGFACE_TOKEN` | `HuggingFaceClient` |

### **News Sources**
| Source | Status | API Key | Implementation |
|--------|--------|---------|----------------|
| Guardian | ✅ Working | `GUARDIAN_API_KEY` | `GuardianClient` |
| NY Times | ✅ Working | `NYTIMES_API_KEY` | `NyTimesClient` |
| NewsAPI | ✅ Working | `NEWSAPI_KEY` | `NewsApiClient` |
| GNews | ✅ Working | `GNEWS_API_KEY` | `GNewsClient` |
| Google News RSS | ✅ Working | No key needed | `GoogleNewsRSSClient` |
| SerpAPI News | ✅ Working | `SERPAPI_API_KEY` | `SerpApiGoogleNewsClient` |
| Apify News Scraper | ✅ Working | `APIFY_API_TOKEN` | `ApifyNewsScraperClient` |

### **Web Search & Scraping**
| Source | Status | API Key | Implementation |
|--------|--------|---------|----------------|
| Exa.ai | ✅ Working | `EXA_API_KEY` | `ExaClient` |
| Tavily | ✅ Working | `TAVILY_API_KEY` | `TavilyClient` |
| Serper | ✅ Working | `SERPER_API_KEY` | `SerperClient` |
| Firecrawl | ✅ Working | `FIRECRAWL_API_KEY` | `FirecrawlClient` (for scraping) |
| Apify Web Scraper | ✅ Working | `APIFY_API_TOKEN` | `ApifyWebScraperClient` |
| Apify Google Search | ✅ Working | `APIFY_API_TOKEN` | `ApifyGoogleSearchScraperClient` |

### **Social Media & Forums**
| Source | Status | API Key | Implementation |
|--------|--------|---------|----------------|
| Reddit (Apify) | ✅ Working | `APIFY_API_TOKEN` | `ApifyRedditScraperClient` |
| Twitter (Apify) | ✅ Working | `APIFY_API_TOKEN` | `ApifyTwitterScraperClient` |
| YouTube (Apify) | ✅ Working | `APIFY_API_TOKEN` | `ApifyYouTubeScraperClient` |

### **Infrastructure (Backend)**
| Component | Status | Implementation |
|-----------|--------|----------------|
| FastAPI | ✅ Working | `src/research_intel/api/routes.py` |
| PostgreSQL | ✅ Working | `DATABASE_CONNECTION_STRING` in .env |
| pgvector | ✅ Working | Used for embeddings |
| Resend Email | ✅ Working | `RESEND_API_KEY` |

**Total Implemented: 26+ sources**

---

## ❌ NOT IMPLEMENTED (Need to Add)

### **Category 1: FREE APIs (Can Implement Immediately)**

#### **1. Jina AI Reader** 🆕 PRIORITY
- **Cost**: FREE (1M requests/month)
- **Use Case**: Convert any URL to clean markdown/text
- **Implementation**: ✅ **I can implement this now**
  - No API key needed
  - Simple GET request: `https://r.jina.ai/{url}`
  - Add `JinaAIClient` class to clients.py
  
```python
# Implementation example
class JinaAIClient(HttpSourceClient):
    name = "Jina AI Reader"
    route_name = "jina"
    source_type = "web"
    
    async def fetch(self, url: str) -> FetchResult:
        response = await self.http.get(f"https://r.jina.ai/{url}")
        # Returns clean markdown automatically
```

#### **2. HackerNews API** 🆕 PRIORITY
- **Cost**: FREE unlimited
- **Use Case**: Tech news, startup discussions, trending topics
- **Implementation**: ✅ **I can implement this now**
  - No API key needed
  - Firebase API: `https://hacker-news.firebaseio.com/v0/`
  - Add `HackerNewsClient` class

#### **3. Dev.to API** 🆕 PRIORITY
- **Cost**: FREE unlimited
- **Use Case**: Developer blogs, tutorials, tech articles
- **Implementation**: ✅ **I can implement this now**
  - No API key needed
  - REST API: `https://dev.to/api/articles`
  - Add `DevToClient` class

#### **4. npm API** 🆕
- **Cost**: FREE unlimited
- **Use Case**: JavaScript package metadata, documentation
- **Implementation**: ✅ **I can implement this now**
  - No API key needed
  - API: `https://registry.npmjs.org/{package}`
  - Add `NpmClient` class

#### **5. PyPI API** 🆕
- **Cost**: FREE unlimited
- **Use Case**: Python package metadata, documentation
- **Implementation**: ✅ **I can implement this now**
  - No API key needed
  - API: `https://pypi.org/pypi/{package}/json`
  - Add `PyPIClient` class

#### **6. GitLab API** 🆕
- **Cost**: FREE (5,000 requests/min)
- **Use Case**: GitLab repositories, alternative to GitHub
- **Implementation**: ⚠️ **Need FREE GitLab account**
  - Register at: https://gitlab.com/users/sign_up
  - Generate personal access token
  - API: `https://gitlab.com/api/v4/`
  - Add to .env: `GITLAB_TOKEN=glpat-...`

#### **7. RSS Feed Parser** 🆕 PRIORITY
- **Cost**: FREE
- **Use Case**: Company blogs, tech news feeds
- **Implementation**: ✅ **I can implement this now**
  - Already using `feedparser` library (imported in clients.py!)
  - Add `RSSFeedClient` with predefined feed list
  - 50+ feeds from CONTENT_SOURCE_MAPPING.md

#### **8. GDELT** 🆕
- **Cost**: FREE unlimited
- **Use Case**: Global news events, trends, sentiment
- **Implementation**: ✅ **I can implement this now**
  - No API key needed
  - API: `https://api.gdeltproject.org/api/v2/`
  - Add `GDELTClient` class

---

### **Category 2: FREE Registration Required**

#### **9. PubMed/NCBI** 🆕 RECOMMENDED
- **Cost**: FREE (10 requests/second with key)
- **Use Case**: Biomedical/health research papers (35M citations)
- **Registration**: ⚠️ **You need to register**
  - Go to: https://www.ncbi.nlm.nih.gov/account/
  - Create free NCBI account
  - Get API key (improves rate limits)
  - Add to .env: `PUBMED_API_KEY=...`
  - API: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/`

#### **10. CORE API** 🆕 RECOMMENDED
- **Cost**: FREE (10k requests/day)
- **Use Case**: Open access papers (240M papers)
- **Registration**: ⚠️ **You need to register**
  - Go to: https://core.ac.uk/services/api
  - Register for free API key
  - Add to .env: `CORE_API_KEY=...`
  - API: `https://api.core.ac.uk/v3/`

#### **11. ProductHunt API** 🆕 RECOMMENDED
- **Cost**: FREE
- **Use Case**: Daily tech product launches
- **Registration**: ⚠️ **You need to register**
  - Go to: https://api.producthunt.com/v2/docs
  - Create ProductHunt account
  - Register OAuth app
  - Add to .env: `PRODUCTHUNT_TOKEN=...`
  - API: GraphQL `https://api.producthunt.com/v2/api/graphql`

#### **12. Reddit Official API** 🆕
- **Cost**: FREE (60 requests/min)
- **Use Case**: Subreddit discussions (better than Apify scraper)
- **Registration**: ⚠️ **You need to register**
  - Go to: https://www.reddit.com/prefs/apps
  - Create app, get client ID + secret
  - Add to .env: `REDDIT_CLIENT_ID=...` and `REDDIT_CLIENT_SECRET=...`
  - API: `https://oauth.reddit.com/`
  - Note: You already have ApifyRedditScraperClient, this is the official API

#### **13. Brave Search API** 🆕
- **Cost**: FREE (2,000 queries/month on free tier)
- **Registration**: ⚠️ **You need to register**
  - Go to: https://brave.com/search/api/
  - Sign up for free tier
  - Add to .env: `BRAVE_SEARCH_API_KEY=...`
  - API: `https://api.search.brave.com/res/v1/web/search`

#### **14. You.com Search API** 🆕
- **Cost**: FREE tier available (check current limits)
- **Use Case**: AI-powered search, research assistant
- **Registration**: ⚠️ **You need to register**
  - Go to: https://you.com/api
  - Sign up for API access
  - Add to .env: `YOU_API_KEY=...`
  - API: Check their documentation

---

### **Category 3: PAID Upgrades (You Have Free Tiers)**

#### **15. GNews Essential** 💰
- **Cost**: You have FREE tier (100/day), Essential is €49.99/month
- **Current**: `GNEWS_API_KEY` (free tier)
- **Upgrade**: ⚠️ **Need to pay €49.99/month**
  - Go to: https://gnews.io/pricing
  - Upgrade to Essential plan (10k requests/day)
  - Replace API key in .env

#### **16. Browserbase Developer** 💰
- **Cost**: FREE tier (1 browser hour), Developer $20/month (100 hours)
- **Use Case**: Browser automation, JavaScript rendering
- **Registration**: ⚠️ **You need to register**
  - Go to: https://www.browserbase.com/
  - Sign up for free tier
  - Add to .env: `BROWSERBASE_API_KEY=...` and `BROWSERBASE_PROJECT_ID=...`
  - Note: You already have Apify for scraping, this is alternative

---

### **Category 4: Tools/Libraries (Not APIs)**

#### **17. RSSHub** 🆕
- **Cost**: FREE (self-hosted, open source)
- **Use Case**: Generate RSS feeds for sites without them
- **Implementation**: ⚠️ **Need to self-host**
  - Clone: https://github.com/DIYgod/RSSHub
  - Deploy to your server or use public instance
  - Not a client in clients.py, but feed URLs can be added to RSS feed list

#### **18. OCR Tools (PyMuPDF, OCRmyPDF, PaddleOCR)**
- **Cost**: FREE (libraries, not APIs)
- **Use Case**: PDF parsing, scanned documents
- **Implementation**: ✅ **I can add these**
  - Install via pip: `pymupdf`, `ocrmypdf`, `paddleocr`
  - Add to `document_parser.py` for enhanced PDF handling
  - Not source clients, but processing utilities

#### **19. Other Tech Stack Items**
- Redis, Celery, MinIO, Scrapy, Playwright, etc.
- These are **infrastructure tools**, not data sources
- Some already in use (PostgreSQL, pgvector)
- Others need separate setup (Redis for caching, Celery for jobs)

---

## 🚀 IMPLEMENTATION ROADMAP

### **Phase 1: Immediate FREE Implementations** (I can do now)
```python
priority_free_sources = [
    "JinaAIClient",        # No key, instant implementation
    "HackerNewsClient",    # No key, instant implementation  
    "DevToClient",         # No key, instant implementation
    "RSSFeedClient",       # Already have feedparser library
    "GDELTClient",         # No key, instant implementation
    "NpmClient",           # No key, instant implementation
    "PyPIClient",          # No key, instant implementation
]
```
**Action**: I can implement all 7 clients right now, adding ~10k+ daily sources.

### **Phase 2: FREE Registrations** (You need to sign up)
```python
free_registration_needed = {
    "PubMed": "https://www.ncbi.nlm.nih.gov/account/",
    "CORE": "https://core.ac.uk/services/api",
    "ProductHunt": "https://api.producthunt.com/v2/docs",
    "GitLab": "https://gitlab.com/users/sign_up",
    "Brave Search": "https://brave.com/search/api/",
    "Reddit Official": "https://www.reddit.com/prefs/apps",
    "You.com": "https://you.com/api",
}
```
**Action**: You register, give me API keys, I implement the clients.

### **Phase 3: Paid Upgrades** (Optional, when scaling)
```python
paid_upgrades = {
    "GNews Essential": "€49.99/month (10k/day vs 100/day)",
    "Browserbase Developer": "$20/month (100 hours vs 1 hour)",
}
```
**Action**: Upgrade when you hit free tier limits.

### **Phase 4: Infrastructure Enhancements**
- Add Redis for caching (local install or managed service)
- Add Celery for background jobs
- Enhance PDF parsing with OCR libraries
- Add more RSS feeds to RSSFeedClient

---

## 📊 SUMMARY TABLE

| Source | Status | Cost | Next Step |
|--------|--------|------|-----------|
| **Jina AI** | ❌ Not implemented | FREE | ✅ I can add now |
| **HackerNews** | ❌ Not implemented | FREE | ✅ I can add now |
| **Dev.to** | ❌ Not implemented | FREE | ✅ I can add now |
| **RSS Feeds** | ❌ Not implemented | FREE | ✅ I can add now |
| **GDELT** | ❌ Not implemented | FREE | ✅ I can add now |
| **npm** | ❌ Not implemented | FREE | ✅ I can add now |
| **PyPI** | ❌ Not implemented | FREE | ✅ I can add now |
| **PubMed** | ❌ Not implemented | FREE | ⚠️ You register |
| **CORE** | ❌ Not implemented | FREE | ⚠️ You register |
| **ProductHunt** | ❌ Not implemented | FREE | ⚠️ You register |
| **GitLab** | ❌ Not implemented | FREE | ⚠️ You register |
| **Reddit Official** | ❌ Not implemented | FREE | ⚠️ You register |
| **Brave Search** | ❌ Not implemented | FREE tier | ⚠️ You register |
| **You.com** | ❌ Not implemented | FREE tier | ⚠️ You register |
| **GNews Essential** | ⚡ Have free | €49.99/mo | 💰 Upgrade later |
| **Browserbase** | ❌ Not implemented | $20/mo | 💰 Register + pay |
| **RSSHub** | ❌ Not implemented | FREE | 🔧 Self-host |

---

## 💡 RECOMMENDATIONS

### **Highest Value FREE Additions** (I can do in 30 minutes):
1. **HackerNews API** → Tech news/discussions (unlimited)
2. **Dev.to API** → Developer blogs (unlimited)
3. **Jina AI Reader** → Clean web scraping (1M/month)
4. **RSS Feed Client** → 50+ company blogs (unlimited)
5. **GDELT** → Global news events (unlimited)

### **Best FREE Registrations** (Worth 10 minutes of your time):
1. **PubMed** → 35M health papers
2. **CORE** → 240M open access papers
3. **ProductHunt** → Daily product launches
4. **Brave Search** → 2k searches/month

### **Optional Paid** (When you scale):
1. **GNews Essential** → Only if you need >100 news/day
2. **Browserbase** → Only if Apify isn't enough for JS-heavy sites

---

## ✅ NEXT STEPS

**Option A: Let me implement all FREE sources now**
```bash
# I will:
# 1. Add 7 new client classes (Jina, HackerNews, Dev.to, RSS, GDELT, npm, PyPI)
# 2. Update build_clients() to include them
# 3. Test each integration
# 4. Update README.md with new sources
```

**Option B: You register for additional APIs first**
```bash
# You:
# 1. Sign up for PubMed, CORE, ProductHunt, etc.
# 2. Get API keys
# 3. Give me the keys
# I will:
# 4. Add them to .env
# 5. Implement the clients
```

**Which approach do you want?**
1. Start with FREE implementations (I do it now)
2. You register for APIs first, then I implement
3. Both in parallel (I implement free, you register for others)

Let me know and I'll start coding! 🚀
