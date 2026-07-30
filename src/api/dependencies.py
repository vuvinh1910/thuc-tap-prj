"""
FastAPI dependency injection container.
Provides service instances to route handlers.
All expensive objects (DB sessions, clients) are properly scoped.
"""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import Settings, get_settings
from src.core.interfaces.document_repo import IDocumentRepository
from src.core.interfaces.embedding import IEmbeddingProvider
from src.core.interfaces.file_storage import IFileStorage
from src.core.interfaces.llm import ILLMProvider
from src.core.interfaces.vector_store import IVectorStore
from src.core.services.chunking_service import ChunkingConfig, ChunkingService, ChunkingStrategy
from src.core.services.prompt_builder import PromptBuilder
from src.core.services.query_service import QueryService
from src.infrastructure.database.document_repo import PostgresDocumentRepository
from src.infrastructure.database.session import get_async_session
from src.infrastructure.file_storage.local_storage import LocalFileStorage
from src.infrastructure.vector_store.qdrant_store import QdrantVectorStore


# ── Settings ──────────────────────────────────────────────────────────────────

def get_settings_dep() -> Settings:
    return get_settings()

SettingsDep = Annotated[Settings, Depends(get_settings_dep)]


# ── Database Session ──────────────────────────────────────────────────────────

SessionDep = Annotated[AsyncSession, Depends(get_async_session)]


# ── Repositories ──────────────────────────────────────────────────────────────

def get_document_repo(session: SessionDep) -> IDocumentRepository:
    return PostgresDocumentRepository(session)

DocumentRepoDep = Annotated[IDocumentRepository, Depends(get_document_repo)]


# ── Infrastructure Providers ──────────────────────────────────────────────────

def get_file_storage(settings: SettingsDep) -> IFileStorage:
    """Factory: returns configured file storage backend."""
    return LocalFileStorage(base_dir=settings.upload_dir)

FileStorageDep = Annotated[IFileStorage, Depends(get_file_storage)]


def get_embedding_provider(settings: SettingsDep) -> IEmbeddingProvider:
    """Factory: returns the configured embedding provider."""
    from src.config.settings import EmbeddingProviderType
    from src.infrastructure.embedding.openai_provider import OpenAIEmbeddingProvider

    if settings.embedding_provider == EmbeddingProviderType.OPENAI:
        return OpenAIEmbeddingProvider()
    raise ValueError(f"Unknown embedding provider: {settings.embedding_provider}")

EmbeddingDep = Annotated[IEmbeddingProvider, Depends(get_embedding_provider)]


def get_llm_provider(settings: SettingsDep) -> ILLMProvider:
    """Factory: returns the configured LLM provider based on LLM_PROVIDER env var."""
    from src.config.settings import LLMProviderType
    from src.infrastructure.llm.anthropic_provider import AnthropicLLMProvider
    from src.infrastructure.llm.ollama_provider import OllamaLLMProvider
    from src.infrastructure.llm.openai_provider import OpenAILLMProvider

    if settings.llm_provider == LLMProviderType.ANTHROPIC:
        return AnthropicLLMProvider()
    elif settings.llm_provider == LLMProviderType.OPENAI:
        return OpenAILLMProvider()
    elif settings.llm_provider == LLMProviderType.OLLAMA:
        return OllamaLLMProvider()
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")

LLMDep = Annotated[ILLMProvider, Depends(get_llm_provider)]


def get_vector_store() -> IVectorStore:
    return QdrantVectorStore()

VectorStoreDep = Annotated[IVectorStore, Depends(get_vector_store)]


# ── Core Services ─────────────────────────────────────────────────────────────

def get_chunking_service(settings: SettingsDep) -> ChunkingService:
    return ChunkingService(
        config=ChunkingConfig(
            strategy=ChunkingStrategy(settings.chunking_strategy.value),
            chunk_size=settings.chunk_size,
            overlap=settings.chunk_overlap,
        )
    )

ChunkingServiceDep = Annotated[ChunkingService, Depends(get_chunking_service)]


def get_query_service(
    embedding: EmbeddingDep,
    vector_store: VectorStoreDep,
    llm: LLMDep,
) -> QueryService:
    return QueryService(
        embedding_provider=embedding,
        vector_store=vector_store,
        llm_provider=llm,
        prompt_builder=PromptBuilder(),
    )

QueryServiceDep = Annotated[QueryService, Depends(get_query_service)]
