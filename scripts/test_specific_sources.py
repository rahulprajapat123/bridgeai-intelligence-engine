"""
Test specific failing sources reported by user
"""
import asyncio
import os
from dotenv import load_dotenv
import httpx
from research_intel.config import Settings
from research_intel.ingestion.clients import (
    KDnuggetsClient,
    AIWeeklyClient,
    SemanticScholarClient,
    PapersWithCodeClient,
    ApifyRedditScraperClient,
    ApifyYouTubeScraperClient,
)

load_dotenv()

async def test_source(client_class, query="artificial intelligence"):
    """Test a single source"""
    settings = Settings()
    async with httpx.AsyncClient(follow_redirects=True) as http:
        client = client_class(http, settings)
        print(f"\n{'='*70}")
        print(f"Testing: {client.name}")
        print(f"Route: {client.route_name}")
        print(f"Enabled: {client.enabled()}")
        print(f"{'='*70}")
        
        try:
            result = await client.fetch(query=query, max_results=5)
            print(f"✓ Success: {len(result.documents)} documents fetched")
            if result.error:
                print(f"✗ Error: {result.error}")
            if result.documents:
                print(f"\nSample document:")
                doc = result.documents[0]
                print(f"  Title: {doc.title[:100]}")
                print(f"  URL: {doc.source_url}")
                print(f"  Date: {doc.publication_date}")
            else:
                print(f"⚠ No documents returned")
        except Exception as e:
            print(f"✗ Exception: {str(e)}")
            import traceback
            traceback.print_exc()

async def main():
    print("\n" + "="*70)
    print("TESTING SPECIFIC FAILING SOURCES")
    print("="*70)
    
    sources = [
        (KDnuggetsClient, "machine learning"),
        (AIWeeklyClient, "AI"),  # Import AI
        (SemanticScholarClient, "artificial intelligence"),
        (PapersWithCodeClient, "neural networks"),
        (ApifyRedditScraperClient, "AI research"),
        (ApifyYouTubeScraperClient, "machine learning"),
    ]
    
    for client_class, query in sources:
        await test_source(client_class, query)
        await asyncio.sleep(1.5)  # Rate limiting
    
    print("\n" + "="*70)
    print("TESTING COMPLETE")
    print("="*70)

if __name__ == "__main__":
    asyncio.run(main())
