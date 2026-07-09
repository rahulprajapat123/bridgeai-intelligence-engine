"""
Quick verification test for core capabilities.
Tests what's working right now.
"""
import asyncio
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from research_intel.config import get_settings
from research_intel.ingestion.clients import (
    SerperClient,
    ExaClient,
    TavilyClient,
    FirecrawlClient,
    GNewsClient,
)
from research_intel.services.file_parser import BriefFileParser, DocumentExtractor


load_dotenv()


async def test_working_scrapers():
    """Test working web scrapers."""
    print("\n" + "="*60)
    print("🌐 Testing Working Web Scrapers")
    print("="*60)
    
    settings = get_settings()
    results = {}
    
    async with httpx.AsyncClient(timeout=30.0) as http:
        # Test Serper (Google Search)
        if settings.serper_api_key:
            try:
                print("\n1. Testing Serper (Google Search)...")
                client = SerperClient(http, settings)
                result = await client.fetch("RAG systems 2026", max_results=3)
                if not result.error:
                    print(f"   ✅ Success: {len(result.documents)} results")
                    for doc in result.documents[:2]:
                        print(f"      - {doc.title[:60]}...")
                    results["Serper"] = True
                else:
                    print(f"   ⚠️  Error: {result.error}")
                    results["Serper"] = False
            except Exception as e:
                print(f"   ❌ Failed: {str(e)}")
                results["Serper"] = False
        
        # Test Exa (Neural Search)
        if settings.exa_api_key:
            try:
                print("\n2. Testing Exa.ai (Neural Search)...")
                client = ExaClient(http, settings)
                result = await client.fetch("vector databases", max_results=3)
                if not result.error:
                    print(f"   ✅ Success: {len(result.documents)} results")
                    for doc in result.documents[:2]:
                        print(f"      - {doc.title[:60]}...")
                    results["Exa"] = True
                else:
                    print(f"   ⚠️  Error: {result.error}")
                    results["Exa"] = False
            except Exception as e:
                print(f"   ❌ Failed: {str(e)}")
                results["Exa"] = False
        
        # Test Tavily
        if settings.tavily_api_key:
            try:
                print("\n3. Testing Tavily (Advanced Search)...")
                client = TavilyClient(http, settings)
                result = await client.fetch("semantic search", max_results=3)
                if not result.error:
                    print(f"   ✅ Success: {len(result.documents)} results")
                    for doc in result.documents[:2]:
                        print(f"      - {doc.title[:60]}...")
                    results["Tavily"] = True
                else:
                    print(f"   ⚠️  Error: {result.error}")
                    results["Tavily"] = False
            except Exception as e:
                print(f"   ❌ Failed: {str(e)}")
                results["Tavily"] = False
        
        # Test FireCrawl
        if settings.firecrawl_api_key:
            try:
                print("\n4. Testing FireCrawl (Web Content)...")
                client = FirecrawlClient(http, settings)
                result = await client.fetch("embeddings", max_results=3)
                if not result.error:
                    print(f"   ✅ Success: {len(result.documents)} results")
                    for doc in result.documents[:2]:
                        print(f"      - {doc.title[:60]}...")
                    results["FireCrawl"] = True
                else:
                    print(f"   ⚠️  Error: {result.error}")
                    results["FireCrawl"] = False
            except Exception as e:
                print(f"   ❌ Failed: {str(e)}")
                results["FireCrawl"] = False
        
        # Test GNews
        if settings.gnews_api_key:
            try:
                print("\n5. Testing GNews (News Articles)...")
                client = GNewsClient(http, settings)
                result = await client.fetch("artificial intelligence", max_results=3)
                if not result.error:
                    print(f"   ✅ Success: {len(result.documents)} results")
                    for doc in result.documents[:2]:
                        print(f"      - {doc.title[:60]}...")
                    results["GNews"] = True
                else:
                    print(f"   ⚠️  Error: {result.error}")
                    results["GNews"] = False
            except Exception as e:
                print(f"   ❌ Failed: {str(e)}")
                results["GNews"] = False
    
    return results


