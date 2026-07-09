from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Any

from pydantic import EmailStr, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    semantic_scholar_api_key: str | None = None
    openalex_contact_email: EmailStr | None = None
    huggingface_token: str | None = None
    gnews_api_key: str | None = None
    newsapi_key: str | None = None
    github_token: str | None = None
    apify_api_token: str | None = None
    openai_api_key: str | None = None
    guardian_api_key: str | None = None
    nytimes_api_key: str | None = None
    exa_api_key: str | None = None
    tavily_api_key: str | None = None
    serper_api_key: str | None = None
    serpapi_api_key: str | None = None
    firecrawl_api_key: str | None = None
    
    # Apify scraper settings
    apify_scraper_timeout_secs: int = 300
    apify_max_pages_per_scrape: int = 10
    apify_enable_javascript: bool = True
    
    # Private source authentication (for future use with Apify)
    gartner_username: str | None = None
    gartner_password: str | None = None
    forrester_username: str | None = None
    forrester_password: str | None = None
    brightedge_api_key: str | None = None
    sprinklr_api_key: str | None = None
    adbeat_api_key: str | None = None

    research_topics: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "retrieval augmented generation",
            "vector search",
            "semantic search",
            "embedding models",
            "dense retrieval",
            "RAG",
        ]
    )
    max_papers_per_source: int = 50
    max_news_articles_per_source: int = 100
    max_github_repos: int = 30
    fetch_interval_hours: int = 6
    research_fetch_hour: int = 2
    developer_fetch_hour: int = 3
    min_publication_year: int = 2022
    news_lookback_days: int = 30

    database_connection_string: str = "sqlite:///./research_intel.db"
    email_provider: str = "resend"
    email_from: str = "Research Intelligence <onboarding@resend.dev>"
    daily_email_from: str = "Research Intelligence <onboarding@resend.dev>"
    daily_email_to: EmailStr | None = None
    resend_api_key: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None

    app_env: str = "local"
    log_level: str = "INFO"
    system_version: str = "0.1.0"
    default_embedding_provider: str = "local"
    default_llm_provider: str = "optional_openai"
    enable_background_scheduler: bool = False
    enable_daily_email: bool = False
    daily_email_hour: int = 8

    request_timeout_seconds: float = 20.0
    user_agent: str = "BridgeAI-Research-Intelligence/0.1"

    @field_validator("research_topics", mode="before")
    @classmethod
    def split_topics(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @field_validator("openalex_contact_email", "daily_email_to", mode="before")
    @classmethod
    def blank_email_to_none(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_connection_string.startswith("postgresql://"):
            return self.database_connection_string.replace(
                "postgresql://", "postgresql+psycopg://", 1
            )
        return self.database_connection_string

    def masked_connectors(self) -> dict[str, bool | str]:
        values: dict[str, bool | str] = {}
        for name in (
            "semantic_scholar_api_key",
            "openalex_contact_email",
            "huggingface_token",
            "gnews_api_key",
            "newsapi_key",
            "github_token",
            "apify_api_token",
            "openai_api_key",
            "guardian_api_key",
            "nytimes_api_key",
            "exa_api_key",
            "tavily_api_key",
            "serper_api_key",
            "firecrawl_api_key",
            "resend_api_key",
        ):
            raw = getattr(self, name)
            values[name] = bool(raw)
        values["database"] = "configured" if self.database_connection_string else "missing"
        return values


@lru_cache
def get_settings() -> Settings:
    return Settings()
