# API Rate Limits & Pricing Analysis

## 📊 Summary Overview

### ✅ UNLIMITED/FREE TIER APIs (No hard monthly limits)
1. **Semantic Scholar** - Introductory 1 RPS, can request higher limits
2. **OpenAlex** - Truly unlimited and free (polite pool)
3. **GitHub** - 5,000 requests/hour (authenticated)
4. **HuggingFace** - Free tier with reasonable limits
5. **Guardian** - 500 calls/day, 1 call/second (developer key, free for non-commercial)

### ⚠️ LIMITED TIER APIs (Monthly quotas)

#### Academic & Research
- **Semantic Scholar**: 1 RPS base (can request higher limits for free if academic)
- **OpenAlex**: UNLIMITED ✨ (polite pool, truly free)

#### News APIs
- **GNews**: 
  - ❌ FREE: 100 requests/day (3,000/month)
  - 💰 Essential: 1,000/day (~30,000/month) - €49.99/month
  
- **NewsAPI**: 
  - ❌ FREE: 100 requests/day (3,000/month) + 24-hour delay
  - 💰 Business: 250,000/month - $449/month
  - 💰 Advanced: 2M/month - $1,749/month

- **Guardian**: 
  - ✅ FREE (Non-commercial): 500/day, 1/second
  - 💰 Commercial: Custom pricing

- **NY Times**: 
  - ⚠️ FREE: 500/day, 5/minute (~15,000/month)
  - Non-commercial use only

#### Web Search & Scraping
- **Exa.ai**: 
  - ✅ FREE: 20,000 requests/month (generous!)
  - 💰 Search: $7/1k requests
  - 💰 Agent: $0.012-$1.00/run

- **Tavily**: 
  - ✅ FREE: 1,000 credits/month
  - 💰 Pay-as-you-go: $0.008/credit
  - Students get free access

- **Serper**: 
  - ✅ FREE TRIAL: 2,500 queries
  - 💰 Starter: 50k credits - $50 ($1.00/1k)
  - 💰 Standard: 500k - $375 ($0.75/1k)
  - Credits valid 6 months

- **SerpAPI**: 
  - ❌ FREE: 250 searches/month
  - 💰 Starter: 1,000/month - $25
  - 💰 Developer: 5,000/month - $75
  - 💰 Production: 15,000/month - $150

- **Firecrawl**: 
  - ✅ FREE: 1,000 pages/month (1,000 credits)
  - 💰 Hobby: 5,000 pages/month - $15/month
  - 💰 Standard: 100,000 pages/month - $79/month
  - 💰 Growth: 500,000 pages/month - $318/month

- **Apify**: 
  - ⚠️ FREE: $5 usage/month (pay-as-you-go)
  - 💰 Starter: $29 prepaid usage - $29/month
  - 💰 Scale: $199 prepaid usage - $199/month
  - Pay per compute unit (1 CU = 1 GB RAM for 1 hour)

#### AI & Development
- **OpenAI**: 
  - ❌ NO FREE TIER
  - 💰 Pay-per-token pricing
  - GPT-5.6 Sol: $5/1M input, $30/1M output
  - GPT-5.6 Luna: $1/1M input, $6/1M output
  - Unlimited usage but pay-per-use

- **GitHub**: 
  - ✅ FREE: 5,000 requests/hour (authenticated)
  - ✅ GitHub Apps: 15,000 requests/hour (enterprise orgs)
  - Unauthenticated: Only 60/hour

- **HuggingFace**: 
  - ✅ FREE: Basic inference and storage
  - 💰 PRO: $9/month (20× inference credits)
  - Inference Endpoints: Pay per compute hour

#### Email
- **Resend**: 
  - ✅ FREE: 3,000 emails/month (100/day limit)
  - 💰 Pro: 50,000/month - $20/month
  - 💰 Scale: 100,000/month - $90/month
  - Your key is send-only (valid but restricted)

---

## 🎯 Tier Classification

### Tier 1: Truly Unlimited/Generous Free
- ✅ **OpenAlex** - Unlimited, truly free
- ✅ **Exa.ai** - 20,000 requests/month free
- ✅ **GitHub** - 5,000/hour (180,000/day)

