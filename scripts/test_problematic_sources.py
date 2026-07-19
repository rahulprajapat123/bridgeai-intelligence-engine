"""
Test TowardsDataScience and Papers with Code specifically
"""
import asyncio
import httpx
from research_intel.config import Settings

async def test_tds():
    """Test Towards Data Science RSS"""
    settings = Settings()
    async with httpx.AsyncClient(follow_redirects=True) as http:
        print("\n" + "="*70)
        print("Testing Towards Data Science RSS Feed")
        print("="*70)
        try:
            response = await http.get(
                "https://towardsdatascience.com/feed",
                timeout=15.0,
                follow_redirects=True
            )
            print(f"Status: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type')}")
            print(f"Response length: {len(response.text)}")
            print(f"First 500 chars:\n{response.text[:500]}")
            
            import feedparser
            feed = feedparser.parse(response.text)
            print(f"\nFeed entries: {len(feed.entries)}")
            if feed.entries:
                print(f"First entry title: {feed.entries[0].get('title')}")
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

async def test_pwc():
    """Test Papers with Code API"""
    async with httpx.AsyncClient(follow_redirects=True) as http:
        print("\n" + "="*70)
        print("Testing Papers with Code API")
        print("="*70)
        try:
            response = await http.get(
                "https://paperswithcode.com/api/v1/papers/",
                params={"q": "neural networks", "items_per_page": 5},
                headers={"User-Agent": "Research-Intelligence-Platform/0.1.0"},
                timeout=30.0
            )
            print(f"Status: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type')}")
            print(f"Response length: {len(response.text)}")
            print(f"First 1000 chars:\n{response.text[:1000]}")
            
            data = response.json()
            print(f"\nResults count: {len(data.get('results', []))}")
            if data.get('results'):
                print(f"First paper: {data['results'][0].get('title')}")
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

async def test_semantic_scholar():
    """Test Semantic Scholar API"""
    settings = Settings()
    async with httpx.AsyncClient(follow_redirects=True) as http:
        print("\n" + "="*70)
        print("Testing Semantic Scholar API")
        print("="*70)
        try:
            headers = {}
            if settings.semantic_scholar_api_key:
                headers["x-api-key"] = settings.semantic_scholar_api_key
                print(f"Using API key: {settings.semantic_scholar_api_key[:10]}...")
            else:
                print("No API key configured")
            
            response = await http.get(
                "https://api.semanticscholar.org/graph/v1/paper/search",
                params={
                    "query": "artificial intelligence",
                    "limit": 5,
                    "fields": "title,abstract,url,authors,year",
                },
                headers=headers,
                timeout=30.0
            )
            print(f"Status: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type')}")
            print(f"Response:\n{response.text[:500]}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"\nResults: {len(data.get('data', []))}")
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

async def main():
    await test_tds()
    await asyncio.sleep(1)
    await test_pwc()
    await asyncio.sleep(1)
    await test_semantic_scholar()

if __name__ == "__main__":
    asyncio.run(main())
