# Content Source Mapping Guide
## Which Methods & Sources for Which Content Types

---

## 🌐 1. INTERNET (General Web Content)

### **Current Tools (What You Have)**

#### **Primary: Firecrawl** ⭐ BEST
- **Use For**: Converting any webpage to clean markdown
- **Strengths**: JavaScript rendering, clean output, structured data
- **Cost**: $79/month (100k pages)
- **API**: `/v1/scrape` endpoint
```python
# Example
firecrawl.scrape(url="https://example.com", formats=["markdown"])
```

#### **Secondary: Apify Web Scraper**
- **Use For**: Complex multi-page scraping, JavaScript-heavy sites
- **Strengths**: Playwright-based, handles SPAs
- **Cost**: Pay-per-compute
- **Best For**: Bulk scraping, crawling entire sites

#### **Fallback: Direct HTTP + BeautifulSoup**
- **Use For**: Simple static pages
- **Strengths**: Free, fast, no API limits
- **When**: Firecrawl not needed for simple HTML

### **Additional Tools to Consider**

#### **Jina AI Reader API** 🆕 RECOMMENDED
- **FREE**: 1M requests/month
- **Use For**: Convert any URL to LLM-friendly text
- **API**: `https://r.jina.ai/{url}`
- **Strengths**: Zero config, instant markdown
```bash
curl https://r.jina.ai/https://example.com
```

#### **ScrapingBee**
- **Cost**: $49/month (100k credits)
- **Use For**: When you need proxies + JS rendering
- **Strengths**: Handles rate limits, rotating proxies

#### **Bright Data (formerly Luminati)**
- **Cost**: Pay-per-GB (starts $500/month)
- **Use For**: Enterprise-scale scraping
- **Strengths**: Best proxies, legal compliance

#### **Puppeteer/Playwright (Self-hosted)**
- **Cost**: FREE (your infra)
- **Use For**: Full control over browser automation
- **Strengths**: Free, customizable

---

## 💻 2. GIT REPOSITORIES

### **Current Tools (What You Have)**

#### **Primary: GitHub API** ⭐ ALREADY WORKING
- **Use For**: Searching repos, getting README, stars, activity
- **Limits**: 5,000 requests/hour (authenticated)
- **Endpoints**:
  - `/search/repositories` - Find repos
  - `/repos/{owner}/{repo}` - Get repo details
  - `/repos/{owner}/{repo}/readme` - Get README

```python
# Already in your codebase!
headers = {"Authorization": f"Bearer {github_token}"}
response = requests.get(
    f"https://api.github.com/repos/{owner}/{repo}/readme",
    headers=headers
)
```

### **Additional Sources to Add**

#### **GitLab API** 🆕
- **FREE**: Unlimited public repo access
- **Use For**: GitLab-hosted projects (alternative to GitHub)
- **API**: `https://gitlab.com/api/v4/projects`
- **Search**: `/search?scope=projects&search=machine+learning`

#### **Bitbucket API** 🆕
- **FREE**: 1,000 requests/hour
- **Use For**: Bitbucket-hosted repos
- **API**: `https://api.bitbucket.org/2.0/repositories`

#### **SourceForge API** 🆕
- **FREE**: Public API
- **Use For**: Legacy/older open-source projects
- **API**: `https://sourceforge.net/rest/`

#### **Code Search Engines**

##### **Sourcegraph API** 🆕 POWERFUL
- **FREE**: Limited searches
- **Use For**: Code search across multiple repos
- **Strengths**: Regex search, symbol search
- **API**: `https://sourcegraph.com/.api/search/stream`

##### **grep.app** 🆕
- **FREE**: Web interface (can scrape)
- **Use For**: Search 500k+ repos instantly
- **URL**: `https://grep.app/search?q={query}`

##### **GitHub Code Search** 🆕
- **FREE**: Via GitHub API
- **Use For**: Search code within GitHub
- **Endpoint**: `/search/code?q={query}`

#### **Package Registries**

##### **npm API**
- **FREE**: Unlimited
- **Use For**: JavaScript packages, documentation
- **API**: `https://registry.npmjs.org/{package}`

##### **PyPI API**
- **FREE**: Unlimited
- **Use For**: Python packages
- **API**: `https://pypi.org/pypi/{package}/json`

##### **crates.io API** (Rust)
- **FREE**: Unlimited
- **API**: `https://crates.io/api/v1/crates/{crate}`

---

## 📚 3. RESEARCH PAPERS

### **Current Tools (What You Have)** ⭐ EXCELLENT COVERAGE

