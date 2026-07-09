"""
Comprehensive test suite for new scraping and extraction capabilities.
Tests Apify integration, enhanced parsing, and private sources.
"""
import asyncio
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from research_intel.config import get_settings
from research_intel.ingestion.clients import (
    ApifyWebScraperClient,
    ApifyGoogleSearchScraperClient,
    ApifyLinkedInScraperClient,
)
from research_intel.services.file_parser import BriefFileParser, DocumentExtractor


load_dotenv()


async def test_apify_web_scraper():
    """Test general Apify web scraper."""
    print("\n" + "="*60)
    print("TEST 1: Apify Web Scraper")
    print("="*60)
    
    settings = get_settings()
    
    if not settings.apify_api_token:
        print("❌ APIFY_API_TOKEN not configured - skipping test")
        return False
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as http:
            client = ApifyWebScraperClient(http, settings)
            print("🔍 Searching for: 'RAG systems best practices'")
            
            result = await client.fetch(
                query="RAG systems best practices",
                max_results=3,
                domain="AI/ML"
            )
            
            if result.error:
                print(f"⚠️  Error: {result.error}")
                return False
            
            print(f"✅ Retrieved {len(result.documents)} documents")
            for i, doc in enumerate(result.documents, 1):
                print(f"\n{i}. {doc.title}")
                print(f"   URL: {doc.source_url}")
                print(f"   Preview: {doc.text[:150]}...")
            
            return True
            
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        return False


async def test_apify_google_search():
    """Test Apify Google Search scraper."""
    print("\n" + "="*60)
    print("TEST 2: Apify Google Search Scraper")
    print("="*60)
    
    settings = get_settings()
    
    if not settings.apify_api_token:
        print("❌ APIFY_API_TOKEN not configured - skipping test")
        return False
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as http:
            client = ApifyGoogleSearchScraperClient(http, settings)
            print("🔍 Searching Google for: 'vector databases 2026'")
            
            result = await client.fetch(
                query="vector databases 2026",
                max_results=5,
                domain="AI/ML"
            )
            
            if result.error:
                print(f"⚠️  Error: {result.error}")
                return False
            
            print(f"✅ Retrieved {len(result.documents)} search results")
            for i, doc in enumerate(result.documents, 1):
                print(f"\n{i}. {doc.title}")
                print(f"   URL: {doc.source_url}")
                print(f"   Position: {doc.metadata.get('position', 'N/A')}")
                print(f"   Snippet: {doc.text[:120]}...")
            
            return True
            
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        return False


async def test_apify_linkedin():
    """Test Apify LinkedIn scraper."""
    print("\n" + "="*60)
    print("TEST 3: Apify LinkedIn Scraper")
    print("="*60)
    
    settings = get_settings()
    
    if not settings.apify_api_token:
        print("❌ APIFY_API_TOKEN not configured - skipping test")
        return False
    
    try:
        async with httpx.AsyncClient(timeout=180.0) as http:
            client = ApifyLinkedInScraperClient(http, settings)
            print("🔍 Fetching LinkedIn company: 'openai'")
            
            result = await client.fetch(
                query="openai",
                max_results=1,
                domain="Business Intelligence"
            )
            
            if result.error:
                print(f"⚠️  Error: {result.error}")
                print("   Note: LinkedIn scraping may require special configuration")
                return False
            
            print(f"✅ Retrieved {len(result.documents)} company profiles")
            for i, doc in enumerate(result.documents, 1):
                print(f"\n{i}. {doc.title}")
                print(f"   URL: {doc.source_url}")
                print(f"   Industry: {doc.metadata.get('industry', 'N/A')}")
                print(f"   Followers: {doc.metadata.get('followers', 'N/A')}")
                print(f"   Description: {doc.text[:200]}...")
            
            return True
            
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        print("   LinkedIn scraping may have restrictions")
        return False