def test_document_parsing():
    """Test enhanced document parsing."""
    print("\n" + "="*60)
    print("📄 Testing Document Parsing")
    print("="*60)
    
    parser = BriefFileParser()
    extractor = DocumentExtractor()
    
    # Test with sample content
    sample_pdf_text = """
    Research Paper: Advanced RAG Systems
    
    Abstract: This paper presents novel approaches to Retrieval Augmented Generation.
    We demonstrate 23% improvement over baseline methods.
    
    Introduction: RAG systems combine retrieval with generation for better accuracy.
    
    Methodology: We tested on MS MARCO and Natural Questions datasets.
    
    Results: Our hybrid approach achieved significant improvements.
    
    Conclusion: RAG systems show promise for information retrieval tasks.
    """
    
    try:
        # Test text parsing
        text = parser.parse("sample.txt", sample_pdf_text.strip().encode())
        print(f"\n✅ Text parsing: {len(text)} characters extracted")
        
        # Test section extraction
        sections = extractor.extract_sections(text)
        print(f"✅ Section extraction: {len(sections)} sections found")
        for name in sections.keys():
            print(f"   - {name.title()}")
        
        # Test multiple formats
        formats = {
            ".txt": b"Sample text content",
            ".md": b"# Markdown\n\nContent here",
            ".html": b"<html><body><h1>Title</h1><p>Content</p></body></html>",
        }
        
        print(f"\n✅ Format support:")
        for ext, content in formats.items():
            text = parser.parse(f"sample{ext}", content)
            print(f"   - {ext}: {len(text)} chars")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Parsing failed: {str(e)}")
        return False


def check_configuration():
    """Check what's configured."""
    print("\n" + "="*60)
    print("⚙️  Configuration Check")
    print("="*60)
    
    settings = get_settings()
    
    configured = {
        "OpenAI": bool(settings.openai_api_key),
        "Semantic Scholar": bool(settings.semantic_scholar_api_key),
        "GitHub": bool(settings.github_token),
        "GNews": bool(settings.gnews_api_key),
        "NewsAPI": bool(settings.newsapi_key),
        "Guardian": bool(settings.guardian_api_key),
        "NY Times": bool(settings.nytimes_api_key),
        "Exa.ai": bool(settings.exa_api_key),
        "Serper": bool(settings.serper_api_key),
        "Tavily": bool(settings.tavily_api_key),
        "FireCrawl": bool(settings.firecrawl_api_key),
        "Apify": bool(settings.apify_api_token),
    }
    
    for name, status in configured.items():
        if status:
            print(f"   ✅ {name}")
        else:
            print(f"   ⚠️  {name} (not configured)")
    
    total = sum(configured.values())
    print(f"\n📊 Total: {total}/{len(configured)} sources configured")
    
    return configured


async def main():
    """Run focused tests."""
    print("\n" + "="*70)
    print(" 🧪 FOCUSED CAPABILITY TEST")
    print("="*70)
    
    # Check configuration
    config = check_configuration()
    
    # Test working scrapers
    scraper_results = await test_working_scrapers()
    
    # Test document parsing
    parsing_ok = test_document_parsing()
    
    # Summary
    print("\n" + "="*70)
    print(" 📊 SUMMARY")
    print("="*70)
    
    working_sources = sum(scraper_results.values())
    total_tested = len(scraper_results)
    
    print(f"\n✅ Working Sources: {working_sources}/{total_tested}")
    for name, status in scraper_results.items():
        print(f"   {'✅' if status else '❌'} {name}")
    
    print(f"\n{'✅' if parsing_ok else '❌'} Document Parsing: {'Working' if parsing_ok else 'Failed'}")
    
    print(f"\n📈 Overall Readiness:")
    print(f"   - Data Sources: {sum(config.values())}/12 configured")
    print(f"   - Web Scrapers: {working_sources}/{total_tested} tested & working")
    print(f"   - Document Parsing: {'✅ Ready' if parsing_ok else '❌ Issues'}")
    
    if working_sources >= total_tested // 2 and parsing_ok:
        print(f"\n✅ System is OPERATIONAL - Ready for use!")
    else:
        print(f"\n⚠️  Some features need configuration")
    
    print("="*70)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted")
    except Exception as e:
        print(f"\n\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
