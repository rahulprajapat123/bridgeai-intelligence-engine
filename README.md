# Research Intelligence Platform

## Daily Intelligence v2

Daily Intelligence is now organized by source category: Academic, Code, News, Blogs, Web, and Social. A run creates a background batch, applies provider-specific budgets and failure isolation, normalizes and deduplicates source records, creates citation-preserving structured summaries, and presents them at Human Checkpoint 1. Reviewers can edit without overwriting AI output, approve/reject individually or in bulk, lock a reviewed snapshot, and export a source-grouped PDF.

Start a run with `POST /api/daily-intelligence/run`, then poll `GET /api/daily-intelligence/batches/{batch_id}`. Review requests accept `X-Reviewer-Id` and `X-Reviewer-Role`; production deployments should connect these headers to their identity proxy. The in-process FastAPI background task and APScheduler reuse the current stack. For horizontally scaled production deployments, replace this seam with Redis plus Celery/ARQ.

Source budgets are configured with `DAILY_SOURCE_BUDGETS_JSON`; never assume the example quotas are current. API keys remain in environment variables. Sources without required credentials are reported as disabled, and source failures do not fail the full batch. General web search uses a primary/fallback chain to avoid paying multiple near-duplicate providers per run.

See [Daily Intelligence API](DAILY_INTELLIGENCE_API.md) and [migration notes](MIGRATION_NOTES.md).

Domain-aware multi-source ingestion and recommendation system for BridgeAI-style research intelligence. It ingests academic, web, news, code, and tooling sources; normalizes them into claim-level evidence; scores credibility; retrieves with hybrid semantic/lexical ranking; and returns schema-validated recommendations with citations.

## What is implemented

- FastAPI backend with health, stats, brief analysis, ingestion, claim search, recommendation, feedback, source health, and ingestion history endpoints.
- Static internal UI at `/` for the main workflows.
- Strict project context intake. Missing required fields return `insufficient_evidence`.
- Domain classification before retrieval, including Partner Programs and Competitive Intelligence routing so business briefs do not default to AI/RAG.
- Structured brief extraction for deliverables, dependencies, risks, inputs, outputs, timeline, and constraints.
- Source clients for arXiv, Semantic Scholar, OpenAlex, Papers with Code, CORE, Hugging Face, GitHub, NewsAPI, GNews, Guardian, NYTimes, Hacker News, GDELT, Product Hunt, Dev.to, RSS Feeds, Towards Data Science, KDnuggets, Import AI, Serper, Exa, Tavily, Jina AI, You.com, Firecrawl, npm, PyPI, and Apify scrapers (39+ total sources).
- Claim extraction with optional OpenAI JSON extraction and deterministic fallback.
- Credibility scoring using the required 100-point framework: source authority, evidence strength, transparency, recency, and external validation.
- Local hash embeddings by default, optional OpenAI embeddings when configured.
- SQLAlchemy persistence for SQLite locally or Postgres/Neon in production.
- Feedback logging and background scheduler hooks.

## Usage Workflow

### Step 1: Upload Project Brief

Use the UI `Brief` tab or `POST /api/brief/upload` to upload a project brief in PDF, TXT, MD, or DOCX format. The system extracts text, classifies domain/intent, extracts technologies, constraints, deliverables, dependencies, risks, and search terms.

### Step 2: Fetch Sources

Use the UI `Ingest` tab, `POST /api/ingest`, or the `Workflow` tab with `Fetch sources before analysis` enabled. Scheduled fetching is available when `ENABLE_BACKGROUND_SCHEDULER=true`:

- Research sources run at `RESEARCH_FETCH_HOUR=2`
- Developer sources run at `DEVELOPER_FETCH_HOUR=3`

Sources are fetched concurrently from configured providers. API-key-backed providers stay disabled until their keys are present in `.env`.

### Step 3: Analyze Brief

Use the UI `Workflow` tab or `POST /api/workflow/analyze`. The system:

- Searches the fetched evidence store for relevant documents and claims
- Scores evidence with the multi-factor credibility algorithm
- Generates ranked technology recommendations and implementation guidance
- Returns citations, source links, and supporting evidence

The lower-level `POST /api/recommend` endpoint remains available for strict RAG architecture recommendations.

### Step 4: Review Recommendations

Workflow recommendations include:

