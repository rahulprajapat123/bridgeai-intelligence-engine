"""
Check database contents and show what data exists
"""
import sys
from sqlalchemy import text, inspect
from research_intel.db import engine, SessionLocal
from research_intel.models import (
    ResearchItem, Claim, IngestionRun, IngestionBatch, 
    DailyRawItem, DailySummary, DailySourceRun
)

def check_database():
    """Check what data is in the database"""
    session = SessionLocal()
    
    print("\n" + "="*70)
    print("DATABASE CONTENTS SUMMARY")
    print("="*70)
    print(f"Database: Neon PostgreSQL (Cloud)")
    print(f"Connection: ep-still-violet-aooo7qxw.c-2.ap-southeast-1.aws.neon.tech")
    print("="*70)
    
    try:
        # Check tables exist
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        print(f"\n📊 Tables in database: {len(tables)}")
        for table in sorted(tables):
            print(f"  - {table}")
        
        print("\n" + "="*70)
        print("DATA COUNTS")
        print("="*70)
        
        # Research Intelligence (Main brief workflow)
        research_count = session.query(ResearchItem).count()
        claims_count = session.query(Claim).count()
        runs_count = session.query(IngestionRun).count()
        
        print(f"\n📚 Research Intelligence (Brief Workflow):")
        print(f"  - Research Items: {research_count}")
        print(f"  - Claims Extracted: {claims_count}")
        print(f"  - Ingestion Runs: {runs_count}")
        
        if research_count > 0:
            latest = session.query(ResearchItem).order_by(ResearchItem.ingestion_date.desc()).first()
            print(f"  - Latest item: {latest.title[:60]}...")
            print(f"  - Source: {latest.source_name}")
            print(f"  - Date: {latest.ingestion_date}")
        
        # Daily Intelligence
        batches_count = session.query(IngestionBatch).count()
        daily_items_count = session.query(DailyRawItem).count()
        summaries_count = session.query(DailySummary).count()
        source_runs_count = session.query(DailySourceRun).count()
        
        print(f"\n📰 Daily Intelligence:")
        print(f"  - Batches: {batches_count}")
        print(f"  - Raw Items: {daily_items_count}")
        print(f"  - Summaries: {summaries_count}")
        print(f"  - Source Runs: {source_runs_count}")
        
        if batches_count > 0:
            latest_batch = session.query(IngestionBatch).order_by(IngestionBatch.created_at.desc()).first()
            print(f"  - Latest batch: {latest_batch.id}")
            print(f"  - Status: {latest_batch.status}")
            print(f"  - Created: {latest_batch.created_at}")
            print(f"  - Items: {latest_batch.unique_items} unique, {latest_batch.duplicate_items} duplicates")
        
        # Show recent daily items
        if daily_items_count > 0:
            print(f"\n📋 Recent Daily Items (last 5):")
            recent_items = session.query(DailyRawItem).order_by(DailyRawItem.id.desc()).limit(5).all()
            for item in recent_items:
                print(f"  - [{item.source_type}] {item.title[:50]}...")
                print(f"    Source: {item.source_name} | Status: {item.review_status}")
        
        print("\n" + "="*70)
        print("HOW TO VIEW DATA")
        print("="*70)
        print("""
1. SQL Editor in Neon Console:
   https://console.neon.tech
   → Select your project → SQL Editor
   
2. Query Examples:
   -- View all daily batches
   SELECT * FROM ingestion_batches ORDER BY created_at DESC;
   
   -- View latest daily items
   SELECT source_name, title, review_status 
   FROM daily_raw_items 
   ORDER BY id DESC LIMIT 20;
   
   -- View source performance
   SELECT source_name, status, items_returned, response_time_ms
   FROM daily_source_runs
   ORDER BY completed_at DESC;

3. Using the API:
   GET http://localhost:8000/api/daily/batches
   GET http://localhost:8000/api/daily/batches/{batch_id}/items
   
4. Export PDF:
   GET http://localhost:8000/api/daily/batches/{batch_id}/pdf
        """)
        
        print("="*70)
        
    except Exception as e:
        print(f"\n❌ Error checking database: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    check_database()
