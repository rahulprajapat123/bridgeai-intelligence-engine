"""
Comprehensive API Source Testing Script
Tests all registered sources and fetches 3-5 items from each to identify issues
"""
import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx

from research_intel.config import Settings
from research_intel.ingestion.clients import build_clients


class SourceTestResult:
    def __init__(self, name: str, route: str, source_type: str):
        self.name = name
        self.route = route
        self.source_type = source_type
        self.status = "unknown"
        self.items_fetched = 0
        self.error_message = ""
        self.duration_ms = 0
        self.api_key_status = "unknown"
        self.sample_titles = []


async def test_source(client, test_query: str) -> SourceTestResult:
    """Test a single source and return results"""
    result = SourceTestResult(client.name, client.route_name, client.source_type)
    
    # Check API key status
    if hasattr(client, 'api_key'):
        result.api_key_status = "present" if client.api_key else "missing"
    elif hasattr(client, 'enabled'):
        result.api_key_status = "enabled" if client.enabled() else "disabled"
    else:
        result.api_key_status = "no key required"
    
    start_time = datetime.now()
    
    try:
        # Attempt to fetch 5 items
        fetch_result = await asyncio.wait_for(
            client.fetch(test_query, max_results=5, domain="Test"),
            timeout=30.0
        )
        
        end_time = datetime.now()
        result.duration_ms = int((end_time - start_time).total_seconds() * 1000)
        
        if fetch_result.error:
            result.status = "degraded" if "reachable" in fetch_result.error.lower() else "failed"
            result.error_message = fetch_result.error[:100]
        elif len(fetch_result.documents) == 0:
            result.status = "no_results"
            result.error_message = "Source reachable but returned 0 items"
        else:
            result.status = "healthy"
            result.items_fetched = len(fetch_result.documents)
            result.sample_titles = [doc.title[:80] for doc in fetch_result.documents[:3]]
            
    except asyncio.TimeoutError:
        result.status = "timeout"
        result.error_message = "Request timed out after 30 seconds"
        result.duration_ms = 30000
    except Exception as e:
        result.status = "failed"
        result.error_message = str(e)[:100]
        end_time = datetime.now()
        result.duration_ms = int((end_time - start_time).total_seconds() * 1000)
    
    return result


async def test_all_sources():
    """Test all registered sources"""
    print("="*80)
    print("Intelligence Engine - Comprehensive Source Testing")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    settings = Settings()
    
    # Test queries for different source types
    test_queries = {
        "academic": "artificial intelligence machine learning",
        "news": "artificial intelligence latest updates",
        "industry": "AI tools latest releases",
        "blog": "AI technology trends",
        "social": "artificial intelligence discussion",
        "package": "ai machine-learning",
    }
    
    timeout = httpx.Timeout(30.0, connect=10.0)
    
    results: list[SourceTestResult] = []
    
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as http:
        clients = build_clients(http, settings)
        
        print(f"\nTesting {len(clients)} sources...\n")
        
        # Test sources sequentially to avoid overwhelming rate limits
        for i, client in enumerate(clients, 1):
            print(f"{i}/{len(clients)} Testing {client.name}...", end=" ", flush=True)
            
            query = test_queries.get(client.source_type, "artificial intelligence")
            result = await test_source(client, query)
            results.append(result)
            
            # Status indicator
            status_emoji = {
                "healthy": "✓",
                "degraded": "⚠",
                "failed": "✗",
                "timeout": "T",
                "no_results": "0",
            }
            print(f"{status_emoji.get(result.status, '?')} {result.status.upper()}")
            
            # Small delay to respect rate limits
            if i < len(clients):
                await asyncio.sleep(0.5)
    
    return results


