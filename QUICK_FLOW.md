# Quick Logic Flow Reference

## 🔄 **End-to-End Flow (Simplified)**

```
USER UPLOADS BRIEF (PDF/DOCX/TXT)
           ↓
    FILE PARSER extracts text
           ↓
    BRIEF UNDERSTANDING SERVICE
    • Domain Classification (AI/ML, Developer, Business, etc.)
    • Keyword Extraction
    • Query Decomposition
    • Route Selection (which sources to use)
           ↓
    INGESTION ORCHESTRATOR (if auto_fetch=true)
    ┌────────────────────────────────────────┐
    │ Parallel Fetch from Multiple Sources:  │
    │ • Semantic Scholar (academic papers)   │
    │ • OpenAlex (research papers)           │
    │ • GitHub (repositories + README)       │
    │ • News APIs (articles)                 │
    │ • Exa.ai (neural web search)           │
    │ • Serper (Google search)               │
    └────────────────────────────────────────┘
           ↓
    FOR EACH DOCUMENT:
    ┌────────────────────────────────────────┐
    │ 1. CLAIM EXTRACTOR (GPT-4)            │
    │    Extracts structured claims with:    │
    │    - Claim text                        │
    │    - Evidence summary                  │
    │    - Evidence type (experiment, etc.)  │
    │    - Metrics, conditions, limitations  │
    │                                        │
    │ 2. CREDIBILITY SCORER (Heuristic)     │
    │    Scores based on:                    │
    │    - Citation count                    │
    │    - Source authority                  │
    │    - Metadata quality                  │
    │    - Recency                          │
    │                                        │
    │ 3. EMBEDDING SERVICE (OpenAI)         │
    │    Generates 1536-dim vectors         │
    │    for semantic search                │
    └────────────────────────────────────────┘
           ↓
    SAVE TO DATABASE
    • ResearchItem table (papers/docs)
    • Claims table (with embeddings)
           ↓
    RETRIEVAL SERVICE
    ┌────────────────────────────────────────┐
    │ Hybrid Search:                         │
    │ • Semantic: Cosine similarity (38%)    │
    │ • Lexical: Token overlap (24%)         │
    │ • Credibility: Score weight (16%)      │
    │ • Domain: Tag matching (12%)           │
    │ • Recency: Publication date (5%)       │
    │ • Rerank: Heuristics (5%)              │
    └────────────────────────────────────────┘
           ↓
    WORKFLOW SERVICE
    • Aggregates evidence
    • Generates technology recommendations
    • Creates structured citations
           ↓
    RESPONSE TO USER
    • Brief analysis
    • Evidence citations (with credibility scores)
    • Technology recommendations
    • Implementation guidance
```

---

## 📦 **Service Initialization (startup)**

```python
main.py (lifespan)
    ↓
config.py (load .env)
    ↓
db.py (init_db → create tables)
    ↓
factory.py (build_services)
    ├─→ DomainClassifier()
    ├─→ BriefUnderstandingService(classifier)
    ├─→ EmbeddingService(settings)  # OpenAI
    ├─→ ClaimExtractor(settings)    # GPT-4
    ├─→ CredibilityScorer()
    ├─→ RetrievalService(embeddings)
    ├─→ IngestionOrchestrator(extractor, scorer, embeddings, classifier)
    ├─→ RecommendationService(retrieval)
    └─→ DailyIntelligenceService()
    ↓
scheduler.py (IntelligenceScheduler)
    ├─→ Research Ingestion (2 AM UTC)
    ├─→ Developer Ingestion (3 AM UTC)
    └─→ Daily Intelligence Email (8 AM UTC)
    ↓
app.state.services = services
app.state.scheduler = scheduler
    ↓
SERVER READY on http://127.0.0.1:8000
```

---

## 🎯 **API Request Patterns**

