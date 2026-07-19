from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator

MIN_SCORES = {"business_relevance": 3, "actionability": 3, "novelty": 2, "credibility": 2, "momentum": 1}
CATEGORY_CAPS = {"news": 8, "blog": 5, "repo": 5, "other": 5}
DEFAULT_DENY_LIST = [
    "candidate evidence for enterprise ai strategy and implementation decisions",
    "important for the ai landscape", "relevant to business strategy",
    "significant implications for the industry", "worth keeping an eye on",
]


class SignalFilterConfig(BaseModel):
    config_version: str = "1.0"
    model_version: str | None = None
    exact_duplicate_enabled: bool = True
    lexical_dedup_enabled: bool = True
    semantic_dedup_enabled: bool = True
    event_clustering_enabled: bool = True
    claim_extraction_enabled: bool = True
    historical_novelty_enabled: bool = True
    auto_regeneration_enabled: bool = True
    lexical_duplicate_threshold: float = Field(0.82, ge=0, le=1)
    semantic_duplicate_threshold: float = Field(0.88, ge=0, le=1)
    event_similarity_threshold: float = Field(0.82, ge=0, le=1)
    uniqueness_similarity_threshold: float = Field(0.60, ge=0, le=1)
    title_similarity_weight: float = Field(0.40, ge=0, le=1)
    body_similarity_weight: float = Field(0.60, ge=0, le=1)
    min_scores: dict[str, int] = Field(default_factory=lambda: dict(MIN_SCORES))
    min_total_score: int = 15
    category_caps: dict[str, int] = Field(default_factory=lambda: dict(CATEGORY_CAPS))
    total_item_cap: int = 20
    auto_accept_confidence: float = Field(0.80, ge=0, le=1)
    human_review_confidence: float = Field(0.55, ge=0, le=1)
    implication_review_confidence: float = Field(0.60, ge=0, le=1)
    max_regeneration_attempts: int = Field(2, ge=0, le=10)
    max_pdf_pages: int = 60
    max_candidate_items: int = 40
    deny_list: list[str] = Field(default_factory=lambda: list(DEFAULT_DENY_LIST))
    recency_half_life_days: dict[str, int] = Field(default_factory=lambda: {"news": 7, "blog": 30, "repo": 45, "research_paper": 180, "documentation": 90, "report": 180, "community": 14, "other": 30})
    source_type_overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)
    domain_overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_weights_and_thresholds(self) -> "SignalFilterConfig":
        if abs(self.title_similarity_weight + self.body_similarity_weight - 1) > 1e-6:
            raise ValueError("title and body similarity weights must sum to 1")
        missing = set(MIN_SCORES) - set(self.min_scores)
        if missing:
            raise ValueError(f"min_scores missing criteria: {sorted(missing)}")
        return self

    def effective_for(self, source_type: str, domain: str | None = None, brief: dict[str, Any] | None = None) -> "SignalFilterConfig":
        data = self.model_dump()
        for override in (self.source_type_overrides.get(source_type, {}), self.domain_overrides.get(domain or "", {}), brief or {}):
            data.update(override)
        return SignalFilterConfig.model_validate(data)

    @classmethod
    def from_file(cls, path: str | Path) -> "SignalFilterConfig":
        path = Path(path)
        raw = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            return cls.model_validate_json(raw)
        try:
            import yaml  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError("YAML configuration requires PyYAML; JSON works without it") from exc
        return cls.model_validate(yaml.safe_load(raw))

    @classmethod
    def from_env(cls, prefix: str = "SIGNAL_FILTER_") -> "SignalFilterConfig":
        import os
        values: dict[str, Any] = {}
        for name in cls.model_fields:
            raw = os.getenv(f"{prefix}{name.upper()}")
            if raw is None:
                continue
            try: values[name] = json.loads(raw)
            except json.JSONDecodeError: values[name] = raw
        return cls.model_validate(values)
