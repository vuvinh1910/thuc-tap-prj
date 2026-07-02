"""
Application settings using Pydantic BaseSettings.
All values can be overridden via environment variables or .env file.
"""

from enum import Enum
from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LLMProviderType(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OLLAMA = "ollama"


class EmbeddingProviderType(str, Enum):
    OPENAI = "openai"


class ChunkingStrategyType(str, Enum):
    FIXED_SIZE = "fixed_size"
    SENTENCE = "sentence"
    RECURSIVE = "recursive"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    app_env: AppEnv = AppEnv.DEVELOPMENT
    app_debug: bool = False
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    # ── Provider Selection ───────────────────────────────────────────────────
    llm_provider: LLMProviderType = LLMProviderType.ANTHROPIC
    embedding_provider: EmbeddingProviderType = EmbeddingProviderType.OPENAI

    # ── OpenAI ───────────────────────────────────────────────────────────────
    openai_api_key: str = Field(default="", description="OpenAI API Key")
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimension: int = 1536
    openai_llm_model: str = "gpt-4o-mini"

    # ── Anthropic ────────────────────────────────────────────────────────────
    anthropic_api_key: str = Field(default="", description="Anthropic API Key")
    anthropic_llm_model: str = "claude-3-5-haiku-20241022"

    # ── Ollama ───────────────────────────────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    ollama_llm_model: str = "llama3.2"

    # ── Qdrant ───────────────────────────────────────────────────────────────
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_grpc_port: int = 6334
    qdrant_collection_name: str = "legal_docs"

    @computed_field  # type: ignore[misc]
    @property
    def qdrant_url(self) -> str:
        return f"http://{self.qdrant_host}:{self.qdrant_port}"

    # ── PostgreSQL ───────────────────────────────────────────────────────────
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "ragbot"
    postgres_password: str = "ragbot_secret"
    postgres_db: str = "ragbot_db"
    database_url: str = "postgresql+asyncpg://ragbot:ragbot_secret@localhost:5432/ragbot_db"

    # ── Redis / Celery ───────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # ── File Storage ─────────────────────────────────────────────────────────
    upload_dir: str = "./uploads"
    max_file_size_mb: int = 50

    @computed_field  # type: ignore[misc]
    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    # ── Chunking ─────────────────────────────────────────────────────────────
    chunk_size: int = 512
    chunk_overlap: int = 50
    chunking_strategy: ChunkingStrategyType = ChunkingStrategyType.RECURSIVE

    # ── RAG Retrieval ─────────────────────────────────────────────────────────
    retrieval_top_k: int = 5
    retrieval_score_threshold: float = 0.35

    @property
    def is_development(self) -> bool:
        return self.app_env == AppEnv.DEVELOPMENT


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton — call this everywhere instead of Settings()."""
    return Settings()
