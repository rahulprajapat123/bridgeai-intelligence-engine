"""Test script for previously "query-dependent" sources"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from research_intel.config import Settings
from research_intel.ingestion.clients import (
    HuggingFaceClient,
    ProductHuntClient,
    DevToClient,
    RSSFeedClient,
    KDnuggetsClient,
    AIWeeklyClient,
)


async def test_source(client, query: str, source_name: str):
    """Test a single source"""
    print(f"\n{'='*80}")
    print(f"Testing: {source_name}")
    print(f"Query: '{query}'")
    print(f"{'='*80}")
    
    try:
        result = await asyncio.wait_for(
            client.fetch(query, max_results=5, domain="Test"),
            timeout=30.0
        )
        
        if result.error:
            print(f"❌ Error: {result.error}")
            return False
        elif len(result.documents) == 0:
            print(f"📭 No results (but API worked)")
            return True  # API works, just no matching content
        else:
            print(f"✅ Success! Retrieved {len(result.documents)} items")
            for i, doc in enumerate(result.documents[:3], 1):
                print(f"\n  {i}. {doc.title[:80]}")
                print(f"     URL: {doc.source_url[:80]}")
            return True
            
    except asyncio.TimeoutError:
        print(f"⏱️  Timeout (>30s)")
        return False
    except Exception as e:
        print(f"❌ Exception: {str(e)[:100]}")
        return False


async def main():
    print("\n" + "="*80)
    print("TESTING PREVIOUSLY QUERY-DEPENDENT SOURCES")
    print("="*80)
    
    settings = Settings()
    test_query = "artificial intelligence"
    
    results = {}
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as http:
        # Test Hugging Face
        client = HuggingFaceClient(http, settings)
        results["Hugging Face"] = await test_source(client, test_query, "Hugging Face")
        await asyncio.sleep(1)
        
        # Test Product Hunt
        if settings.producthunt_token:
            client = ProductHuntClient(http, settings)
            results["Product Hunt"] = await test_source(client, test_query, "Product Hunt")
            await asyncio.sleep(1)
        else:
            print(f"\n⚠️  Skipping Product Hunt (no API token)")
            results["Product Hunt"] = None
        
        # Test Dev.to
        client = DevToClient(http, settings)
        results["Dev.to"] = await test_source(client, test_query, "Dev.to")
        await asyncio.sleep(1)
        
        # Test RSS Feeds
        client = RSSFeedClient(http, settings)
        results["RSS Feeds"] = await test_source(client, test_query, "RSS Feeds")
        await asyncio.sleep(1)
        
        # Test KDnuggets
        client = KDnuggetsClient(http, settings)
        results["KDnuggets"] = await test_source(client, test_query, "KDnuggets")
        await asyncio.sleep(1)
        
        # Test Import AI
        client = AIWeeklyClient(http, settings)
        results["Import AI"] = await test_source(client, test_query, "Import AI")
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    working = [name for name, status in results.items() if status is True]
    failed = [name for name, status in results.items() if status is False]
    skipped = [name for name, status in results.items() if status is None]
    
    print(f"\n✅ Working: {len(working)}/{len([s for s in results.values() if s is not None])}")
    for name in working:
        print(f"   • {name}")
    
    if failed:
        print(f"\n❌ Failed: {len(failed)}")
        for name in failed:
            print(f"   • {name}")
    
    if skipped:
        print(f"\n⚠️  Skipped: {len(skipped)}")
        for name in skipped:
            print(f"   • {name}")
    
    print("\n" + "="*80)
    
    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    asyncio.run(main())
