"""Test New Blog Sources: Towards Data Science, KDnuggets, AI Weekly"""
import asyncio
import httpx
from research_intel.config import Settings
from research_intel.ingestion.clients import (
    TowardsDataScienceClient,
    KDnuggetsClient,
    AIWeeklyClient
)

async def test_blog_sources():
    print("\n" + "="*80)
    print("TESTING NEW BLOG SOURCES")
    print("="*80)
    
    settings = Settings()
    
    sources = [
        ("Towards Data Science", TowardsDataScienceClient, "machine learning"),
        ("KDnuggets", KDnuggetsClient, "data science"),
        ("Import AI", AIWeeklyClient, "AI"),
    ]
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as http:
        for i, (name, ClientClass, query) in enumerate(sources, 1):
            print(f"\n{i}. Testing {name}")
            print("-" * 80)
            print(f"   Query: '{query}'")
            
            client = ClientClass(http, settings)
            result = await client.fetch(query, max_results=5, domain="blog")
            
            if result.error:
                print(f"   ❌ Error: {result.error}")
            elif not result.documents:
                print(f"   ⚠️  No documents found (may need different query)")
            else:
                print(f"   ✅ Success! Retrieved {len(result.documents)} articles")
                
                for j, doc in enumerate(result.documents[:3], 1):
                    print(f"\n      {j}. {doc.title[:70]}...")
                    print(f"         URL: {doc.source_url[:80]}")
                    print(f"         Published: {doc.publication_date or 'Unknown'}")
                    
                    # Show specific metadata
                    if name == "Towards Data Science":
                        print(f"         Paywall: {doc.metadata.get('paywall', 'N/A')}")
                    elif name == "KDnuggets":
                        categories = doc.metadata.get('categories', [])
                        if categories:
                            print(f"         Categories: {', '.join(categories[:3])}")
                    elif name == "Import AI":
                        print(f"         Type: {doc.metadata.get('type', 'N/A')}")
    
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    print("\n✅ New Blog Sources Added:")
    print("   1. Towards Data Science (Medium)")
    print("      • RSS feed: https://towardsdatascience.com/feed")
    print("      • Note: ~3 free articles/month, then paywalled")
    print("      • Content: AI, ML, Data Science tutorials")
    
    print("\n   2. KDnuggets")
    print("      • RSS feed: https://www.kdnuggets.com/feed")
    print("      • Note: Fully FREE")
    print("      • Content: Data Science, ML news and tutorials")
    
    print("\n   3. Import AI")
    print("      • RSS feed: https://jack-clark.net/feed/")
    print("      • Note: FREE newsletter by Jack Clark")
    print("      • Content: Weekly AI/ML news and research digest")
    
    print("\n📊 Total Blog Sources Now: 5")
    print("   • Dev.to (FREE)")
    print("   • RSS Feeds (13 curated feeds)")
    print("   • Towards Data Science (3 free/month)")
    print("   • KDnuggets (FREE)")
    print("   • Import AI (FREE)")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    asyncio.run(test_blog_sources())
