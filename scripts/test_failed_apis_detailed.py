"""
Detailed testing for failed APIs
"""
import os
import requests
from dotenv import load_dotenv
import json

load_dotenv()

print("\n" + "="*70)
print("DETAILED TESTING FOR FAILED APIs")
print("="*70 + "\n")

# 1. APIFY
print("1. APIFY API TEST")
print("-" * 70)
token = os.getenv("APIFY_API_TOKEN")
print(f"Token: {token[:20]}...{token[-10:]}")

# Try different endpoints
endpoints = [
    f"https://api.apify.com/v2/user?token={token}",
    f"https://api.apify.com/v2/acts?token={token}",
    f"https://api.apify.com/v2/store?token={token}",
]

for endpoint in endpoints:
    try:
        response = requests.get(endpoint, timeout=10)
        print(f"\nEndpoint: {endpoint.split('?')[0]}")
        print(f"Status: {response.status_code}")
        if response.status_code != 200:
            print(f"Response: {response.text[:200]}")
    except Exception as e:
        print(f"Error: {e}")

# 2. FIRECRAWL API TEST
print("\n\n2. FIRECRAWL API TEST")
print("-" * 70)
api_key = os.getenv("FIRECRAWL_API_KEY")
print(f"API Key: {api_key[:20]}...{api_key[-10:]}")

# Try different endpoints and versions
tests = [
    ("v0", "https://api.firecrawl.dev/v0/scrape?url=https://example.com"),
    ("v1", "https://api.firecrawl.dev/v1/scrape"),
    ("status", "https://api.firecrawl.dev/v0/status"),
]

for version, endpoint in tests:
    try:
        headers = {"Authorization": f"Bearer {api_key}"}
        if version == "v1":
            # v1 uses POST with JSON body
            response = requests.post(
                endpoint,
                headers={**headers, "Content-Type": "application/json"},
                json={"url": "https://example.com"},
                timeout=15
            )
        else:
            response = requests.get(endpoint, headers=headers, timeout=15)
        
        print(f"\n{version} - {endpoint}")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:200]}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {str(e)[:100]}")

# 3. RESEND API TEST
print("\n\n3. RESEND API TEST")
print("-" * 70)
api_key = os.getenv("RESEND_API_KEY")
print(f"API Key: {api_key[:20]}...{api_key[-10:]}")

# Try different endpoints
tests = [
    ("GET /api-keys", "GET", "https://api.resend.com/api-keys", None),
    ("GET /domains", "GET", "https://api.resend.com/domains", None),
    ("GET /emails (no id)", "GET", "https://api.resend.com/emails", None),
]

for name, method, endpoint, body in tests:
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        if method == "GET":
            response = requests.get(endpoint, headers=headers, timeout=10)
        else:
            response = requests.post(endpoint, headers=headers, json=body, timeout=10)
        
        print(f"\n{name}")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Response: Success - {list(data.keys()) if isinstance(data, dict) else 'data received'}")
        else:
            print(f"Response: {response.text[:200]}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {str(e)[:100]}")

print("\n" + "="*70)
print("TESTING COMPLETE")
print("="*70 + "\n")
