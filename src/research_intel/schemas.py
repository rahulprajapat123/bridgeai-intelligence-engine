from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


SourceType = Literal["academic", "industry", "vendor", "blog", "news", "code", "web"]
EvidenceType = Literal[
    "experiment",
    "benchmark",
    "case_study",
    "analysis",
    "announcement",
    "documentation",
    "review",
    "theoretical",
    "anecdotal",
]
ProblemType = Literal["QA", "search", "summarization", "agentic", "classification"]
DataModality = Literal["PDFs", "tickets", "logs", "code", "mixed", "structured", "unstructured"]
AccuracyCostTradeoff = Literal["accuracy_first", "balanced", "cost_first"]
DeploymentEnv = Literal["GCP", "AWS", "Azure", "on-prem", "hybrid", "edge", "cloud"]


class RawDocumentSchema(BaseModel):
    title: str
    source_url: str
    source_type: SourceType
    source_name: str
    text: str
    authors: list[str] = Field(default_factory=list)
    publication_date: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClaimCreate(BaseModel):
    claim_text: str
    evidence_summary: str = ""
    evidence_type: EvidenceType
    evidence_location: str = ""
    metrics: list[str] = Field(default_factory=list)
    conditions: str = ""
    limitations: str = ""
    applicability_tags: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    extraction_method: str = "heuristic_auto"


class ProjectContext(BaseModel):
    problem_type: ProblemType
    data_modality: DataModality
    corpus_scale: str = Field(min_length=1)
    latency_constraint: str = Field(min_length=1)
    accuracy_cost_tradeoff: AccuracyCostTradeoff
    deployment_env: DeploymentEnv
    domain: str = Field(default="general", min_length=1)
    extra_constraints: dict[str, Any] = Field(default_factory=dict)

    @field_validator("corpus_scale", "latency_constraint", "domain")
    @classmethod
    def no_vague_values(cls, value: str) -> str:
        lowered = value.strip().lower()
        vague = {"unknown", "n/a", "na", "tbd", "not sure", "varies", "some", "many"}
        if not lowered or lowered in vague:
            raise ValueError("Project context contains a vague required value.")
        return value.strip()


class ProjectContextInput(BaseModel):
    problem_type: str | None = None
    data_modality: str | None = None
    corpus_scale: str | None = None
    latency_constraint: str | None = None
    accuracy_cost_tradeoff: str | None = None
    deployment_env: str | None = None
    domain: str | None = None
    extra_constraints: dict[str, Any] = Field(default_factory=dict)

    def missing_fields(self) -> list[str]:
        required = [
            "problem_type",
            "data_modality",
            "corpus_scale",
            "latency_constraint",
            "accuracy_cost_tradeoff",
            "deployment_env",
        ]
        return [field for field in required if not getattr(self, field)]


class DomainClassification(BaseModel):
    domain: str
    primary_domain: str | None = None
    secondary_domains: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    hierarchy: list[str] = Field(default_factory=list)
    scores: dict[str, float] = Field(default_factory=dict)
    rationale: list[str] = Field(default_factory=list)
    reasoning_summary: str = ""
    negative_signals: list[str] = Field(default_factory=list)


class SourceRoute(BaseModel):
    source_type: str
    priority: int = Field(ge=1)
    query: str


class BriefAnalysis(BaseModel):
    brief_id: str | None = None
    title: str = ""
    domain: DomainClassification
    primary_domain: str
    secondary_domains: list[str] = Field(default_factory=list)
    objective: str
    intent: str
    audience: list[str] = Field(default_factory=list)
    companies: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    tools_or_platforms: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    query_decomposition: list[str] = Field(default_factory=list)
    research_questions: list[str] = Field(default_factory=list)
    retrieval_routes: list[str] = Field(default_factory=list)
    source_routes: list[str] = Field(default_factory=list)
    source_route_plan: list[SourceRoute] = Field(default_factory=list)
    structured_constraints: dict[str, Any] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)
    deliverables: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    timeline: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0, ge=0, le=1)
    inferred_project_context: ProjectContextInput


class BriefUploadResponse(BaseModel):
    brief_id: str
    filename: str
    content_type: str
    text_length: int
    analysis: BriefAnalysis


class WorkflowAnalyzeRequest(BaseModel):
    brief_id: str | None = None
    text: str | None = None
    auto_fetch: bool = False
    max_per_source: int = Field(default=5, ge=1, le=50)
    top_k: int = Field(default=8, ge=1, le=30)
    min_credibility: float = Field(default=60, ge=0, le=100)
    include_latest_sources: bool = True
    output_format: Literal["one_page_brief", "legacy"] = "one_page_brief"

    @model_validator(mode="after")
    def require_brief_source(self) -> "WorkflowAnalyzeRequest":
        if not self.brief_id and not self.text:
            raise ValueError("Provide either brief_id or text.")
        return self


class TechnologyRecommendation(BaseModel):
    technology_name: str
    category: str
    relevance_score: float = Field(ge=0, le=1)
    supporting_evidence: list[EvidenceItem] = Field(default_factory=list)
    source_links: list[str] = Field(default_factory=list)
    implementation_guidance: str


class OnePageRecommendation(BaseModel):
    point: str
    why_it_matters: str
    supporting_evidence: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"]


