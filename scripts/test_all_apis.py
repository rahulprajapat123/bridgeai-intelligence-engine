"""
Test all API keys and services from .env file
"""
import os
import sys
import requests
from dotenv import load_dotenv
from datetime import datetime
import json

# Load environment variables
load_dotenv()

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_status(service, status, message=""):
    """Print colored status message"""
    color = GREEN if status == "OK" else RED if status == "FAIL" else YELLOW
    print(f"{color}[{status}]{RESET} {service:30s} {message}")

def test_semantic_scholar():
    """Test Semantic Scholar API"""
    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    if not api_key:
        print_status("Semantic Scholar", "SKIP", "No API key found")
        return False
    
    try:
        headers = {"x-api-key": api_key}
        response = requests.get(
            "https://api.semanticscholar.org/graph/v1/paper/search?query=retrieval",
            headers=headers,
            timeout=10
        )
        if response.status_code == 200:
            print_status("Semantic Scholar", "OK", f"API working")
            return True
        else:
            print_status("Semantic Scholar", "FAIL", f"Status: {response.status_code}")
            return False
    except Exception as e:
        print_status("Semantic Scholar", "FAIL", f"Error: {str(e)[:50]}")
        return False

def test_openalex():
    """Test OpenAlex API"""
    email = os.getenv("OPENALEX_CONTACT_EMAIL")
    if not email:
        print_status("OpenAlex", "SKIP", "No contact email found")
        return False
    
    try:
        response = requests.get(
            f"https://api.openalex.org/works?search=machine+learning&mailto={email}",
            timeout=10
        )
        if response.status_code == 200:
            print_status("OpenAlex", "OK", "API working (no key required)")
            return True
        else:
            print_status("OpenAlex", "FAIL", f"Status: {response.status_code}")
            return False
    except Exception as e:
        print_status("OpenAlex", "FAIL", f"Error: {str(e)[:50]}")
        return False

def test_huggingface():
    """Test HuggingFace API"""
    token = os.getenv("HUGGINGFACE_TOKEN")
    if not token:
        print_status("HuggingFace", "SKIP", "No token found")
        return False
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            "https://huggingface.co/api/whoami-v2",
            headers=headers,
            timeout=10
        )
        if response.status_code == 200:
            print_status("HuggingFace", "OK", "Token valid")
            return True
        else:
            print_status("HuggingFace", "FAIL", f"Status: {response.status_code}")
            return False
    except Exception as e:
        print_status("HuggingFace", "FAIL", f"Error: {str(e)[:50]}")
        return False

def test_gnews():
    """Test GNews API"""
    api_key = os.getenv("GNEWS_API_KEY")
    if not api_key:
        print_status("GNews", "SKIP", "No API key found")
        return False
    
    try:
        response = requests.get(
            f"https://gnews.io/api/v4/search?q=technology&token={api_key}&lang=en&max=1",
            timeout=10
        )
        if response.status_code == 200:
            print_status("GNews", "OK", "API working")
            return True
        else:
            print_status("GNews", "FAIL", f"Status: {response.status_code} - {response.text[:50]}")
            return False
    except Exception as e:
        print_status("GNews", "FAIL", f"Error: {str(e)[:50]}")
        return False

def test_newsapi():
    """Test NewsAPI"""
    api_key = os.getenv("NEWSAPI_KEY")
    if not api_key:
        print_status("NewsAPI", "SKIP", "No API key found")
        return False
    
    try:
        response = requests.get(
            f"https://newsapi.org/v2/top-headlines?country=us&pageSize=1&apiKey={api_key}",
            timeout=10
        )
        if response.status_code == 200:
            print_status("NewsAPI", "OK", "API working")
            return True
        else:
            print_status("NewsAPI", "FAIL", f"Status: {response.status_code} - {response.text[:50]}")
            return False
    except Exception as e:
        print_status("NewsAPI", "FAIL", f"Error: {str(e)[:50]}")
        return False

def test_github():
    """Test GitHub Token"""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print_status("GitHub", "SKIP", "No token found")
        return False
    
    try:
        headers = {"Authorization": f"token {token}"}
        response = requests.get(
            "https://api.github.com/user",
            headers=headers,
            timeout=10
        )
        if response.status_code == 200:
            print_status("GitHub", "OK", "Token valid")
            return True
        else:
            print_status("GitHub", "FAIL", f"Status: {response.status_code}")
            return False
    except Exception as e:
        print_status("GitHub", "FAIL", f"Error: {str(e)[:50]}")
        return False

