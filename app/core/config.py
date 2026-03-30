"""
Application configuration — loaded from environment variables.
Uses pydantic-settings for validation and type safety.
Pattern adopted from eve-core: lru_cache factory + Field aliases.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from .env file and environment variables."""

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Environment ─────────────────────────────────────────
    env: str = Field(default="development", alias="ENV")
    log_level: str = Field(default="info", alias="LOG_LEVEL")

    # ── OpenAI ──────────────────────────────────────────────
    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")

    # ── Model configuration ─────────────────────────────────
    llm_model: str = Field(default="gpt-4o", alias="LLM_MODEL")
    embedding_model: str = Field(
        default="text-embedding-3-small", alias="EMBEDDING_MODEL"
    )
    llm_temperature: float = Field(default=0.0, alias="LLM_TEMPERATURE")

    # ── Retriever configuration ─────────────────────────────
    retriever_k: int = Field(default=5, alias="RETRIEVER_K")

    # ── Ingestion configuration ─────────────────────────────
    chunk_size: int = Field(default=700, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=120, alias="CHUNK_OVERLAP")

    # ── Paths ───────────────────────────────────────────────
    courses_json_path: str = Field(default="data/courses.json", alias="COURSES_JSON_PATH")
    vectorstore_path: str = Field(default="vectorstore", alias="VECTORSTORE_PATH")

    # ── API ──────────────────────────────────────────────────
    api_title: str = "Course Planning Assistant"
    api_version: str = "1.0.0"
    api_description: str = (
        "RAG-powered API to check course eligibility, "
        "generate term plans, and answer questions grounded in catalog data."
    )


@lru_cache
def get_settings() -> Settings:
    """Singleton factory for application settings (cached on first call)."""
    return Settings()  # type: ignore[call-arg]