class RecommendedToolOrMethod(BaseModel):
    name: str
    category: str
    fit_reason: str
    tradeoffs: str
    citations: list[str] = Field(default_factory=list)


class OnePageBrief(BaseModel):
    title: str = "One-Page Research Intelligence Brief"
    generated_at: str
    brief_summary: str
    domain: str
    client_need: str
    top_recommendations: list[OnePageRecommendation] = Field(default_factory=list)
    recommended_tools_or_methods: list[RecommendedToolOrMethod] = Field(default_factory=list)
    risks_and_limitations: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    suggested_next_steps: list[str] = Field(default_factory=list)
    insufficient_evidence_items: list[str] = Field(default_factory=list)


class WorkflowAnalyzeResponse(BaseModel):
    brief_id: str | None = None
    analysis: BriefAnalysis
    fetched_sources: IngestResponse | None = None
    recommendations: list[TechnologyRecommendation]
    citations: list[EvidenceItem]
    one_page_brief: OnePageBrief | None = None
    insufficient_evidence: bool = False


class IngestRequest(BaseModel):
    topic: str = Field(min_length=2)
    domain: str | None = None
    max_per_source: int | None = Field(default=None, ge=1, le=200)
    dry_run: bool = False


class IngestResponse(BaseModel):
    run_id: str
    status: str
    topic: str
    domain: str
    documents_seen: int
    documents_inserted: int
    claims_inserted: int
    errors: list[str] = Field(default_factory=list)


class ClaimSearchRequest(BaseModel):
    query: str = Field(min_length=2)
    domain: str | None = None
    top_k: int = Field(default=10, ge=1, le=50)
    min_credibility: float = Field(default=0, ge=0, le=100)


class RetrievedClaim(BaseModel):
    claim_id: str
    claim_text: str
    evidence_type: str
    evidence_summary: str
    source: str
    source_url: str
    title: str
    credibility_score: float
    confidence: float
    relevance_score: float
    applicability_tags: list[str] = Field(default_factory=list)
    evidence_location: str = ""
    metrics: list[str] = Field(default_factory=list)
    limitations: str = ""
    publication_date: str | None = None


class EvidenceItem(BaseModel):
    source: str
    source_url: str
    title: str
    credibility_score: float = Field(ge=0, le=100)
    key_findings: str
    evidence_snippet: str
    evidence_location: str = ""
    citation_count: int | None = None
    date: str | None = None
    claim_id: str


class RecommendationCore(BaseModel):
    technique: str
    why_it_works: str
    expected_benefit: str
    tradeoffs: str


class ImplementationNotes(BaseModel):
    complexity: Literal["low", "medium", "high"]
    tooling_options: list[str] = Field(default_factory=list)
    gotchas: list[str] = Field(default_factory=list)


class RecommendationContract(BaseModel):
    schema_version: str = "1.0"
    generated_at: str
    system_version: str
    project_context: dict[str, Any]
    recommendation: RecommendationCore
    techniques_to_apply: list[RecommendationCore] = Field(default_factory=list)
    techniques_to_avoid: list[RecommendationCore] = Field(default_factory=list)
    tooling_suggestions: list[str] = Field(default_factory=list)
    explicit_tradeoffs: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem]
    implementation_notes: ImplementationNotes
    confidence_level: Literal["high", "medium", "low"]

    @model_validator(mode="after")
    def enforce_evidence(self) -> "RecommendationContract":
        if not self.evidence:
            raise ValueError("Recommendation contract requires at least one evidence item.")
        cited_sources = {item.claim_id for item in self.evidence}
        if not cited_sources:
            raise ValueError("Evidence must cite claim IDs.")
        return self


class InsufficientEvidence(BaseModel):
    status: Literal["insufficient_evidence"] = "insufficient_evidence"
    generated_at: str
    system_version: str
    reason: str
    missing_fields: list[str] = Field(default_factory=list)
    searched_query: str | None = None
    top_evidence_count: int = 0


class RecommendationRequest(BaseModel):
    project_context: ProjectContextInput
    top_k: int = Field(default=12, ge=3, le=50)
    min_credibility: float = Field(default=60, ge=0, le=100)


class RecommendationResponse(BaseModel):
    status: Literal["ok", "insufficient_evidence"]
    query_id: str
    latency_ms: int
    data: RecommendationContract | InsufficientEvidence


class FeedbackRequest(BaseModel):
    query_id: str | None = None
    rating: Literal["helpful", "partially_helpful", "not_helpful"]
    notes: str = ""
    project_context: dict[str, Any] = Field(default_factory=dict)
    recommendation: dict[str, Any] = Field(default_factory=dict)


class FeedbackResponse(BaseModel):
    feedback_id: str
    status: str


class DailyIntelligenceRequest(BaseModel):
    send_email: bool = False
    recipient_email: str | None = None
    recipient: str | None = None
    max_items: int = Field(default=50, ge=1, le=200)
    topics: list[str] = Field(default_factory=list)


class DailyIntelligenceResponse(BaseModel):
    report_id: str
    status: str
    sent: bool = False
    report: dict[str, Any]


class HealthResponse(BaseModel):
    status: str
    generated_at: datetime
    connectors: dict[str, bool | str]
    database: str