- Technology name and category
- Relevance score from `0` to `1`
- Supporting evidence with citations
- Source links for papers, articles, and repositories
- Implementation guidance

### Step 5: Daily Intelligence

Use the UI `Ops` tab or `POST /api/daily-intelligence` to generate a daily report with:

- Latest research papers
- Trending repositories
- Tech news summaries
- Recommended reading based on uploaded briefs

To send email reports, set `RESEND_API_KEY`, `EMAIL_FROM`, `DAILY_EMAIL_TO`, `ENABLE_BACKGROUND_SCHEDULER=true`, and `ENABLE_DAILY_EMAIL=true` in `.env`.

## Setup

```powershell
cd C:\Users\praja\Documents\Codex\2026-06-22\multi-source-data-ingestion-api-keys\outputs\research-intelligence-platform
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
Copy-Item .env.example .env
```

Fill `.env` with your real keys. The generated source does not hardcode secrets.

Initialize tables:

```powershell
research-intel init-db
```

Run the app:

```powershell
python -m research_intel.run_server --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`.

If you use the Desktop copy requested for local work:

```powershell
cd $env:USERPROFILE\Desktop\intelligence_engine
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
research-intel init-db
python -m research_intel.run_server --host 127.0.0.1 --port 8010
```

Then open `http://127.0.0.1:8010`.

## Required Project Context

Recommendations require all of:

- `problem_type`: `QA`, `search`, `summarization`, `agentic`, `classification`
- `data_modality`: `PDFs`, `tickets`, `logs`, `code`, `mixed`, `structured`, `unstructured`
- `corpus_scale`
- `latency_constraint`
- `accuracy_cost_tradeoff`: `accuracy_first`, `balanced`, `cost_first`
- `deployment_env`: `GCP`, `AWS`, `Azure`, `on-prem`, `hybrid`, `edge`, `cloud`
- optional `domain`

If the evidence store has no sufficiently credible matching claims, the system returns `insufficient_evidence` instead of fabricating a recommendation.

## API Examples

Analyze a brief:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/brief/analyze `
  -Method POST `
  -ContentType "application/json" `
  -Body (@{ text = "Intel Partner Program competitive benchmark with Microsoft, Nvidia, AMD, MDF, co-marketing, deal registration, BrightEdge, Sprinklr, Adbeat, executive report and PPT." } | ConvertTo-Json)
```

Upload a brief:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/brief/upload `
  -Method POST `
  -Form @{ file = Get-Item .\brief.docx }
```

Run the full workflow:

```json
{
  "brief_id": "brief id from upload",
  "auto_fetch": true,
  "max_per_source": 5,
  "top_k": 8
}
```

Generate daily intelligence:

```json
{
  "send_email": false,
  "max_items": 10
}
```

Run ingestion:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/ingest `
  -Method POST `
  -ContentType "application/json" `
  -Body (@{ topic = "retrieval augmented generation hybrid search reranking"; domain = "AI/ML"; max_per_source = 10 } | ConvertTo-Json)
```

Generate a recommendation:

```json
{
  "project_context": {
    "problem_type": "QA",
    "data_modality": "PDFs",
    "corpus_scale": "50K documents",
    "latency_constraint": "3-5s",
    "accuracy_cost_tradeoff": "accuracy_first",
    "deployment_env": "GCP",
    "domain": "legal"
  },
  "top_k": 12,
  "min_credibility": 60
}
```

## CLI

```powershell
research-intel analyze-brief .\brief.txt
research-intel ingest "retrieval augmented generation hybrid search" --domain "AI/ML" --max-per-source 10
research-intel recommend .\context.json
```

## Tests

```powershell
pytest
```

The tests cover the domain routing regression from the Intel Partner Program review, structured extraction, credibility scoring, strict context handling, retrieval, and recommendation contract behavior.

## Deployment Notes

- For local development, SQLite is enough.
- For Neon/Postgres, set `DATABASE_CONNECTION_STRING` in `.env`; `postgresql://` is automatically adapted to SQLAlchemy's psycopg driver.
- For GCP, deploy with Cloud Run and invoke `/api/ingest` from Cloud Scheduler, or enable the built-in scheduler with `ENABLE_BACKGROUND_SCHEDULER=true`.
- Use the source health endpoint and query logs to monitor ingestion failures, low credibility distributions, latency, and `insufficient_evidence` rates.
