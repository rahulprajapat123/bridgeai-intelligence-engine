"""
Test Semantic Scholar with proper rate limiting
"""
import asyncio
import time
import httpx
from research_intel.config import Settings
from research_intel.ingestion.clients import SemanticScholarClient

async def test_semantic_scholar_rate_limiting():
    """Test that Semantic Scholar respects 1 req/sec limit with proper gaps"""
    settings = Settings()
    async with httpx.AsyncClient(follow_redirects=True) as http:
        client = SemanticScholarClient(http, settings)
        
        print("\n" + "="*70)
        print("Testing Semantic Scholar with Rate Limiting")
        print("="*70)
        print(f"Client: {client.name}")
        print(f"Enabled: {client.enabled()}")
        print(f"API Key: {'Yes' if client.api_key else 'No (using public tier)'}")
        print(f"Expected: 1.5 second gaps between requests")
        print("="*70)
        
        # Test 3 consecutive requests to verify rate limiting works
        queries = ["machine learning", "neural networks", "deep learning"]
        request_times = []
        
        for i, query in enumerate(queries, 1):
            print(f"\n[Request {i}/3] Query: '{query}'")
            start = time.time()
            
            try:
                result = await client.fetch(query=query, max_results=5)
                elapsed = time.time() - start
                request_times.append(time.time())
                
                print(f"  ✓ Completed in {elapsed:.2f}s")
                print(f"  Documents: {len(result.documents)}")
                
                if result.error:
                    print(f"  ⚠ Warning: {result.error}")
                elif result.documents:
                    print(f"  Sample: {result.documents[0].title[:60]}...")
                
                # Calculate gap since last request
                if i > 1:
                    gap = request_times[-1] - request_times[-2]
                    print(f"  Gap since last request: {gap:.2f}s")
                    if gap >= 1.5:
                        print(f"  ✓ Rate limit respected (>= 1.5s gap)")
                    else:
                        print(f"  ✗ WARNING: Gap too short!")
                        
            except Exception as e:
                print(f"  ✗ Error: {str(e)}")
        
        print("\n" + "="*70)
        print("Rate Limiting Test Complete")
        print("="*70)
        
        if len(request_times) > 1:
            gaps = [request_times[i] - request_times[i-1] for i in range(1, len(request_times))]
            avg_gap = sum(gaps) / len(gaps)
            min_gap = min(gaps)
            max_gap = max(gaps)
            
            print(f"\nGap Statistics:")
            print(f"  Average gap: {avg_gap:.2f}s")
            print(f"  Min gap: {min_gap:.2f}s")
            print(f"  Max gap: {max_gap:.2f}s")
            print(f"  Required: >= 1.5s")
            
            if min_gap >= 1.5:
                print(f"\n✓ SUCCESS: All requests respected the 1 req/sec limit")
            else:
                print(f"\n✗ FAILED: Some requests violated rate limit")

if __name__ == "__main__":
    asyncio.run(test_semantic_scholar_rate_limiting())