#### **Primary: OpenAlex** ⭐ UNLIMITED FREE
- **Use For**: Comprehensive paper search
- **Coverage**: 250M+ works
- **Strengths**: Unlimited, fast, well-structured
- **API**: `https://api.openalex.org/works`

#### **Secondary: Semantic Scholar**
- **Use For**: CS/AI papers with citations
- **Limits**: 1 RPS (can request more)
- **Strengths**: Citation graph, paper recommendations
- **API**: `https://api.semanticscholar.org/graph/v1`

#### **Tertiary: arXiv API**
- **Use For**: Pre-prints, latest research
- **Strengths**: FREE, unlimited, daily updates
- **API**: `http://export.arxiv.org/api/query`

### **Additional Sources to Add**

#### **PubMed/PubMed Central** 🆕 RECOMMENDED
- **FREE**: Unlimited access
- **Use For**: Biomedical/health research papers
- **Coverage**: 35M+ citations
- **API**: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/`
```python
# Example
url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
params = {"db": "pubmed", "term": "machine learning", "retmode": "json"}
```

#### **CORE (COnnecting REpositories)** 🆕
- **FREE**: 10k requests/day
- **Use For**: Open access papers from 10k+ repositories
- **Coverage**: 240M+ papers
- **API**: `https://api.core.ac.uk/v3`

#### **CrossRef API** 🆕
- **FREE**: Unlimited
- **Use For**: DOI resolution, metadata
- **Coverage**: 150M+ works
- **API**: `https://api.crossref.org/works`

#### **Europe PMC** 🆕
- **FREE**: Unlimited
- **Use For**: Life sciences papers
- **API**: `https://www.ebi.ac.uk/europepmc/webservices/rest/search`

#### **DBLP (Computer Science)** 🆕
- **FREE**: Unlimited
- **Use For**: CS conference/journal papers
- **API**: `https://dblp.org/search/publ/api`

#### **IEEE Xplore API** 🆕
- **Cost**: Requires institutional access or purchase
- **Use For**: IEEE conference papers
- **Coverage**: 5M+ documents

#### **ACM Digital Library API** 🆕
- **Cost**: Requires ACM membership
- **Use For**: ACM publications

#### **Papers with Code API** 🆕 RECOMMENDED
- **FREE**: Open source
- **Use For**: ML papers with code implementations
- **API**: `https://paperswithcode.com/api/v1/papers/`
- **Strengths**: Links papers to GitHub repos

#### **Unpaywall API** 🆕
- **FREE**: 100k requests/day
- **Use For**: Find free/legal versions of paywalled papers
- **API**: `https://api.unpaywall.org/v2/{doi}`

---

## 📰 4. NEWS

### **Current Tools (What You Have)**

#### **Primary: Guardian API** ⭐ BEST FREE
- **FREE**: 500 requests/day (15k/month)
- **Use For**: Quality journalism, UK perspective
- **Strengths**: Well-structured, reliable

#### **Secondary: NY Times API**
- **FREE**: 500 requests/day (15k/month)
- **Use For**: US news, in-depth reporting
- **Strengths**: High quality, searchable archives

#### **Tertiary: NewsAPI**
- **FREE**: 100 requests/day (limited)
- **Use For**: Multi-source aggregation
- **Paid**: $449/month for real-time

#### **Quaternary: GNews**
- **FREE**: 100 requests/day (limited)
- **Paid**: €49.99/month for real-time

### **Additional Sources to Add**

#### **RSS Feeds** 🆕 HIGHLY RECOMMENDED (FREE)

##### **Tech News RSS**
```python
feeds = [
    "https://techcrunch.com/feed/",           # TechCrunch
    "https://www.theverge.com/rss/index.xml", # The Verge
    "https://www.wired.com/feed/rss",         # WIRED
    "https://feeds.arstechnica.com/arstechnica/index", # Ars Technica
    "https://www.artificialintelligence-news.com/feed/", # AI News
    "https://venturebeat.com/feed/",          # VentureBeat
    "https://www.technologyreview.com/feed/", # MIT Tech Review
]
```

##### **Business/Startup RSS**
```python
feeds = [
    "https://feeds.feedburner.com/entrepreneur/latest", # Entrepreneur
    "https://www.businessinsider.com/rss",   # Business Insider
    "https://fortune.com/feed/",             # Fortune
    "https://www.forbes.com/startups/feed/", # Forbes Startups
]
```

##### **Python Library**: `feedparser`
```python
import feedparser
feed = feedparser.parse("https://techcrunch.com/feed/")
for entry in feed.entries[:5]:
    print(entry.title, entry.link)
```

