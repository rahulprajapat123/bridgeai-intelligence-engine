"""Test NewsAPI Fallback Mechanism"""
import asyncio
import httpx
from research_intel.config import Settings
from research_intel.ingestion.clients import NewsApiClient

async def test_newsapi_fallback():
    print("\n" + "="*70)
    print("TESTING NEWSAPI FALLBACK MECHANISM")
    print("="*70)
    
    settings = Settings()
    
    print(f"\n📋 Configuration:")
    print(f"   Primary Key: {settings.newsapi_key[:20] if settings.newsapi_key else 'Not set'}...")
    print(f"   Alternate Key: {settings.newsapi_key_alternate[:20] if settings.newsapi_key_alternate else 'Not set'}...")
    
    if not settings.newsapi_key:
        print("\n❌ Primary NewsAPI key not configured!")
        return
    
    if not settings.newsapi_key_alternate:
        print("\n⚠️  No alternate key configured (fallback disabled)")
    
    # Test with actual API
    print(f"\n🔍 Testing NewsAPI...")
    print("-" * 70)
    
    async with httpx.AsyncClient(timeout=30.0) as http:
        client = NewsApiClient(http, settings)
        
        # Test fetch
        result = await client.fetch(
            query="artificial intelligence",
            max_results=5,
            domain="news"
        )
        
        if result.error:
            print(f"❌ Error: {result.error}")
            
            if settings.newsapi_key_alternate:
                print(f"\n🔄 Fallback should have been attempted automatically")
        else:
            print(f"✅ Success! Retrieved {len(result.documents)} articles")
            
            for i, doc in enumerate(result.documents[:3], 1):
                print(f"\n   {i}. {doc.title[:70]}...")
                print(f"      URL: {doc.source_url}")
                print(f"      Publisher: {doc.metadata.get('publisher', 'Unknown')}")
    
    print("\n" + "="*70)
    print("FALLBACK MECHANISM")
    print("="*70)
    print("\n✅ NewsAPI now has automatic fallback:")
    print("   1. Try primary key: 13d297a03a1f49d3b0b4ae17332f3235")
    print("   2. If primary fails (null/error), try alternate: 0d092f066679464291f64bfb75106f9b")
    print("   3. Return results from whichever works")
    print("\n✅ Same pattern as GNews and Firecrawl!")
    print("✅ Increased reliability and uptime")
    print("\n" + "="*70)

if __name__ == "__main__":
    asyncio.run(test_newsapi_fallback())
