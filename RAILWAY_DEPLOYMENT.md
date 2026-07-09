# Railway Deployment Guide

## Quick Deploy to Railway

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/new?template=https://github.com/rahulprajapat123/bridgeai-intelligence-engine)

## Manual Deployment Steps

### 1. Create Railway Project

1. Go to [Railway.app](https://railway.app)
2. Sign in with GitHub
3. Click "New Project"
4. Select "Deploy from GitHub repo"
5. Choose `bridgeai-intelligence-engine`

### 2. Configure Environment Variables

Add all these environment variables in Railway dashboard:

```bash
# Required API Keys
OPENAI_API_KEY=your_openai_api_key_here
APIFY_API_TOKEN=your_apify_token_here
SERPER_API_KEY=your_serper_api_key_here

# Academic Sources (Optional but Recommended)
SEMANTIC_SCHOLAR_API_KEY=your_semantic_scholar_api_key
OPENALEX_CONTACT_EMAIL=your-email@example.com

# News Sources (Optional)
GNEWS_API_KEY=your_gnews_api_key
NEWSAPI_KEY=your_newsapi_key
GUARDIAN_API_KEY=your_guardian_api_key
NYTIMES_API_KEY=your_nytimes_api_key

# Additional Sources (Optional)
HUGGINGFACE_TOKEN=your_huggingface_token
GITHUB_TOKEN=your_github_token
EXA_API_KEY=your_exa_api_key
TAVILY_API_KEY=your_tavily_api_key
SERPAPI_API_KEY=your_serpapi_api_key
FIRECRAWL_API_KEY=your_firecrawl_api_key

# Database (Railway will auto-configure PostgreSQL)
DATABASE_CONNECTION_STRING=${{Postgres.DATABASE_URL}}

# Email Configuration
EMAIL_PROVIDER=resend
EMAIL_FROM=Research Intelligence <onboarding@resend.dev>
RESEND_API_KEY=your_resend_api_key

# Apify Settings
APIFY_SCRAPER_TIMEOUT_SECS=600
APIFY_MAX_PAGES_PER_SCRAPE=5
APIFY_ENABLE_JAVASCRIPT=true

# Research Settings
MAX_PAPERS_PER_SOURCE=10
MAX_NEWS_ARTICLES_PER_SOURCE=50
MAX_GITHUB_REPOS=10
MIN_PUBLICATION_YEAR=2022
NEWS_LOOKBACK_DAYS=30
```

### 3. Add PostgreSQL Database

1. In Railway dashboard, click "New"
2. Select "Database" → "PostgreSQL"
3. Railway will automatically set `DATABASE_URL`
4. Update your `DATABASE_CONNECTION_STRING` to: `${{Postgres.DATABASE_URL}}`

### 4. Deploy

Railway will automatically:
- Detect Python project
- Install dependencies from `pyproject.toml`
- Run the start command from `Procfile`
- Assign a public URL

### 5. Access Your Application

Once deployed, Railway provides a public URL like:
```
https://your-app.railway.app
```

## Architecture

- **Framework**: FastAPI + Uvicorn
- **Database**: PostgreSQL (auto-provisioned by Railway)
- **Package Structure**: Source layout (`src/research_intel/`) with setuptools
- **Build System**: Nixpacks with automatic package installation
- **Data Sources**: 26 integrated sources (ArXiv, Semantic Scholar, OpenAlex, Papers with Code, GitHub, HuggingFace, NewsAPI, Apify, etc.)
- **AI Engine**: OpenAI GPT-4 for analysis

## Features

- ✅ Multi-source research intelligence aggregation
- ✅ AI-powered analysis and recommendations
- ✅ Credibility scoring and source validation
- ✅ Daily intelligence reports
- ✅ Email notifications (Resend)
- ✅ Web scraping with Apify (Twitter, Reddit, YouTube, News)
- ✅ RESTful API with interactive docs

## Monitoring

Check Railway dashboard for:
- Build logs
- Runtime logs
- Resource usage
- Deployment status

## Troubleshooting

### ModuleNotFoundError: No module named 'research_intel'
This error occurs if the package isn't installed properly. **Fixed in latest version** with:
- Added `[build-system]` to `pyproject.toml`
- Created `nixpacks.toml` for proper Railway installation
- Package is now installed with `pip install -e .` during build

If you still see this error:
1. Ensure you're using the latest commit from GitHub
2. Trigger a rebuild on Railway (Settings → Redeploy)
3. Check build logs for installation errors

### Build Fails
- Check Railway build logs
- Verify all dependencies in `pyproject.toml`

### Runtime Errors
- Check environment variables are set correctly
- Verify API keys are valid
- Check database connection string

### Timeout Issues
- Increase `APIFY_SCRAPER_TIMEOUT_SECS` if needed
- Check Railway resource limits

## Support

- GitHub: https://github.com/rahulprajapat123/bridgeai-intelligence-engine
- Issues: https://github.com/rahulprajapat123/bridgeai-intelligence-engine/issues