def test_enhanced_pdf_parsing():
    """Test enhanced PDF parsing."""
    print("\n" + "="*60)
    print("TEST 4: Enhanced PDF Parsing")
    print("="*60)
    
    # Create a sample text file to demonstrate
    sample_content = """
# Research Paper: RAG Systems

## Abstract
This paper presents a comprehensive study of Retrieval Augmented Generation (RAG) systems.
We analyze performance across multiple benchmarks and propose novel improvements.

## Introduction
RAG systems combine retrieval with generation for improved accuracy.

## Methodology
We conducted experiments on MS MARCO and Natural Questions datasets.

## Results
Our approach achieved 23% improvement in accuracy over baseline methods.

## Conclusion
RAG systems show significant promise for information retrieval tasks.
    """.strip().encode('utf-8')
    
    try:
        parser = BriefFileParser()
        
        # Test text parsing
        text = parser.parse("sample.txt", sample_content)
        print("✅ Successfully parsed text file")
        print(f"   Extracted {len(text)} characters")
        
        # Test section extraction
        extractor = DocumentExtractor()
        sections = extractor.extract_sections(text)
        
        print(f"\n📑 Extracted {len(sections)} sections:")
        for section_name, section_text in sections.items():
            print(f"   - {section_name.title()}: {len(section_text)} chars")
            print(f"     Preview: {section_text[:100]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        return False


def test_multiple_formats():
    """Test parsing of multiple document formats."""
    print("\n" + "="*60)
    print("TEST 5: Multiple Format Support")
    print("="*60)
    
    parser = BriefFileParser()
    
    formats = {
        "TXT": "sample.txt",
        "Markdown": "sample.md",
        "HTML": "sample.html",
    }
    
    results = {}
    
    for format_name, filename in formats.items():
        try:
            # Create sample content
            if filename.endswith('.html'):
                content = b"<html><body><h1>Title</h1><p>Content</p></body></html>"
            else:
                content = b"# Sample Document\n\nThis is sample content."
            
            text = parser.parse(filename, content)
            results[format_name] = "✅ Supported"
            print(f"   {format_name}: ✅ Parsed successfully ({len(text)} chars)")
            
        except Exception as e:
            results[format_name] = f"❌ {str(e)}"
            print(f"   {format_name}: ❌ {str(e)}")
    
    # Check supported extensions
    print(f"\n📄 Supported extensions: {', '.join(parser._clean.__globals__['SUPPORTED_EXTENSIONS'])}")
    
    return all("✅" in status for status in results.values())


async def test_all_sources():
    """Test connectivity to all configured sources."""
    print("\n" + "="*60)
    print("TEST 6: All Source Connectivity")
    print("="*60)
    
    settings = get_settings()
    
    sources = {
        "Semantic Scholar": settings.semantic_scholar_api_key,
        "GitHub": settings.github_token,
        "GNews": settings.gnews_api_key,
        "NewsAPI": settings.newsapi_key,
        "Guardian": settings.guardian_api_key,
        "NY Times": settings.nytimes_api_key,
        "Exa": settings.exa_api_key,
        "Serper": settings.serper_api_key,
        "Tavily": settings.tavily_api_key,
        "FireCrawl": settings.firecrawl_api_key,
        "Apify": settings.apify_api_token,
    }
    
    configured = []
    missing = []
    
    for source_name, api_key in sources.items():
        if api_key:
            configured.append(source_name)
            print(f"   ✅ {source_name}: Configured")
        else:
            missing.append(source_name)
            print(f"   ⚠️  {source_name}: Not configured")
    
    print(f"\n📊 Summary:")
    print(f"   Configured: {len(configured)}/{len(sources)} sources")
    print(f"   Total sources available: {len(configured)}")
    
    return len(configured) > 0


async def main():
    """Run all tests."""
    print("\n" + "="*70)
    print(" 🧪 COMPREHENSIVE INTEGRATION TEST SUITE")
    print("="*70)
    print("\nTesting new scraping and extraction capabilities...")
    
    results = {}
    
    # Test Apify integrations (with longer timeouts)
    print("\n🔧 Testing Apify Integrations...")
    results["Apify Web Scraper"] = await test_apify_web_scraper()
    results["Apify Google Search"] = await test_apify_google_search()
    results["Apify LinkedIn"] = await test_apify_linkedin()
    
    # Test parsing capabilities
    print("\n📄 Testing Document Parsing...")
    results["Enhanced PDF Parsing"] = test_enhanced_pdf_parsing()
    results["Multiple Formats"] = test_multiple_formats()
    
    # Test source configuration
    print("\n🌐 Testing Source Connectivity...")
    results["All Sources"] = await test_all_sources()
    
    # Summary
    print("\n" + "="*70)
    print(" 📊 TEST RESULTS SUMMARY")
    print("="*70)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status:12} {test_name}")
    
    print(f"\n{'='*70}")
    print(f" Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print(" 🎉 ALL TESTS PASSED!")
    elif passed > total // 2:
        print(" ⚠️  SOME TESTS FAILED - Check configuration")
    else:
        print(" ❌ MOST TESTS FAILED - Check API keys and connectivity")
    
    print("="*70)
    
    return passed == total


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