def test_apify():
    """Test Apify API"""
    token = os.getenv("APIFY_API_TOKEN")
    if not token:
        print_status("Apify", "SKIP", "No token found")
        return False
    
    try:
        # Use /v2/acts endpoint instead of /v2/user
        response = requests.get(
            f"https://api.apify.com/v2/acts?token={token}",
            timeout=10
        )
        if response.status_code == 200:
            print_status("Apify", "OK", "Token valid")
            return True
        else:
            print_status("Apify", "FAIL", f"Status: {response.status_code}")
            return False
    except Exception as e:
        print_status("Apify", "FAIL", f"Error: {str(e)[:50]}")
        return False

def test_openai():
    """Test OpenAI API"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print_status("OpenAI", "SKIP", "No API key found")
        return False
    
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        response = requests.get(
            "https://api.openai.com/v1/models",
            headers=headers,
            timeout=10
        )
        if response.status_code == 200:
            print_status("OpenAI", "OK", "API key valid")
            return True
        else:
            print_status("OpenAI", "FAIL", f"Status: {response.status_code}")
            return False
    except Exception as e:
        print_status("OpenAI", "FAIL", f"Error: {str(e)[:50]}")
        return False

def test_guardian():
    """Test Guardian API"""
    api_key = os.getenv("GUARDIAN_API_KEY")
    if not api_key:
        print_status("Guardian", "SKIP", "No API key found")
        return False
    
    try:
        response = requests.get(
            f"https://content.guardianapis.com/search?api-key={api_key}&page-size=1",
            timeout=10
        )
        if response.status_code == 200:
            print_status("Guardian", "OK", "API working")
            return True
        else:
            print_status("Guardian", "FAIL", f"Status: {response.status_code}")
            return False
    except Exception as e:
        print_status("Guardian", "FAIL", f"Error: {str(e)[:50]}")
        return False

def test_nytimes():
    """Test NY Times API"""
    api_key = os.getenv("NYTIMES_API_KEY")
    if not api_key:
        print_status("NY Times", "SKIP", "No API key found")
        return False
    
    try:
        response = requests.get(
            f"https://api.nytimes.com/svc/search/v2/articlesearch.json?q=technology&api-key={api_key}",
            timeout=10
        )
        if response.status_code == 200:
            print_status("NY Times", "OK", "API working")
            return True
        else:
            print_status("NY Times", "FAIL", f"Status: {response.status_code}")
            return False
    except Exception as e:
        print_status("NY Times", "FAIL", f"Error: {str(e)[:50]}")
        return False

def test_exa():
    """Test Exa.ai API"""
    api_key = os.getenv("EXA_API_KEY")
    if not api_key:
        print_status("Exa.ai", "SKIP", "No API key found")
        return False
    
    try:
        headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json"
        }
        data = {
            "query": "machine learning",
            "numResults": 1
        }
        response = requests.post(
            "https://api.exa.ai/search",
            headers=headers,
            json=data,
            timeout=10
        )
        if response.status_code == 200:
            print_status("Exa.ai", "OK", "API working")
            return True
        else:
            print_status("Exa.ai", "FAIL", f"Status: {response.status_code}")
            return False
    except Exception as e:
        print_status("Exa.ai", "FAIL", f"Error: {str(e)[:50]}")
        return False

def test_tavily():
    """Test Tavily API"""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        print_status("Tavily", "SKIP", "No API key found")
        return False
    
    try:
        headers = {"Content-Type": "application/json"}
        data = {
            "api_key": api_key,
            "query": "technology news",
            "max_results": 1
        }
        response = requests.post(
            "https://api.tavily.com/search",
            headers=headers,
            json=data,
            timeout=10
        )
        if response.status_code == 200:
            print_status("Tavily", "OK", "API working")
            return True
        else:
            print_status("Tavily", "FAIL", f"Status: {response.status_code}")
            return False
    except Exception as e:
        print_status("Tavily", "FAIL", f"Error: {str(e)[:50]}")
        return False

def test_serper():
    """Test Serper API"""
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        print_status("Serper", "SKIP", "No API key found")
        return False
    
    try:
        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json"
        }
        data = {"q": "technology"}
        response = requests.post(
            "https://google.serper.dev/search",
            headers=headers,
            json=data,
            timeout=10
        )
        if response.status_code == 200:
            print_status("Serper", "OK", "API working")
            return True
        else:
            print_status("Serper", "FAIL", f"Status: {response.status_code}")
            return False
    except Exception as e:
        print_status("Serper", "FAIL", f"Error: {str(e)[:50]}")
        return False

def test_serpapi():
    """Test SerpAPI"""
    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key:
        print_status("SerpAPI", "SKIP", "No API key found")
        return False
    
    try:
        response = requests.get(
            f"https://serpapi.com/search?q=technology&api_key={api_key}&engine=google",
            timeout=10
        )
        if response.status_code == 200:
            print_status("SerpAPI", "OK", "API working")
            return True
        else:
            print_status("SerpAPI", "FAIL", f"Status: {response.status_code}")
            return False
    except Exception as e:
        print_status("SerpAPI", "FAIL", f"Error: {str(e)[:50]}")
        return False

def test_firecrawl():
    """Test Firecrawl API"""
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        print_status("Firecrawl", "SKIP", "No API key found")
        return False
    
    try:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        # Use v1/scrape endpoint (search endpoint doesn't exist)
        response = requests.post(
            "https://api.firecrawl.dev/v1/scrape",
            headers=headers,
            json={"url": "https://example.com", "formats": ["markdown"]},
            timeout=15
        )
        if response.status_code in [200, 201]:
            print_status("Firecrawl", "OK", "API working (scrape endpoint)")
            return True
        else:
            print_status("Firecrawl", "FAIL", f"Status: {response.status_code}")
            return False
    except Exception as e:
        print_status("Firecrawl", "FAIL", f"Error: {str(e)[:50]}")
        return False

def test_resend():
    """Test Resend Email API"""
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        print_status("Resend", "SKIP", "No API key found")
        return False
    
    try:
        headers = {"Authorization": f"Bearer {api_key}"}
        response = requests.get(
            "https://api.resend.com/api-keys",
            headers=headers,
            timeout=10
        )
        if response.status_code == 200:
            print_status("Resend", "OK", "API key valid")
            return True
        elif response.status_code == 401:
            # Check if it's a send-only key (expected behavior)
            try:
                error_data = response.json()
                if error_data.get("name") == "restricted_api_key":
                    print_status("Resend", "OK", "Send-only key (valid)")
                    return True
            except:
                pass
            print_status("Resend", "FAIL", f"Status: {response.status_code}")
            return False
        else:
            print_status("Resend", "FAIL", f"Status: {response.status_code}")
            return False
    except Exception as e:
        print_status("Resend", "FAIL", f"Error: {str(e)[:50]}")
        return False

def test_database():
    """Test Database Connection"""
    conn_string = os.getenv("DATABASE_CONNECTION_STRING")
    if not conn_string:
        print_status("Database", "SKIP", "No connection string found")
        return False
    
    try:
        import psycopg2
        conn = psycopg2.connect(conn_string)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        print_status("Database", "OK", "Connection successful")
        return True
    except ImportError:
        print_status("Database", "WARN", "psycopg2 not installed, skipping")
        return None
    except Exception as e:
        print_status("Database", "FAIL", f"Error: {str(e)[:50]}")
        return False

def main():
    """Run all API tests"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}API Testing Suite - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    tests = [
        ("Semantic Scholar", test_semantic_scholar),
        ("OpenAlex", test_openalex),
        ("HuggingFace", test_huggingface),
        ("GNews", test_gnews),
        ("NewsAPI", test_newsapi),
        ("GitHub", test_github),
        ("Apify", test_apify),
        ("OpenAI", test_openai),
        ("Guardian", test_guardian),
        ("NY Times", test_nytimes),
        ("Exa.ai", test_exa),
        ("Tavily", test_tavily),
        ("Serper", test_serper),
        ("SerpAPI", test_serpapi),
        ("Firecrawl", test_firecrawl),
        ("Resend", test_resend),
        ("Database", test_database),
    ]
    
    results = {}
    for name, test_func in tests:
        result = test_func()
        results[name] = result
    
    # Summary
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}Summary:{RESET}")
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)
    
    print(f"  {GREEN}Passed:{RESET}  {passed}")
    print(f"  {RED}Failed:{RESET}  {failed}")
    print(f"  {YELLOW}Skipped:{RESET} {skipped}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    # List failed APIs
    if failed > 0:
        print(f"{RED}Failed APIs:{RESET}")
        for name, result in results.items():
            if result is False:
                print(f"  - {name}")
        print()

if __name__ == "__main__":
    main()