### Tier 2: Adequate Free for Development
- ⚠️ **Semantic Scholar** - 1 RPS (can request more)
- ⚠️ **Tavily** - 1,000 credits/month
- ⚠️ **Firecrawl** - 1,000 pages/month
- ⚠️ **Resend** - 3,000 emails/month
- ⚠️ **Guardian** - 500/day (~15,000/month)
- ⚠️ **NY Times** - 500/day (~15,000/month)

### Tier 3: Very Limited Free
- ❌ **GNews** - 100/day (3,000/month)
- ❌ **NewsAPI** - 100/day (3,000/month) + delays
- ❌ **SerpAPI** - 250/month
- ❌ **Apify** - $5 usage credit/month
- ❌ **Serper** - 2,500 one-time trial

### Tier 4: Pay-Only (No meaningful free tier)
- 💰 **OpenAI** - Pay per token
- 💰 **HuggingFace (paid features)** - Pay per compute

---

## 💡 Recommendations

### For Unlimited Research Access
1. **Use OpenAlex** - Truly unlimited academic papers
2. **Use Semantic Scholar** - Request higher rate limit (free for academic use)
3. **Use GitHub API** - 5,000/hour is very generous

### For Web Search
1. **Exa.ai** (20k free) is your best option for volume
2. **Tavily** (1k free) for AI agent search
3. **Serper** requires paid credits after trial

### For News
1. **Guardian** (500/day free) and **NY Times** (500/day free) are best free options
2. **GNews** and **NewsAPI** very limited at 100/day
3. Consider Guardian's free non-commercial tier

### For Web Scraping
1. **Firecrawl** (1,000 pages/month free) - working and available
2. **Apify** has $5/month credit but complex pricing
3. Use document parsing fallbacks when possible

### Cost Management Strategy
- **Development/Testing**: Use free tiers (OpenAlex, Exa, Guardian, NY Times)
- **Production Low Volume**: Exa.ai 20k free + Tavily 1k free covers most needs
- **Production High Volume**: Budget for Exa ($7/1k), Serper ($0.50-1.00/1k), or SerpAPI

---

## 📈 Monthly Request Capacity at Free Tiers

| API | Free Monthly Requests | Sufficient for Development? |
|-----|----------------------|---------------------------|
| OpenAlex | ∞ Unlimited | ✅ Yes |
| Exa.ai | 20,000 | ✅ Yes |
| GitHub | ~4M (5k/hr × 24 × 30) | ✅ Yes |
| Guardian | 15,000 (500/day) | ✅ Yes |
| NY Times | 15,000 (500/day) | ✅ Yes |
| Semantic Scholar | ~2.6M (1 RPS) | ✅ Yes (can request more) |
| Tavily | 1,000 | ⚠️ Limited |
| Firecrawl | 1,000 | ⚠️ Limited |
| Resend | 3,000 | ⚠️ Limited |
| GNews | 3,000 | ❌ Very limited |
| NewsAPI | 3,000 | ❌ Very limited |
| SerpAPI | 250 | ❌ Very limited |
| Serper | 2,500 (one-time) | ❌ Trial only |
| Apify | ~$5 compute | ❌ Very limited |
| OpenAI | 0 (pay-per-use) | ❌ No free tier |

---

## 🔑 Key Findings

### You Have Strong Free Coverage For:
- ✅ Academic papers (OpenAlex unlimited, Semantic Scholar generous)
- ✅ GitHub repos (5,000/hour)
- ✅ Quality news (Guardian + NY Times = 30,000/month combined)
- ✅ Web search (Exa.ai 20,000/month)

### You Need Paid Plans For:
- ⚠️ High-volume web search (beyond Exa's 20k)
- ⚠️ Real-time news without delays (GNews/NewsAPI free have delays)
- ⚠️ Large-scale web scraping (beyond Firecrawl's 1k pages)
- ⚠️ AI/LLM usage (OpenAI pay-per-use)

### Best Value Paid APIs (if needed):
1. **Exa.ai**: $7/1k requests (good for AI agents)
2. **Serper**: $0.50-1.00/1k (cheapest Google search)
3. **Guardian Commercial**: Custom pricing for commercial use
4. **Firecrawl Standard**: $79/month for 100k pages

### Cost Optimization:
- Your current free tier gives you ~80,000+ requests/month capacity
- Focus on OpenAlex (unlimited), Exa.ai (20k), Guardian (15k), NY Times (15k)
- Only pay for services when you exceed free tier OR need commercial rights
