"""Test script for newly added FREE API sources"""
import asyncio
import httpx
from research_intel.config import Settings
from research_intel.ingestion.clients import (
    JinaAIClient,
    HackerNewsClient,
    DevToClient,
    RSSFeedClient,
    GDELTClient,
    NpmClient,
    PyPIClient,
)


async def test_jina_ai():
    """Test Jina AI Reader"""
    print("\n" + "="*60)
    print("Testing Jina AI Reader...")
    print("="*60)
    
    async with httpx.AsyncClient() as http:
        settings = Settings()
        client = JinaAIClient(http, settings)
        
        # Test with a simple URL
        result = await client.fetch("https://firecrawl.dev")
        
        if result.error:
            print(f"❌ Error: {result.error}")
        else:
            print(f"✅ Success! Retrieved {len(result.documents)} document(s)")
            if result.documents:
                doc = result.documents[0]
                print(f"   Title: {doc.title[:100]}")
                print(f"   URL: {doc.source_url}")
                print(f"   Content preview: {doc.text[:200]}...")


async def test_hackernews():
    """Test HackerNews API"""
    print("\n" + "="*60)
    print("Testing Hacker News API...")
    print("="*60)
    
    async with httpx.AsyncClient() as http:
        settings = Settings()
        client = HackerNewsClient(http, settings)
        
        result = await client.fetch("AI", max_results=5)
        
        if result.error:
            print(f"❌ Error: {result.error}")
        else:
            print(f"✅ Success! Retrieved {len(result.documents)} stories")
            for i, doc in enumerate(result.documents[:3], 1):
                print(f"\n   {i}. {doc.title}")
                print(f"      Score: {doc.metadata.get('score', 0)} | Comments: {doc.metadata.get('comments', 0)}")
                print(f"      URL: {doc.source_url}")


async def test_devto():
    """Test Dev.to API"""
    print("\n" + "="*60)
    print("Testing Dev.to API...")
    print("="*60)
    
    async with httpx.AsyncClient() as http:
        settings = Settings()
        client = DevToClient(http, settings)
        
        result = await client.fetch("python", max_results=5)
        
        if result.error:
            print(f"❌ Error: {result.error}")
        else:
            print(f"✅ Success! Retrieved {len(result.documents)} articles")
            for i, doc in enumerate(result.documents[:3], 1):
                print(f"\n   {i}. {doc.title}")
                print(f"      Author: {doc.authors[0] if doc.authors else 'Unknown'}")
                print(f"      Reactions: {doc.metadata.get('reactions', 0)}")
                print(f"      Tags: {', '.join(doc.metadata.get('tags', [])[:5])}")


async def test_rss_feeds():
    """Test RSS Feed Client"""
    print("\n" + "="*60)
    print("Testing RSS Feed Client...")
    print("="*60)
    
    async with httpx.AsyncClient() as http:
        settings = Settings()
        client = RSSFeedClient(http, settings)
        
        result = await client.fetch("AI", max_results=5)
        
        if result.error:
            print(f"❌ Error: {result.error}")
        else:
            print(f"✅ Success! Retrieved {len(result.documents)} articles")
            for i, doc in enumerate(result.documents[:3], 1):
                print(f"\n   {i}. {doc.title[:80]}")
                print(f"      Source: {doc.metadata.get('feed_source', 'Unknown')}")
                print(f"      Date: {doc.publication_date or 'N/A'}")


async def test_gdelt():
    """Test GDELT API"""
    print("\n" + "="*60)
    print("Testing GDELT API...")
    print("="*60)
    
    async with httpx.AsyncClient() as http:
        settings = Settings()
        client = GDELTClient(http, settings)
        
        result = await client.fetch("artificial intelligence", max_results=5)
        
        if result.error:
            print(f"❌ Error: {result.error}")
        else:
            print(f"✅ Success! Retrieved {len(result.documents)} articles")
            for i, doc in enumerate(result.documents[:3], 1):
                print(f"\n   {i}. {doc.title[:80]}")
                print(f"      Country: {doc.metadata.get('source_country', 'Unknown')}")
                print(f"      Language: {doc.metadata.get('language', 'Unknown')}")


async def test_npm():
    """Test npm API"""
    print("\n" + "="*60)
    print("Testing npm API...")
    print("="*60)
    
    async with httpx.AsyncClient() as http:
        settings = Settings()
        client = NpmClient(http, settings)
        
        result = await client.fetch("react", max_results=5)
        
        if result.error:
            print(f"❌ Error: {result.error}")
        else:
            print(f"✅ Success! Retrieved {len(result.documents)} packages")
            for i, doc in enumerate(result.documents[:3], 1):
                print(f"\n   {i}. {doc.title}")
                print(f"      Version: {doc.metadata.get('version', 'Unknown')}")
                print(f"      Description: {doc.text[:100]}")


async def test_pypi():
    """Test PyPI API"""
    print("\n" + "="*60)
    print("Testing PyPI API...")
    print("="*60)
    
    async with httpx.AsyncClient() as http:
        settings = Settings()
        client = PyPIClient(http, settings)
        
        # Test with specific package name
        result = await client.fetch("fastapi", max_results=1)
        
        if result.error:
            print(f"⚠️  Note: {result.error}")
            if result.documents:
                print(f"✅ But retrieved {len(result.documents)} package(s)")
        else:
            print(f"✅ Success! Retrieved {len(result.documents)} package(s)")
            
        for i, doc in enumerate(result.documents[:3], 1):
            print(f"\n   {i}. {doc.title}")
            print(f"      Version: {doc.metadata.get('version', 'Unknown')}")
            print(f"      Description: {doc.text[:100]}")


async def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("TESTING 7 NEW FREE API SOURCES")
    print("="*60)
    
    tests = [
        ("Jina AI Reader", test_jina_ai),
        ("Hacker News", test_hackernews),
        ("Dev.to", test_devto),
        ("RSS Feeds", test_rss_feeds),
        ("GDELT", test_gdelt),
        ("npm", test_npm),
        ("PyPI", test_pypi),
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


if __name__ == "__main__":
    asyncio.run(main())