#### **News Aggregator APIs**

##### **Bing News Search API** 🆕
- **Cost**: $3/1k queries (first 1k free/month)
- **Use For**: Multi-language news search
- **API**: Azure Cognitive Services

##### **Currents API** 🆕
- **FREE**: 600 requests/day
- **Use For**: News from 7,400+ sources
- **API**: `https://api.currentsapi.services/v1/search`

##### **News API.ai** 🆕
- **FREE**: 50 requests/day
- **Paid**: $9/month (500/day)
- **API**: `https://newsapi.ai/api/v1/article/getArticles`

##### **MediaStack** 🆕
- **FREE**: 500 requests/month
- **Paid**: $9/month (1,000/month)
- **API**: `http://api.mediastack.com/v1/news`

#### **Alternative News Sources**

##### **HackerNews (YC) API** 🆕 EXCELLENT FOR TECH
- **FREE**: Unlimited
- **Use For**: Tech community discussions
- **API**: `https://hacker-news.firebaseio.com/v0/topstories.json`
```python
# Get top stories
import requests
top_ids = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json").json()[:10]
for story_id in top_ids:
    story = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json").json()
    print(story.get('title'), story.get('url'))
```

##### **Reddit API** 🆕
- **FREE**: 100 requests/minute
- **Use For**: Subreddit discussions (r/MachineLearning, r/technology)
- **API**: `https://www.reddit.com/r/MachineLearning.json`

##### **ProductHunt API** 🆕
- **FREE**: GraphQL API
- **Use For**: Daily tech product launches
- **API**: `https://api.producthunt.com/v2/api/graphql`

---

## 📝 5. BLOGS

### **Current Tools (What You Have)**

#### **Primary: Exa.ai** ⭐ BEST FOR BLOGS
- **FREE**: 20k requests/month
- **Use For**: Semantic search for high-quality blog posts
- **Strengths**: Finds relevant content by meaning, not just keywords
- **API**: `/search` endpoint

```python
# Find AI/ML blogs
exa.search(
    query="latest transformer architecture improvements",
    category="blog",
    num_results=10
)
```

#### **Secondary: Serper/SerpAPI**
- **Use For**: Google search for blogs
- **Cost**: $0.50-1.00/1k queries

#### **Tertiary: Firecrawl**
- **Use For**: Extracting blog content once you have URLs
- **Converts**: HTML → Clean Markdown

### **Additional Sources to Add**

#### **Blog Aggregator APIs**

##### **Dev.to API** 🆕 EXCELLENT
- **FREE**: Unlimited
- **Use For**: Developer blogs, tutorials
- **Coverage**: 1M+ developers
- **API**: `https://dev.to/api/articles`
```python
# Get top AI articles
response = requests.get("https://dev.to/api/articles?tag=machinelearning&top=7")
```

##### **Medium API** 🆕
- **Limited**: RSS only (no official API)
- **Use For**: Medium publications
- **RSS**: `https://medium.com/feed/@{username}`
- **Tags**: `https://medium.com/feed/tag/{tag}`

##### **Hashnode API** 🆕
- **FREE**: GraphQL API
- **Use For**: Developer blogs
- **API**: `https://gql.hashnode.com`

##### **Substack** 🆕
- **FREE**: RSS feeds per publication
- **Use For**: Newsletter-style blogs
- **RSS**: `https://{substack}.substack.com/feed`

#### **Technology Company Blogs (RSS)**

##### **AI/ML Company Blogs**
```python
company_blogs = {
    "OpenAI": "https://openai.com/blog/rss/",
    "Anthropic": "https://www.anthropic.com/news/rss",
    "Google AI": "https://blog.google/technology/ai/rss/",
    "Meta AI": "https://ai.meta.com/blog/rss/",
    "Microsoft Research": "https://www.microsoft.com/en-us/research/feed/",
    "DeepMind": "https://deepmind.google/blog/rss.xml",
    "Hugging Face": "https://huggingface.co/blog/feed.xml",
    "Scale AI": "https://scale.com/blog/rss.xml",
}
```

##### **Developer Tool Blogs**
```python
tool_blogs = {
    "GitHub Blog": "https://github.blog/feed/",
    "GitLab Blog": "https://about.gitlab.com/atom.xml",
    "Vercel": "https://vercel.com/blog/rss.xml",
    "Netlify": "https://www.netlify.com/blog/index.xml",
    "AWS": "https://aws.amazon.com/blogs/aws/feed/",
}
```

#### **Blog Search Engines**

