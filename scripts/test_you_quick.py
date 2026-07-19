"""Quick test for You.com with simple query"""
import asyncio
import httpx
from research_intel.config import Settings
from research_intel.ingestion.clients import YouComClient


async def test():
    async with httpx.AsyncClient() as http:
        settings = Settings()
        client = YouComClient(http, settings)
        
        # Test with simple queries
        queries = ["Python", "AI", "machine learning"]
        
        for query in queries:
            print(f"\n🔍 Testing: '{query}'")
            result = await client.fetch(query, max_results=3)
            
            if result.error:
                print(f"   ❌ Error: {result.error}")
            else:
                print(f"   ✅ Success! Retrieved {len(result.documents)} results")
                for i, doc in enumerate(result.documents, 1):
                    print(f"      {i}. {doc.title[:70]}")
                    print(f"         {doc.source_url}")

asyncio.run(test())
