"""Test signal filter with minimal data"""
import asyncio
from research_intel.signal_filter.models import SignalItem, SourceMetadata, SourceType
from research_intel.signal_filter.pipeline import FilterContext, build_default_pipeline
from research_intel.signal_filter.config import SignalFilterConfig
from research_intel.config import Settings
from research_intel.signal_filter.adapters import EmbeddingServiceAdapter
from research_intel.intelligence.embeddings import EmbeddingService
from datetime import datetime, timezone

async def test_minimal():
    # Create a single test item
    item = SignalItem(
        item_id="test-001",
        title="Test Signal",
        body="This is a test signal for filtering.",
        metadata=SourceMetadata(
            source_url="https://example.com",
            source_name="Test Source",
            source_type=SourceType.NEWS,
            published_at=datetime.now(timezone.utc),
            domain="general",
        ),
    )
    
    # Create minimal config (disable expensive operations)
    config = SignalFilterConfig(
        enable_clustering=False,
        enable_qa_checks=False,
        novelty_threshold=5.0,
        relevance_threshold=50.0,
        max_output_items=5,
    )
    
    # Create context with just embedding adapter
    settings = Settings()
    embedding_service = EmbeddingService(settings)
    embedding_adapter = EmbeddingServiceAdapter(embedding_service)
    
    context = FilterContext(
        embedding_provider=embedding_adapter,
    )
    
    print("Starting pipeline...")
    try:
        result = await build_default_pipeline(config).run([item], context)
        print(f"✓ Pipeline completed!")
        print(f"  Run ID: {result.run_id}")
        print(f"  Items: {len(result.items)}")
        print(f"  Accepted: {result.metrics.accepted_count}")
        print(f"  Time: {result.metrics.processing_time_ms:.2f}ms")
        return True
    except Exception as e:
        print(f"✗ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = asyncio.run(test_minimal())
    exit(0 if success else 1)
