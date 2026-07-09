"""Test Apify API connectivity and token validity."""
import asyncio
import httpx
from dotenv import load_dotenv
import os

load_dotenv()

async def test_apify_api():
    """Test if Apify API token is valid."""
    api_token = os.getenv("APIFY_API_TOKEN")
    
    if not api_token:
        print("❌ APIFY_API_TOKEN not found in .env file")
        return False
    
    print(f"🔑 Found API Token: {api_token[:15]}...")
    
    # Test 1: Get user info (validates token)
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            print("\n📡 Testing Apify API connectivity...")
            response = await client.get(
                "https://api.apify.com/v2/users/me",
                params={"token": api_token}
            )
            
            if response.status_code == 200:
                user_data = response.json()
                print(f"✅ API Token is VALID")
                print(f"   User: {user_data.get('data', {}).get('username', 'N/A')}")
                print(f"   Email: {user_data.get('data', {}).get('email', 'N/A')}")
                
                # Test 2: List available actors
                print("\n📋 Fetching available actors...")
                actors_response = await client.get(
                    "https://api.apify.com/v2/store",
                    params={"token": api_token, "limit": 5}
                )
                
                if actors_response.status_code == 200:
                    actors = actors_response.json()
                    print(f"✅ Successfully fetched {actors.get('total', 0)} actors from store")
                    print("   Top 5 actors:")
                    for item in actors.get('data', {}).get('items', [])[:5]:
                        print(f"   - {item.get('name', 'N/A')} by {item.get('username', 'N/A')}")
                
                return True
                
            elif response.status_code == 401:
                print(f"❌ API Token is INVALID or EXPIRED")
                print(f"   Status: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
            else:
                print(f"⚠️  Unexpected response: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except httpx.TimeoutException:
            print("❌ Request timed out - Apify API may be unreachable")
            return False
        except Exception as e:
            print(f"❌ Error testing Apify API: {str(e)}")
            return False

if __name__ == "__main__":
    result = asyncio.run(test_apify_api())
    print("\n" + "="*60)
    if result:
        print("✅ APIFY API IS WORKING")
    else:
        print("❌ APIFY API TEST FAILED")
    print("="*60)
