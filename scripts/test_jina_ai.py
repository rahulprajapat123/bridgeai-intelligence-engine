"""
Test Jina AI with API key authentication
"""
import asyncio
import httpx
from research_intel.config import Settings
from research_intel.ingestion.clients import JinaAIClient

async def test_jina_ai():
    """Test Jina AI search and reader with authentication"""
    settings = Settings()
    async with httpx.AsyncClient(follow_redirects=True) as http:
        client = JinaAIClient(http, settings)
        
        print("\n" + "="*70)
        print("Testing Jina AI Search & Reader")
        print("="*70)
        print(f"Client: {client.name}")
        print(f"Enabled: {client.enabled()}")
        print(f"API Key: {'Yes - ' + client.api_key[:20] + '...' if client.api_key else 'No'}")
        print("="*70)
        
        # Test 1: Search mode
        print("\n[Test 1] Search Mode: 'artificial intelligence news'")
        try:
            result = await client.fetch(query="artificial intelligence news", max_results=3)
            if result.error:
                print(f"  ✗ Error: {result.error}")
            else:
                print(f"  ✓ Success: {len(result.documents)} documents")
                if result.documents:
                    for i, doc in enumerate(result.documents[:2], 1):
                        print(f"\n  Document {i}:")
                        print(f"    Title: {doc.title[:70]}...")
                        print(f"    URL: {doc.source_url}")
                        print(f"    Content: {doc.text[:100]}...")
        except Exception as e:
            print(f"  ✗ Exception: {e}")
        
        # Test 2: Reader mode with a specific URL
        print("\n\n[Test 2] Reader Mode: Convert URL to markdown")
        test_url = "https://techcrunch.com"
        try:
            result = await client.fetch(query=test_url, max_results=1)
            if result.error:
                print(f"  ✗ Error: {result.error}")
            else:
                print(f"  ✓ Success: {len(result.documents)} document")
                if result.documents:
                    doc = result.documents[0]
                    print(f"  Title: {doc.title}")
                    print(f"  URL: {doc.source_url}")
                    print(f"  Content length: {len(doc.text)} chars")
                    print(f"  Content preview: {doc.text[:200]}...")
        except Exception as e:
            print(f"  ✗ Exception: {e}")
        
        print("\n" + "="*70)
        print("Test Complete")
        print("="*70)

if __name__ == "__main__":
    asyncio.run(test_jina_ai())
