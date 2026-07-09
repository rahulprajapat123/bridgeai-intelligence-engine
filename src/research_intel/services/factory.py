from __future__ import annotations

from dataclasses import dataclass

from research_intel.config import Settings, get_settings
from research_intel.ingestion.orchestrator import IngestionOrchestrator
from research_intel.intelligence.brief import BriefUnderstandingService
from research_intel.intelligence.credibility import CredibilityScorer
from research_intel.intelligence.domain import DomainClassifier
from research_intel.intelligence.embeddings import EmbeddingService
from research_intel.intelligence.extraction import ClaimExtractor
from research_intel.intelligence.recommendation import RecommendationService
from research_intel.intelligence.retrieval import RetrievalService
from research_intel.services.daily_intelligence import DailyIntelligenceService
from research_intel.services.document_parser import DocumentParserService


@dataclass
class AppServices:
    settings: Settings
    classifier: DomainClassifier
    brief: BriefUnderstandingService
    embeddings: EmbeddingService
    extractor: ClaimExtractor
    scorer: CredibilityScorer
    document_parser: DocumentParserService
    retrieval: RetrievalService
    ingestion: IngestionOrchestrator
    recommendation: RecommendationService
    daily_intelligence: DailyIntelligenceService


def build_services(settings: Settings | None = None) -> AppServices:
    settings = settings or get_settings()
    classifier = DomainClassifier()
    brief = BriefUnderstandingService(classifier)
    embeddings = EmbeddingService(settings)
    extractor = ClaimExtractor(settings)
    scorer = CredibilityScorer()
    document_parser = DocumentParserService(settings)
    retrieval = RetrievalService(embeddings)
    ingestion = IngestionOrchestrator(
        settings, extractor, scorer, embeddings, classifier, document_parser
    )
    recommendation = RecommendationService(settings, retrieval)
    daily_intelligence = DailyIntelligenceService(settings)
    return AppServices(
        settings=settings,
        classifier=classifier,
        brief=brief,
        embeddings=embeddings,
        extractor=extractor,
        scorer=scorer,
        document_parser=document_parser,
        retrieval=retrieval,
        ingestion=ingestion,
        recommendation=recommendation,
        daily_intelligence=daily_intelligence,
    )
