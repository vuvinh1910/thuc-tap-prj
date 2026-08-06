"""
Integration tests for PostgresDocumentRepository.
Uses aiosqlite (in-memory SQLite) to avoid needing a real PostgreSQL instance.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.entities.document import Document, DocumentStatus
from src.infrastructure.database.document_repo import PostgresDocumentRepository
from src.infrastructure.database.models import Base


@pytest_asyncio.fixture
async def db_session():
    """Create an in-memory SQLite async session for integration tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def sample_document() -> Document:
    return Document(
        filename="nghi_dinh_mau.pdf",
        file_path="/uploads/nghi_dinh_mau.pdf",
        status=DocumentStatus.PENDING,
        file_size_bytes=1024 * 512,
        content_type="application/pdf",
    )


@pytest.mark.asyncio
async def test_save_and_find_by_id(db_session, sample_document):
    repo = PostgresDocumentRepository(db_session)

    saved = await repo.save(sample_document)
    assert saved.id == sample_document.id

    found = await repo.find_by_id(sample_document.id)
    assert found is not None
    assert found.filename == "nghi_dinh_mau.pdf"
    assert found.status == DocumentStatus.PENDING


@pytest.mark.asyncio
async def test_find_by_id_not_found(db_session):
    repo = PostgresDocumentRepository(db_session)
    result = await repo.find_by_id(uuid.uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_update_status_completed(db_session, sample_document):
    repo = PostgresDocumentRepository(db_session)
    await repo.save(sample_document)

    await repo.update_status(
        document_id=sample_document.id,
        status=DocumentStatus.COMPLETED,
        chunk_count=42,
    )

    updated = await repo.find_by_id(sample_document.id)
    assert updated.status == DocumentStatus.COMPLETED
    assert updated.chunk_count == 42


@pytest.mark.asyncio
async def test_update_status_failed(db_session, sample_document):
    repo = PostgresDocumentRepository(db_session)
    await repo.save(sample_document)

    await repo.update_status(
        document_id=sample_document.id,
        status=DocumentStatus.FAILED,
        error_message="Qdrant connection timeout",
    )

    updated = await repo.find_by_id(sample_document.id)
    assert updated.status == DocumentStatus.FAILED
    assert updated.error_message == "Qdrant connection timeout"


@pytest.mark.asyncio
async def test_list_all(db_session):
    repo = PostgresDocumentRepository(db_session)

    for i in range(3):
        doc = Document(
            filename=f"doc_{i}.pdf",
            file_path=f"/uploads/doc_{i}.pdf",
            status=DocumentStatus.PENDING,
        )
        await repo.save(doc)

    docs = await repo.list_all(limit=10, offset=0)
    assert len(docs) == 3


@pytest.mark.asyncio
async def test_delete(db_session, sample_document):
    repo = PostgresDocumentRepository(db_session)
    await repo.save(sample_document)

    await repo.delete(sample_document.id)

    found = await repo.find_by_id(sample_document.id)
    assert found is None
