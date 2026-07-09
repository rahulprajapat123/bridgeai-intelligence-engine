"""
Test script to verify Apify integration is working correctly.
Tests multiple Apify scrapers with real API calls.
"""
import asyncio
import httpx
from research_intel.config import Settings

async def test_apify_web_scraper():
    """Test the Apify Web Scraper actor."""
    print("\n" + "="*60)
    print("Testing Apify Web Scraper")
    print("="*60)
    
    settings = Settings()
    if not settings.apify_api_token:
        print("❌ No APIFY_API_TOKEN found in environment")
        return False
    
    print(f"✓ Using API token: {settings.apify_api_token[:15]}...")
    
    async with httpx.AsyncClient(timeout=200.0) as client:
        try:
            # Test the website-content-crawler actor
            response = await client.post(
                "https://api.apify.com/v2/acts/apify~website-content-crawler/run-sync-get-dataset-items",
                params={"token": settings.apify_api_token, "timeout": 120},
                json={
                    "startUrls": [{"url": "https://techcrunch.com/"}],
                    "maxCrawlPages": 2,
                    "crawlerType": "playwright:adaptive",
                    "renderJavaScript": True,
                    "maxResults": 2,
                    "saveMarkdown": True,
                },
                timeout=130.0,
            )
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                items = response.json()
                print(f"✅ SUCCESS! Retrieved {len(items)} items")
                if items:
                    print(f"Sample item URL: {items[0].get('url', 'N/A')}")
                    print(f"Sample item title: {items[0].get('title', 'N/A')[:100]}...")
                return True
            else:
                print(f"❌ FAILED: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
            return False

async def test_apify_google_search():
    """Test Google Search via Apify."""
    print("\n" + "="*60)
    print("Testing Apify Google Search")
    print("="*60)
    
    settings = Settings()
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            # Test Google Search actor
            response = await client.post(
                "https://api.apify.com/v2/acts/apify~google-search-scraper/run-sync-get-dataset-items",
                params={"token": settings.apify_api_token, "timeout": 60},
                json={
                    "queries": "artificial intelligence latest research 2024",
                    "maxPagesPerQuery": 1,
                    "resultsPerPage": 5,
                },
                timeout=70.0,
            )
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                items = response.json()
                print(f"✅ SUCCESS! Retrieved {len(items)} search results")
                if items:
                    print(f"First result: {items[0].get('title', 'N/A')[:100]}...")
                return True
            else:
                print(f"❌ FAILED: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
            return False

async def test_apify_account_info():
    """Test Apify account access and get account info."""
    print("\n" + "="*60)
    print("Testing Apify Account Access")
    print("="*60)
    
    settings = Settings()
    
    async with httpx.AsyncClient() as client:
        try:
            # Get user account info
            response = await client.get(
                "https://api.apify.com/v2/user",
                params={"token": settings.apify_api_token}
            )
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json().get("data", {})
                print(f"✅ Account Active!")
                print(f"   Plan: {data.get('plan', 'N/A')}")
                print(f"   Email: {data.get('email', 'N/A')}")
                print(f"   Credits: ${data.get('monthlyCredits', {}).get('available', 0)}")
                return True
            else:
                print(f"❌ FAILED: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
            return False

async def main():
    """Run all Apify tests."""
    print("\n🔍 APIFY INTEGRATION TESTING")
    print("="*60)
    
    results = []
    
    # Test 1: Account access
    results.append(await test_apify_account_info())
    
    # Test 2: Web scraper
    results.append(await test_apify_web_scraper())
    
    # Test 3: Google search
    results.append(await test_apify_google_search())
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("✅ All Apify tests passed! Integration is working.")
    else:
        print("⚠️ Some tests failed. Check configuration.")

if __name__ == "__main__":
    asyncio.run(main())
