"""Debug You.com API response"""
import asyncio
import httpx
from research_intel.config import Settings


async def test():
    settings = Settings()
    
    headers = {
        "X-API-Key": settings.you_api_key,
        "Accept": "application/json",
    }
    
    params = {
        "query": "Python programming",
        "count": 5,
        "offset": 0,
        "language": "EN",
        "safesearch": "moderate",
    }
    
    async with httpx.AsyncClient() as http:
        print("📡 Calling You.com API...")
        print(f"   URL: https://ydc-index.io/v1/search")
        print(f"   Params: {params}")
        
        response = await http.get(
            "https://ydc-index.io/v1/search",
            headers=headers,
            params=params,
            timeout=30.0
        )
        
        print(f"\n📊 Response Status: {response.status_code}")
        print(f"📄 Response Body:")
        
        try:
            data = response.json()
            import json
            print(json.dumps(data, indent=2)[:1000])  # First 1000 chars
            
            print(f"\n🔑 Keys in response: {list(data.keys())}")
            
            if "hits" in data:
                print(f"   hits: {len(data['hits'])} items")
            if "results" in data:
                print(f"   results: {len(data['results'])} items")
                
        except Exception as e:
            print(f"   Raw text: {response.text[:500]}")
            print(f"   Error parsing JSON: {e}")

asyncio.run(test())