def print_summary(results: list[SourceTestResult]):
    """Print a detailed summary of test results"""
    
    # Summary statistics
    healthy = [r for r in results if r.status == "healthy"]
    degraded = [r for r in results if r.status == "degraded"]
    failed = [r for r in results if r.status == "failed"]
    timeout = [r for r in results if r.status == "timeout"]
    no_results = [r for r in results if r.status == "no_results"]
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Healthy: {len(healthy)} | Degraded: {len(degraded)} | Failed: {len(failed)} | Timeout: {len(timeout)} | No Results: {len(no_results)}")
    print("="*80)
    
    # Healthy sources
    if healthy:
        print("\n✓ HEALTHY SOURCES")
        print("-" * 80)
        print(f"{'Source':<30} {'Type':<12} {'Items':<6} {'Time(ms)':<10} {'Sample Title'}")
        print("-" * 80)
        for r in sorted(healthy, key=lambda x: x.duration_ms):
            sample = r.sample_titles[0][:40] if r.sample_titles else ""
            print(f"{r.name:<30} {r.source_type:<12} {r.items_fetched:<6} {r.duration_ms:<10} {sample}")
    
    # Degraded sources
    if degraded:
        print("\n⚠ DEGRADED SOURCES (Reachable but issues)")
        print("-" * 80)
        print(f"{'Source':<30} {'Type':<12} {'API Key':<15} {'Issue'}")
        print("-" * 80)
        for r in sorted(degraded, key=lambda x: x.name):
            print(f"{r.name:<30} {r.source_type:<12} {r.api_key_status:<15} {r.error_message[:50]}")
    
    # Failed sources
    if failed:
        print("\n✗ FAILED SOURCES")
        print("-" * 80)
        print(f"{'Source':<30} {'Type':<12} {'API Key':<15} {'Error'}")
        print("-" * 80)
        for r in sorted(failed, key=lambda x: x.name):
            print(f"{r.name:<30} {r.source_type:<12} {r.api_key_status:<15} {r.error_message[:50]}")
    
    # Timeout sources
    if timeout:
        print("\nT TIMEOUT SOURCES")
        print("-" * 80)
        print(f"{'Source':<30} {'Type':<12} {'Issue'}")
        print("-" * 80)
        for r in sorted(timeout, key=lambda x: x.name):
            print(f"{r.name:<30} {r.source_type:<12} Request exceeded 30 second timeout")
    
    # No results sources
    if no_results:
        print("\n0 NO RESULTS SOURCES (Working but no data)")
        print("-" * 80)
        print(f"{'Source':<30} {'Type':<12} {'Note'}")
        print("-" * 80)
        for r in sorted(no_results, key=lambda x: x.name):
            print(f"{r.name:<30} {r.source_type:<12} Query returned 0 items")
    
    # Categorized analysis
    print("\n📊 ANALYSIS BY ISSUE TYPE")
    print("="*80)
    
    api_key_missing = [r for r in results if r.api_key_status == "missing" and r.status != "healthy"]
    if api_key_missing:
        print(f"\nAPI Key Missing ({len(api_key_missing)}):")
        for r in api_key_missing:
            print(f"  • {r.name} - {r.error_message}")
    
    rate_limited = [r for r in results if "rate" in r.error_message.lower() or "limit" in r.error_message.lower()]
    if rate_limited:
        print(f"\nRate Limited ({len(rate_limited)}):")
        for r in rate_limited:
            print(f"  • {r.name} - {r.error_message}")
    
    auth_issues = [r for r in results if any(x in r.error_message.lower() for x in ["auth", "unauthorized", "forbidden", "401", "403"])]
    if auth_issues:
        print(f"\nAuthentication Issues ({len(auth_issues)}):")
        for r in auth_issues:
            print(f"  • {r.name} - {r.error_message}")
    
    network_issues = [r for r in results if any(x in r.error_message.lower() for x in ["timeout", "connection", "network", "dns"])]
    if network_issues:
        print(f"\nNetwork Issues ({len(network_issues)}):")
        for r in network_issues:
            print(f"  • {r.name} - {r.error_message}")
    
    # Recommendations
    print("\n💡 RECOMMENDATIONS")
    print("="*80)
    if api_key_missing:
        print("1. Configure missing API keys in .env file")
    if rate_limited:
        print("2. Review rate limits and consider upgrading plans or adding delays")
    if auth_issues:
        print("3. Verify API keys are valid and have proper permissions")
    if len(failed) + len(timeout) > len(results) * 0.3:
        print("4. High failure rate - check network connectivity and API service status")
    
    print("\n" + "="*80 + "\n")


async def main():
    try:
        results = await test_all_sources()
        print_summary(results)
        
        # Exit code based on results
        failed_count = len([r for r in results if r.status in ["failed", "timeout"]])
        sys.exit(1 if failed_count > 0 else 0)
        
    except KeyboardInterrupt:
        print("\nTesting interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
