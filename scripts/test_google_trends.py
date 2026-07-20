"""Quick test for Google Trends client"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from research_intel.config import Settings
from research_intel.ingestion.clients import GoogleTrendsClient


async def test_google_trends():
    print("="*80)
    print("Testing Google Trends Client (pytrends)")
    print("="*80)
    
    settings = Settings()
    
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as http:
        client = GoogleTrendsClient(http, settings)
        
        print(f"\n✓ Client initialized: {client.name}")
        print(f"✓ Route: {client.route_name}")
        print(f"✓ Source type: {client.source_type}")
        print(f"✓ Enabled: {client.enabled()}")
        
        print("\n" + "-"*80)
        print("Fetching trends for 'artificial intelligence'...")
        print("-"*80)
        
        result = await client.fetch("artificial intelligence", max_results=5)
        
        if result.error:
            print(f"\n❌ Error: {result.error}")
            return False
        
        print(f"\n✅ Success! Retrieved {len(result.documents)} trend items")
        
        for i, doc in enumerate(result.documents, 1):
            print(f"\n{i}. {doc.title}")
            print(f"   URL: {doc.source_url}")
            print(f"   Text: {doc.text[:150]}...")
            print(f"   Metadata: {doc.metadata}")
        
        return True


async def main():
    try:
        success = await test_google_trends()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
