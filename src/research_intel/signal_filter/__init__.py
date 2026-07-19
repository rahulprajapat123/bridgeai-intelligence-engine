"""Production-oriented, provider-neutral intelligence signal filtering."""

from .adapters import (
    DatabaseHistoricalRepository,
    EmbeddingServiceAdapter,
    OpenAIIntelligenceAdapter,
)
from .config import SignalFilterConfig
from .models import SignalItem
from .pipeline import FilterContext, SignalFilterPipeline, build_default_pipeline

__all__ = [
    "DatabaseHistoricalRepository",
    "EmbeddingServiceAdapter",
    "FilterContext",
    "OpenAIIntelligenceAdapter",
    "SignalFilterConfig",
    "SignalFilterPipeline",
    "SignalItem",
    "build_default_pipeline",
]
