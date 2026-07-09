#!/usr/bin/env python
"""Quick ingestion to populate database with research content."""

import asyncio
from research_intel.db import SessionLocal
from research_intel.ingestion.orchestrator import IngestionOrchestrator
from research_intel.config import get_settings

async def main():
    settings = get_settings()
    session = SessionLocal()
    orchestrator = IngestionOrchestrator(settings)
    
    print("🚀 Starting ingestion to populate database...")
    print("This will fetch content from all configured sources.")
    print()
    
    # Ingest research papers and articles
    topics = [
        "retrieval augmented generation",
        "vector search", 
        "semantic search",
        "large language models",
        "embedding models",
    ]
    
    for topic in topics:
        print(f"📚 Ingesting: {topic}")
        await orchestrator.ingest_topic(
            session,
            topic=topic,
            domain="AI/ML",
            max_per_source=20,  # Get 20 items per source
        )
        print(f"✅ Completed: {topic}\n")
    
    session.close()
    print("🎉 Ingestion complete! Check your database stats.")

if __name__ == "__main__":
    asyncio.run(main())