##### **Algolia DocSearch** 🆕
- **FREE**: For documentation sites
- **Use For**: Searching technical documentation
- **API**: Via Algolia

##### **Google Programmable Search Engine (PSE)** 🆕
- **FREE**: 100 queries/day
- **Paid**: $5/1k queries
- **Use For**: Custom blog search engine
- **API**: `https://www.googleapis.com/customsearch/v1`

---

## 🎯 QUICK REFERENCE MATRIX

| Content Type | Primary Method | Best Tool(s) | Cost | Update Frequency |
|--------------|----------------|--------------|------|------------------|
| **General Web** | Scraping | Firecrawl, Jina AI | $0-79/mo | On-demand |
| **Git Repos** | API | GitHub, GitLab | FREE | Real-time |
| **Research Papers** | API | OpenAlex, Semantic Scholar | FREE | Daily |
| **News** | API + RSS | Guardian, NYT, RSS | FREE | Hourly |
| **Blogs** | API + RSS | Exa.ai, Dev.to, RSS | FREE-$210/mo | Daily |

---

## 🚀 IMPLEMENTATION PRIORITY

### **Phase 1: FREE High-Quality Sources** (Implement First)
```python
priority_sources = {
    "papers": ["OpenAlex", "arXiv", "Papers with Code"],
    "news": ["Guardian API", "NY Times API", "HackerNews API", "RSS Feeds"],
    "code": ["GitHub API", "npm API", "PyPI API"],
    "blogs": ["Dev.to API", "Company RSS Feeds", "Medium RSS"],
    "web": ["Jina AI Reader", "Direct HTTP"],
}
```

### **Phase 2: Enhanced Coverage** (Add When Scaling)
```python
enhanced_sources = {
    "papers": ["CORE", "CrossRef", "PubMed"],
    "news": ["ProductHunt API", "Reddit API"],
    "code": ["GitLab API", "Sourcegraph"],
    "blogs": ["Hashnode", "Substack RSS"],
    "web": ["Firecrawl Paid"],
}
```

### **Phase 3: Premium Tools** (For Production Scale)
```python
premium_sources = {
    "web": ["Exa.ai Paid", "Browserbase"],
    "news": ["GNews Essential", "NewsAPI Business"],
    "intelligence": ["Crunchbase", "BuiltWith"],
}
```

---

## 💻 CODE EXAMPLES

### **1. General Web Scraping**
```python
# Option A: Jina AI (Simplest)
def scrape_with_jina(url):
    response = requests.get(f"https://r.jina.ai/{url}")
    return response.text  # Clean markdown

# Option B: Firecrawl (Most Powerful)
def scrape_with_firecrawl(url):
    response = requests.post(
        "https://api.firecrawl.dev/v1/scrape",
        headers={"Authorization": f"Bearer {FIRECRAWL_KEY}"},
        json={"url": url, "formats": ["markdown"]}
    )
    return response.json()["data"]["markdown"]

# Option C: Direct (Fastest, Limited)
def scrape_direct(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    return soup.get_text()
```

### **2. Git Repo Discovery**
```python
# GitHub search
def search_github_repos(query):
    response = requests.get(
        "https://api.github.com/search/repositories",
        params={"q": query, "sort": "stars"},
        headers={"Authorization": f"Bearer {GITHUB_TOKEN}"}
    )
    return response.json()["items"]

# GitLab search
def search_gitlab_repos(query):
    response = requests.get(
        "https://gitlab.com/api/v4/projects",
        params={"search": query, "order_by": "star_count"}
    )
    return response.json()
```

### **3. Research Paper Search**
```python
# OpenAlex (Best)
def search_papers_openalex(query):
    response = requests.get(
        "https://api.openalex.org/works",
        params={"search": query, "per_page": 10}
    )
    return response.json()["results"]

# Papers with Code (With implementations)
def search_papers_with_code(query):
    response = requests.get(
        f"https://paperswithcode.com/api/v1/papers/",
        params={"q": query}
    )
    return response.json()["results"]
```

### **4. News Aggregation**
```python
# HackerNews
def get_hackernews_top():
    top_ids = requests.get(
        "https://hacker-news.firebaseio.com/v0/topstories.json"
    ).json()[:30]
    
    stories = []
    for story_id in top_ids:
        story = requests.get(
            f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
        ).json()
        stories.append(story)
    return stories

# RSS Feed Parser
import feedparser
def parse_rss_feed(feed_url):
    feed = feedparser.parse(feed_url)
    return [{
        "title": entry.title,
        "link": entry.link,
        "published": entry.published,
        "summary": entry.summary
    } for entry in feed.entries]
```