### **Pattern 1: Simple Brief Analysis**
```
POST /api/brief/analyze
{
  "text": "Build a RAG system for legal documents..."
}
    ↓
BriefUnderstandingService.analyze(text)
    ↓
Response:
{
  "domain": {"domain": "Legal", "confidence": 0.95},
  "intent": "Build retrieval system",
  "keywords": ["rag", "legal", "documents"],
  "query_decomposition": [...],
  "retrieval_routes": ["semantic_scholar", "github"]
}
```

### **Pattern 2: File Upload + Analysis**
```
POST /api/brief/upload
Content-Type: multipart/form-data
file: project_brief.pdf
    ↓
BriefFileParser.parse(filename, content)
    ↓
BriefUnderstandingService.analyze(text)
    ↓
Save UploadedBrief to DB
    ↓
Response:
{
  "brief_id": "034d0590...",
  "analysis": {...}
}
```

### **Pattern 3: Full Workflow (Upload → Fetch → Recommend)**
```
POST /api/workflow/analyze
{
  "brief_id": "034d0590...",
  "auto_fetch": true,
  "max_per_source": 20,
  "top_k": 10
}
    ↓
Load brief from DB
    ↓
BriefUnderstandingService.analyze()
    ↓
IngestionOrchestrator.ingest_topic()  // if auto_fetch
    ├─→ Parallel fetch from sources
    ├─→ Extract claims
    ├─→ Score credibility
    ├─→ Generate embeddings
    └─→ Save to DB
    ↓
RetrievalService.search()
    ├─→ Hybrid ranking
    └─→ Return top-K claims
    ↓
WorkflowService.technology_recommendations()
    ↓
Response:
{
  "brief_id": "034d0590...",
  "analysis": {...},
  "fetched_sources": {...},
  "recommendations": [...],
  "citations": [...]
}
```

### **Pattern 4: Direct Recommendation**
```
POST /api/recommend
{
  "project_context": {
    "domain": "AI/ML",
    "objective": "Improve RAG accuracy",
    "stakeholders": ["engineering", "product"],
    "timeline": "Q2 2026"
  },
  "top_k": 12,
  "min_credibility": 60
}
    ↓
Validate project_context
    ↓
Build query from context
    ↓
RetrievalService.search()
    ↓
Filter by min_credibility
    ↓
Build recommendation contract
    ↓
Log to QueryLog
    ↓
Response:
{
  "status": "ok",
  "query_id": "query_abc123...",
  "data": {
    "core": {...},
    "evidence": [...],
    "implementation": {...}
  }
}
```

---

## 🔍 **Key Classes & Their Roles**

| Class | Purpose | Key Methods |
|-------|---------|-------------|
| `BriefUnderstandingService` | Analyzes briefs | `analyze(text)` → BriefAnalysis |
| `DomainClassifier` | Classifies domain | `classify(text)` → domain + confidence |
| `IngestionOrchestrator` | Coordinates data fetch | `ingest_topic(topic, domain)` |
| `ClaimExtractor` | LLM-based extraction | `extract(document)` → List[Claim] |
| `CredibilityScorer` | Scores reliability | `score(document, claims)` → float |
| `EmbeddingService` | Vector generation | `embed(text)` → List[float] |
| `RetrievalService` | Hybrid search | `search(query, domain, top_k)` |
| `RecommendationService` | Generate recs | `recommend(context, top_k)` |
| `WorkflowService` | End-to-end pipeline | `analyze_workflow()` |
| `IntelligenceScheduler` | Background jobs | `start()`, scheduled tasks |

---

## 📊 **Database Tables (Core)**

