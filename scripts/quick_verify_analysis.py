"""Quick test of research analysis on existing data"""
from research_intel.db import SessionLocal
from research_intel.models import ResearchItem
import json

def test_existing_papers():
    print("\n" + "="*80)
    print("CHECKING RESEARCH PAPERS IN DATABASE")
    print("="*80)
    
    with SessionLocal() as session:
        # Get all academic papers
        papers = session.query(ResearchItem).filter(
            ResearchItem.source_type == "academic"
        ).order_by(ResearchItem.ingestion_date.desc()).limit(5).all()
        
        print(f"\n📊 Found {len(papers)} recent academic papers")
        print("-" * 80)
        
        for i, paper in enumerate(papers, 1):
            print(f"\n{i}. {paper.title[:70]}...")
            print(f"   Source: {paper.source_name}")
            print(f"   Credibility: {paper.credibility_score}/100")
            
            meta = paper.metadata_json
            
            # Check if AI analysis exists
            if meta.get("analyzed"):
                print(f"\n   ✅ AI ANALYSIS EXISTS!")
                print(f"   Summary: {meta.get('ai_summary', 'N/A')[:100]}...")
                print(f"   Key Findings: {len(meta.get('key_findings', []))} findings")
                print(f"   Technologies: {', '.join(meta.get('technologies', [])[:5])}")
                print(f"   Industries: {', '.join(meta.get('industries', []))}")
                print(f"   Atomic Insights: {len(meta.get('atomic_insights', []))} insights")
            else:
                print(f"\n   ❌ No AI analysis (old data or analysis disabled)")
                print(f"   Metadata fields: {list(meta.keys())}")
        
        # Count analyzed vs not
        total = session.query(ResearchItem).filter(
            ResearchItem.source_type == "academic"
        ).count()
        
        print(f"\n" + "="*80)
        print(f"TOTAL ACADEMIC PAPERS IN DATABASE: {total}")
        print("="*80)
        
        print(f"\n💡 To test new AI analysis:")
        print(f"   1. The ResearchPaperAnalyzer has been implemented")
        print(f"   2. The IngestionOrchestrator now calls it automatically")
        print(f"   3. Run a new ingestion to see it in action:")
        print(f"\n   from research_intel.api.routes import ingest_topic")
        print(f"   response = await ingest_topic(topic='your query', domain='academic')")
        print(f"\n   Or use the API:")
        print(f"   POST http://localhost:8000/api/ingest")
        print(f"   {{\"topic\": \"your query\", \"domain\": \"academic\"}}")

if __name__ == "__main__":
    test_existing_papers()
