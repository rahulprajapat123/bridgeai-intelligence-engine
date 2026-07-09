"""
Comprehensive test for all Apify scrapers.
Tests Reddit, YouTube, Twitter, News, and Web scrapers.
"""
import asyncio
import httpx
from research_intel.config import Settings

async def test_reddit_scraper():
    """Test Apify Reddit scraper."""
    print("\n" + "="*60)
    print("Testing Apify Reddit Scraper")
    print("="*60)
    
    settings = Settings()
    async with httpx.AsyncClient(timeout=150.0) as client:
        try:
            response = await client.post(
                "https://api.apify.com/v2/acts/trudax~reddit-scraper/run-sync-get-dataset-items",
                params={"token": settings.apify_api_token, "timeout": 60},
                json={
                    "searches": ["machine learning"],
                    "searchPosts": True,
                    "maxPostCount": 5,
                    "sort": "relevance",
                    "time": "month",
                },
                timeout=70.0,
            )
            
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                items = response.json()
                print(f"✅ SUCCESS! Got {len(items)} Reddit posts")
                if items:
                    for i, item in enumerate(items[:2], 1):
                        print(f"\n{i}. {item.get('title', 'N/A')[:80]}...")
                        print(f"   Subreddit: r/{item.get('communityName', 'N/A')}")
                        print(f"   Upvotes: {item.get('upVotes', 0)}")
                return True
            else:
                print(f"❌ FAILED: {response.text[:500]}")
                return False
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
            return False

async def test_youtube_scraper():
    """Test Apify YouTube scraper."""
    print("\n" + "="*60)
    print("Testing Apify YouTube Scraper")
    print("="*60)
    
    settings = Settings()
    async with httpx.AsyncClient(timeout=150.0) as client:
        try:
            response = await client.post(
                "https://api.apify.com/v2/acts/bernardo~youtube-scraper/run-sync-get-dataset-items",
                params={"token": settings.apify_api_token, "timeout": 60},
                json={
                    "searchKeywords": "artificial intelligence 2024",
                    "maxResults": 5,
                    "searchType": "videos",
                },
                timeout=70.0,
            )
            
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                items = response.json()
                print(f"✅ SUCCESS! Got {len(items)} YouTube videos")
                if items:
                    for i, item in enumerate(items[:2], 1):
                        print(f"\n{i}. {item.get('title', 'N/A')[:80]}...")
                        print(f"   Channel: {item.get('channelName', 'N/A')}")
                        print(f"   Views: {item.get('viewCount', 0):,}")
                return True
            else:
                print(f"❌ FAILED: {response.text[:500]}")
                return False
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
            return False

async def test_twitter_scraper():
    """Test Apify Twitter scraper."""
    print("\n" + "="*60)
    print("Testing Apify Twitter Scraper")
    print("="*60)
    
    settings = Settings()
    async with httpx.AsyncClient(timeout=150.0) as client:
        try:
            response = await client.post(
                "https://api.apify.com/v2/acts/apidojo~tweet-scraper/run-sync-get-dataset-items",
                params={"token": settings.apify_api_token, "timeout": 60},
                json={
                    "queries": ["#AI #MachineLearning"],
                    "maxItems": 5,
                    "sort": "Latest",
                    "tweetLanguage": "en",
                },
                timeout=70.0,
            )
            
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                items = response.json()
                print(f"✅ SUCCESS! Got {len(items)} tweets")
                if items:
                    for i, item in enumerate(items[:2], 1):
                        print(f"\n{i}. @{item.get('author', {}).get('userName', 'N/A')}")
                        print(f"   {item.get('text', 'N/A')[:100]}...")
                        print(f"   Likes: {item.get('likeCount', 0)} | RTs: {item.get('retweetCount', 0)}")
                return True
            else:
                print(f"❌ FAILED: {response.text[:500]}")
                return False
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
            return False

async def test_news_scraper():
    """Test Apify News scraper."""
    print("\n" + "="*60)
    print("Testing Apify News Scraper")
    print("="*60)
    
    settings = Settings()
    async with httpx.AsyncClient(timeout=150.0) as client:
        try:
            search_url = "https://news.google.com/search?q=artificial+intelligence"
            response = await client.post(
                "https://api.apify.com/v2/acts/apify~google-news-scraper/run-sync-get-dataset-items",
                params={"token": settings.apify_api_token, "timeout": 60},
                json={
                    "startUrls": [{"url": search_url}],
                    "maxItems": 5,
                },
                timeout=70.0,
            )
            
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                items = response.json()
                print(f"✅ SUCCESS! Got {len(items)} news articles")
                if items:
                    for i, item in enumerate(items[:2], 1):
                        print(f"\n{i}. {item.get('title', 'N/A')[:80]}...")
                        source = item.get('source', {})
                        publisher = source.get('name') if isinstance(source, dict) else source
                        print(f"   Source: {publisher}")
                return True
            else:
                print(f"❌ FAILED: {response.text[:500]}")
                return False
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
            return False

async def test_web_scraper():
    """Test Apify Web Scraper (improved timeout)."""
    print("\n" + "="*60)
    print("Testing Apify Web Scraper")
    print("="*60)
    
    settings = Settings()
    async with httpx.AsyncClient(timeout=150.0) as client:
        try:
            response = await client.post(
                "https://api.apify.com/v2/acts/apify~website-content-crawler/run-sync-get-dataset-items",
                params={"token": settings.apify_api_token, "timeout": 90},
                json={
                    "startUrls": [{"url": "https://news.ycombinator.com/"}],
                    "maxCrawlPages": 2,
                    "crawlerType": "playwright:adaptive",
                    "maxResults": 2,
                },
                timeout=100.0,
            )
            
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                items = response.json()
                print(f"✅ SUCCESS! Scraped {len(items)} pages")
                if items:
                    print(f"Sample URL: {items[0].get('url', 'N/A')}")
                return True
            else:
                print(f"❌ FAILED: {response.text[:500]}")
                return False
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
            return False

async def main():
    """Run all Apify scraper tests."""
    print("\n🚀 TESTING ALL APIFY SCRAPERS (Premium Subscription)")
    print("="*60)
    
    results = {
        "Reddit": await test_reddit_scraper(),
        "YouTube": await test_youtube_scraper(),
        "Twitter": await test_twitter_scraper(),
        "News": await test_news_scraper(),
        "Web": await test_web_scraper(),
    }
    
    # Summary
    print("\n" + "="*60)
    print("📊 SUMMARY")
    print("="*60)
    
    for scraper, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{scraper:15} {status}")
    
    passed = sum(results.values())
    total = len(results)
    print(f"\n{passed}/{total} scrapers working ({(passed/total)*100:.0f}%)")
    
    if passed >= 3:
        print("\n✅ Apify integration is functional! Premium scrapers are active.")
    else:
        print("\n⚠️ Some scrapers failed. Check API token and actor availability.")

if __name__ == "__main__":
    asyncio.run(main())