```
ResearchItem (research papers/docs)
  ├─ research_id (PK)
  ├─ source_url (unique)
  ├─ title, authors, publication_date
  ├─ credibility_score (0-100)
  ├─ domain_tags (JSON array)
  └─ raw_text

Claim (extracted structured claims)
  ├─ claim_id (PK)
  ├─ research_id (FK → ResearchItem)
  ├─ claim_text
  ├─ evidence_summary
  ├─ evidence_type
  ├─ embedding (JSON array, 1536 dims)
  └─ applicability_tags

UploadedBrief (user uploads)
  ├─ brief_id (PK)
  ├─ filename
  ├─ extracted_text
  └─ analysis (JSON)

QueryLog (recommendation history)
  ├─ query_id (PK)
  ├─ project_context (JSON)
  ├─ response (JSON)
  └─ status

IngestionRun (fetch history)
  ├─ run_id (PK)
  ├─ topic, domain
  ├─ documents_seen, documents_inserted
  └─ claims_inserted
```

---

## 🧠 **Intelligence Components**

### **1. Domain Classification**
```
Input: Text
Output: {domain, confidence, keywords}

Domains:
- AI/ML
- Developer Tooling
- Business Intelligence
- Legal
- Partner
- Competitive

Method: Keyword matching + rule-based
```

### **2. Claim Extraction (LLM)**
```
Input: RawDocument
LLM: GPT-4
Prompt: "Extract factual claims with evidence..."
Output: List[ExtractedClaim]

Structure:
{
  "claim_text": "Hybrid search improves recall by 23%",
  "evidence_summary": "Experiment on MS MARCO dataset",
  "evidence_type": "experiment",
  "metrics": ["recall: +23%"],
  "conditions": "On information retrieval tasks",
  "limitations": "Requires BM25 preprocessing"
}
```

### **3. Credibility Scoring (Heuristic)**
```
Factors:
1. Citations (0-40 pts)
   - 100+ citations: 40
   - 50-99: 30
   - 10-49: 20
   - <10: 10

2. Source Authority (0-30 pts)
   - Tier 1 (Nature, Science): 30
   - Tier 2 (IEEE, ACM): 25
   - Tier 3: 20
   - Unknown: 15

3. Metadata Quality (0-15 pts)
4. Recency (0-15 pts)

Total: 0-100
```

### **4. Embedding Generation**
```
Model: OpenAI text-embedding-3-small
Dimensions: 1536
Input: claim_text + evidence_summary + tags
Output: Vector stored in Claims.embedding
```

### **5. Hybrid Retrieval**
```
Query → Query Embedding → Fetch Candidates

For each candidate:
  Semantic = cosine_similarity(query_emb, claim_emb)
  Lexical = token_overlap(query_terms, claim_terms)
  Credibility = claim.research_item.credibility_score / 100
  Domain = tag_overlap(query_domain, claim_tags)
  Recency = age_penalty(publication_date)
  Rerank = heuristic_boost(evidence_type, metrics)
  
  Score = 0.38×Semantic + 0.24×Lexical + 0.16×Credibility
        + 0.12×Domain + 0.05×Recency + 0.05×Rerank

Sort by Score DESC → Return Top-K
```

---

## ⚙️ **Configuration Keys**

```bash
# OpenAI (Required for embeddings + extraction)
OPENAI_API_KEY=sk-proj-...

# Data Sources (At least one required)
SEMANTIC_SCHOLAR_API_KEY=...
GITHUB_TOKEN=...
GNEWS_API_KEY=...
EXA_API_KEY=...
SERPER_API_KEY=...

# Database (Required)
DATABASE_CONNECTION_STRING=postgresql://...

# Optional: Email notifications
RESEND_API_KEY=...
EMAIL_FROM=...

# Ingestion Settings
MAX_PAPERS_PER_SOURCE=50
RESEARCH_FETCH_HOUR=2
DEVELOPER_FETCH_HOUR=3
```

---

## 🚀 **Running the System**

```powershell
# 1. Install dependencies
.\.venv\Scripts\python.exe -m pip install -e .[dev]

# 2. Initialize database
.\.venv\Scripts\research-intel.exe init-db

# 3. Start server
.\.venv\Scripts\python.exe -m research_intel.run_server --reload

# Or use the convenience script:
.\scripts\run_dev.ps1
```

Server: http://127.0.0.1:8000
Docs: http://127.0.0.1:8000/docs
