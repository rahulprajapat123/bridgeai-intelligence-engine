"""Test Complete Research Paper Pipeline"""
import asyncio
from research_intel.config import Settings
from research_intel.db import SessionLocal
from research_intel.ingestion.orchestrator import IngestionOrchestrator
from research_intel.intelligence.credibility import CredibilityScorer
from research_intel.intelligence.embeddings import EmbeddingService
from research_intel.intelligence.extraction import ClaimExtractor
from research_intel.services.document_parser import DocumentParserService
from research_intel.models import ResearchItem, Claim

async def test_pipeline():
    print("\n" + "="*70)
    print("TESTING RESEARCH PAPER PIPELINE")
    print("="*70)
    
    settings = Settings()
    
    # Initialize services
    extractor = ClaimExtractor(settings)
    scorer = CredibilityScorer()
    embeddings = EmbeddingService(settings)
    parser = DocumentParserService(settings)
    
    orchestrator = IngestionOrchestrator(
        settings=settings,
        extractor=extractor,
        scorer=scorer,
        embeddings=embeddings,
        document_parser=parser
    )
    
    # Test ingestion with academic sources
    print("\n1️⃣  Ingesting Research Papers on 'agentic ai'...")
    print("-" * 70)
    
    with SessionLocal() as session:
        response = await orchestrator.ingest_topic(
            session,
            topic="agentic ai",
            domain="academic",
            max_per_source=3
        )
        
        print(f"\n   Status: {response.status}")
        print(f"   Documents Seen: {response.documents_seen}")
        print(f"   Documents Inserted: {response.documents_inserted}")
        print(f"   Claims Extracted: {response.claims_inserted}")
        
        if response.errors:
            print(f"\n   ⚠️  Errors: {len(response.errors)}")
            for error in response.errors[:3]:
                print(f"      - {error}")
    
    # Check what was stored
    print("\n2️⃣  Checking Stored Data...")
    print("-" * 70)
    
    with SessionLocal() as session:
        # Get latest research item
        item = session.query(ResearchItem).filter(
            ResearchItem.source_type == "academic"
        ).order_by(ResearchItem.ingestion_date.desc()).first()
        
        if item:
            print(f"\n   ✅ Found Research Paper:")
            print(f"      Title: {item.title[:80]}...")
            print(f"      Source: {item.source_name}")
            print(f"      Authors: {', '.join(item.authors[:3])}")
            print(f"      URL: {item.source_url}")
            print(f"      Credibility: {item.credibility_score}/100")
            print(f"      Domain Tags: {item.domain_tags}")
            print(f"\n      📄 Text Length: {len(item.raw_text)} chars")
            print(f"      Text Preview: {item.raw_text[:200]}...")
            
            print(f"\n      📊 Metadata:")
            for key, value in item.metadata_json.items():
                print(f"         {key}: {value}")
            
            # Check claims
            claims = session.query(Claim).filter(
                Claim.research_id == item.research_id
            ).all()
            
            print(f"\n      💡 Claims Extracted: {len(claims)}")
            if claims:
                for i, claim in enumerate(claims[:2], 1):
                    print(f"\n         Claim {i}:")
                    print(f"         Text: {claim.claim_text[:100]}...")
                    print(f"         Evidence: {claim.evidence_type}")
                    print(f"         Confidence: {claim.confidence}")
            
            # Check what's MISSING for complete analysis
            print(f"\n3️⃣  Missing AI Analysis Fields:")
            print("-" * 70)
            
            missing_fields = {
                "Summary": "No dedicated summary field",
                "Key Findings": "Only claims, not structured findings",
                "Business Impact": "No business impact analysis",
                "Technologies": "Not extracted systematically",
                "Keywords": "No keyword extraction",
                "Industry": "Domain tags exist but not industry-specific",
                "Atomic Insights": "Claim-level but not insight-level",
            }
            
            for field, status in missing_fields.items():
                print(f"      ❌ {field}: {status}")
            
        else:
            print("   ❌ No academic papers found")
    
    print("\n" + "="*70)
    print("PIPELINE ANALYSIS COMPLETE")
    print("="*70)
    
    print("\n📋 Current Pipeline:")
    print("   ✅ Search across 5 academic sources")
    print("   ✅ Collect metadata (title, authors, abstract, citations)")
    print("   ✅ Remove duplicates")
    print("   ⚠️  Ranking (basic by citation count)")
    print("   ⚠️  PDF Download (parsing exists, but not auto-download)")
    print("   ✅ Parse documents (PDF, HTML, text)")
    print("   ⚠️  AI Analysis (ONLY claim extraction, NOT comprehensive)")
    print("   ✅ Store in cloud database (PostgreSQL)")
    print("   ⚠️  Knowledge Base (data stored but lacks rich analysis)")
    
    print("\n❌ MISSING COMPONENTS:")
    print("   1. Automatic PDF download from arXiv/OpenAlex")
    print("   2. Comprehensive AI analysis:")
    print("      - Executive Summary")
    print("      - Key Findings")
    print("      - Business Impact Assessment")
    print("      - Technology Extraction")
    print("      - Keyword/Topic Extraction")
    print("      - Industry Classification")
    print("      - Atomic Insights Generation")
    print("   3. Better relevance ranking algorithm")
    print("   4. Structured storage for analysis results")

if __name__ == "__main__":
    asyncio.run(test_pipeline())
