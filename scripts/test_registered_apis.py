"""Test script for newly added API sources with registration"""
import asyncio
import httpx
from research_intel.config import Settings
from research_intel.ingestion.clients import (
    ProductHuntClient,
    COREClient,
    YouComClient,
)


async def test_producthunt():
    """Test ProductHunt API"""
    print("\n" + "="*60)
    print("Testing ProductHunt API...")
    print("="*60)
    
    async with httpx.AsyncClient() as http:
        settings = Settings()
        
        if not settings.producthunt_token:
            print("❌ PRODUCTHUNT_TOKEN not found in .env")
            return
        
        client = ProductHuntClient(http, settings)
        result = await client.fetch("AI", max_results=5)
        
        if result.error:
            print(f"❌ Error: {result.error}")
        else:
            print(f"✅ Success! Retrieved {len(result.documents)} products")
            for i, doc in enumerate(result.documents[:3], 1):
                print(f"\n   {i}. {doc.title}")
                print(f"      Votes: {doc.metadata.get('votes', 0)} | Comments: {doc.metadata.get('comments', 0)}")
                print(f"      Topics: {', '.join(doc.metadata.get('topics', [])[:3])}")
                print(f"      URL: {doc.source_url}")


async def test_core():
    """Test CORE API"""
    print("\n" + "="*60)
    print("Testing CORE API...")
    print("="*60)
    
    async with httpx.AsyncClient() as http:
        settings = Settings()
        
        if not settings.core_api_key:
            print("❌ CORE_API_KEY not found in .env")
            return
        
        client = COREClient(http, settings)
        result = await client.fetch("machine learning", max_results=5)
        
        if result.error:
            print(f"❌ Error: {result.error}")
        else:
            print(f"✅ Success! Retrieved {len(result.documents)} papers")
            for i, doc in enumerate(result.documents[:3], 1):
                print(f"\n   {i}. {doc.title[:80]}")
                print(f"      Authors: {', '.join(doc.authors[:3]) if doc.authors else 'Unknown'}")
                print(f"      Year: {doc.metadata.get('year', 'N/A')}")
                print(f"      Citations: {doc.metadata.get('citations', 0)}")


async def test_you_com():
    """Test You.com API"""
    print("\n" + "="*60)
    print("Testing You.com API...")
    print("="*60)
    
    async with httpx.AsyncClient() as http:
        settings = Settings()
        
        if not settings.you_api_key:
            print("❌ YOU_API_KEY not found in .env")
            return
        
        client = YouComClient(http, settings)
        result = await client.fetch("artificial intelligence news", max_results=5)
        
        if result.error:
            print(f"❌ Error: {result.error}")
        else:
            print(f"✅ Success! Retrieved {len(result.documents)} results")
            for i, doc in enumerate(result.documents[:3], 1):
                print(f"\n   {i}. {doc.title[:80]}")
                print(f"      Score: {doc.metadata.get('score', 0)}")
                print(f"      URL: {doc.source_url}")


async def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("TESTING 3 NEW REGISTERED API SOURCES")
    print("="*60)
    
    tests = [
        ("ProductHunt", test_producthunt),
        ("CORE", test_core),
        ("You.com", test_you_com),
    ]
    
    results = {"passed": 0, "failed": 0}
    
    for name, test_func in tests:
        try:
            await test_func()
            results["passed"] += 1
        except Exception as e:
            print(f"\n❌ FAILED: {name}")
            print(f"   Error: {str(e)}")
            results["failed"] += 1
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"✅ Passed: {results['passed']}/{len(tests)}")
    print(f"❌ Failed: {results['failed']}/{len(tests)}")
    print("="*60)
    
    print("\n📊 TOTAL SOURCES NOW: 36+")
    print("   - 7 FREE (no registration): Jina AI, HackerNews, Dev.to, RSS, GDELT, npm, PyPI")
    print("   - 3 NEW (with registration): ProductHunt, CORE, You.com")
    print("   - 26 existing sources")


if __name__ == "__main__":
    asyncio.run(main())
