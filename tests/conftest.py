"""
Test fixtures and shared configuration.
Uses in-memory mocks for all external services.
"""

import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.main import create_app
from src.core.entities.chunk import Chunk, EmbeddedChunk
from src.core.entities.document import Document, DocumentStatus
from src.core.entities.query import Citation, LLMResponse, SearchResult
from src.core.interfaces.document_repo import IDocumentRepository
from src.core.interfaces.embedding import IEmbeddingProvider
from src.core.interfaces.llm import ILLMProvider
from src.core.interfaces.vector_store import IVectorStore
from src.infrastructure.database.models import Base

# ── In-memory SQLite for tests ────────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def test_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create an in-memory SQLite session for each test."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()


# ── Mock Providers ────────────────────────────────────────────────────────────

@pytest.fixture
def mock_embedding_provider() -> IEmbeddingProvider:
    """Mock that returns deterministic vectors."""
    provider = MagicMock(spec=IEmbeddingProvider)
    provider.model_name = "mock-embedding"
    provider.dimension = 4
    provider.embed_text = AsyncMock(return_value=[0.1, 0.2, 0.3, 0.4])
    provider.embed_batch = AsyncMock(
        side_effect=lambda texts: [[0.1, 0.2, 0.3, 0.4] for _ in texts]
    )
    return provider


@pytest.fixture
def mock_llm_provider() -> ILLMProvider:
    """Mock LLM that returns a fixed answer."""
    provider = MagicMock(spec=ILLMProvider)
    provider.model_name = "mock-llm"
    provider.generate = AsyncMock(
        return_value=LLMResponse(
            answer="Đây là câu trả lời test.",
            is_grounded=True,
            model_used="mock-llm",
            usage_tokens=100,
        )
    )
    return provider


@pytest.fixture
def mock_vector_store() -> IVectorStore:
    """Mock vector store with configurable search results."""
    doc_id = uuid.uuid4()
    chunk = Chunk(
        document_id=doc_id,
        content="Mức phạt vi phạm tốc độ là 3-5 triệu đồng.",
        chunk_index=0,
        page_number=1,
    )
    store = MagicMock(spec=IVectorStore)
    store.upsert = AsyncMock()
    store.delete_by_document = AsyncMock()
    store.collection_exists = AsyncMock(return_value=True)
    store.ensure_collection = AsyncMock()
    store.search = AsyncMock(
        return_value=[
            SearchResult(
                chunk=chunk,
                score=0.85,
                document_filename="nghi-dinh.pdf",
            )
        ]
    )
    return store


@pytest.fixture
def mock_document_repo() -> IDocumentRepository:
    """Mock repository with a pre-saved document."""
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        filename="test.pdf",
        file_path="/tmp/test.pdf",
        status=DocumentStatus.COMPLETED,
        chunk_count=5,
    )
    repo = MagicMock(spec=IDocumentRepository)
    repo.save = AsyncMock(return_value=doc)
    repo.find_by_id = AsyncMock(return_value=doc)
    repo.update_status = AsyncMock()
    repo.list_all = AsyncMock(return_value=[doc])
    repo.delete = AsyncMock(return_value=True)
    return repo


# ── Test HTTP Client ──────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def test_client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client for integration tests."""
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