### **5. Blog Discovery**
```python
# Dev.to API
def get_devto_articles(tag="machinelearning"):
    response = requests.get(
        "https://dev.to/api/articles",
        params={"tag": tag, "top": 7}
    )
    return response.json()

# Exa.ai (Semantic search)
def search_blogs_exa(query):
    response = requests.post(
        "https://api.exa.ai/search",
        headers={"x-api-key": EXA_KEY},
        json={"query": query, "category": "blog", "num_results": 10}
    )
    return response.json()["results"]
```

---

## 📋 COMPLETE SOURCE CHECKLIST

### ✅ **Already Implemented (Your Current Sources)**
- [x] OpenAlex (papers)
- [x] Semantic Scholar (papers)
- [x] arXiv (papers)
- [x] GitHub (code)
- [x] Guardian (news)
- [x] NY Times (news)
- [x] NewsAPI (news)
- [x] GNews (news)
- [x] Exa.ai (web/blogs)
- [x] Serper (web)
- [x] SerpAPI (web)
- [x] Tavily (web)
- [x] Firecrawl (web scraping)
- [x] Apify (web scraping)

### 🆕 **High Priority to Add (FREE)**
- [ ] Jina AI Reader (web scraping - FREE)
- [ ] HackerNews API (tech news - FREE)
- [ ] ProductHunt API (tech products - FREE)
- [ ] Dev.to API (developer blogs - FREE)
- [ ] Papers with Code API (ML papers - FREE)
- [ ] RSS Feed Parser (blogs/news - FREE)
- [ ] Reddit API (discussions - FREE)
- [ ] GitLab API (code repos - FREE)
- [ ] npm/PyPI APIs (package info - FREE)
- [ ] CORE API (papers - FREE 10k/day)
- [ ] CrossRef API (paper metadata - FREE)
- [ ] PubMed API (health papers - FREE)

### 💰 **Consider Adding (PAID)**
- [ ] Crunchbase (company intelligence - $49/mo)
- [ ] BuiltWith (tech stack intel - $295/mo)
- [ ] Apollo.io (sales intelligence - $49/mo)
- [ ] ScrapingBee (advanced scraping - $49/mo)

---

## 🎓 BEST PRACTICES

### **For Each Content Type:**

#### **Web Scraping**
1. Start with Jina AI (free, fast)
2. Use Firecrawl for complex sites
3. Fallback to direct HTTP for simple pages
4. Respect robots.txt
5. Add rate limiting

#### **Git Repos**
1. Use GitHub API for discovery
2. Cache repository data (changes infrequently)
3. Get README + stars + last update
4. Track trending repositories
5. Monitor new releases

#### **Research Papers**
1. Primary: OpenAlex (unlimited, comprehensive)
2. Secondary: Semantic Scholar (citations)
3. Tertiary: arXiv (latest pre-prints)
4. Use Papers with Code for implementations
5. Cache paper metadata

#### **News**
1. Use RSS feeds (free, reliable)
2. Guardian + NYT for quality
3. HackerNews for tech community
4. ProductHunt for new products
5. Update hourly

#### **Blogs**
1. Aggregate company RSS feeds
2. Use Dev.to API for tutorials
3. Exa.ai for semantic discovery
4. Monitor Substack newsletters
5. Update daily

---

## 🔗 Quick Implementation Template

```python
# Add to your ingestion/clients.py

class JinaAIClient(HttpSourceClient):
    name = "Jina AI Reader"
    route_name = "jina"
    source_type = "web"
    
    async def fetch(self, url: str) -> FetchResult:
        response = await self.http.get(f"https://r.jina.ai/{url}")
        return FetchResult(
            source_name=self.name,
            documents=[RawDocument(
                title=url,
                source_url=url,
                text=response.text,
                source_type="web",
                source_name=self.name
            )]
        )

class DevToClient(HttpSourceClient):
    name = "Dev.to"
    route_name = "devto"
    source_type = "blog"
    
    async def fetch(self, query: str, *, max_results: int) -> FetchResult:
        response = await self.http.get(
            "https://dev.to/api/articles",
            params={"tag": query, "top": 7, "per_page": max_results}
        )
        articles = response.json()
        docs = [
            RawDocument(
                title=article["title"],
                source_url=article["url"],
                text=article.get("body_markdown", ""),
                source_type="blog",
                source_name=self.name,
                publication_date=article["published_at"][:10]
            )
            for article in articles[:max_results]
        ]
        return FetchResult(source_name=self.name, documents=docs)
```

This guide should give you a complete roadmap for each content type! 🚀
