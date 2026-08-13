"""
Celery task: ingest_document.
Runs in the worker process — builds all dependencies manually (no FastAPI DI).
"""

import asyncio
import uuid

import structlog

from src.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


def _build_ingestion_service():
    """
    Manually wire dependencies for the Celery worker context.
    FastAPI DI container is not available in worker processes.
    """
    from src.config.settings import get_settings
    from src.core.services.chunking_service import ChunkingConfig, ChunkingService, ChunkingStrategy
    from src.core.services.ingestion_service import IngestionService
    from src.infrastructure.database.document_repo import PostgresDocumentRepository
    from src.infrastructure.database.session import AsyncSessionFactory
    from src.infrastructure.embedding.openai_provider import OpenAIEmbeddingProvider
    from src.infrastructure.file_storage.local_storage import LocalFileStorage
    from src.infrastructure.vector_store.qdrant_store import QdrantVectorStore

    settings = get_settings()

    # AsyncSessionFactory is a sessionmaker — call it to get a scoped session
    session = AsyncSessionFactory()

    chunking_service = ChunkingService(
        config=ChunkingConfig(
            strategy=ChunkingStrategy(settings.chunking_strategy.value),
            chunk_size=settings.chunk_size,
            overlap=settings.chunk_overlap,
        )
    )

    return IngestionService(
        chunking_service=chunking_service,
        embedding_provider=OpenAIEmbeddingProvider(),
        vector_store=QdrantVectorStore(),
        file_storage=LocalFileStorage(base_dir=settings.upload_dir),
        document_repo=PostgresDocumentRepository(session),
    ), session


async def _run_ingestion(document_id: str, filename: str, file_path: str) -> dict:
    """
    Async helper: update status to PROCESSING, then run the full ingest pipeline.
    Properly closes the DB session in all cases.
    """
    from src.core.entities.document import Document, DocumentStatus

    ingestion_service, session = _build_ingestion_service()

    try:
        # Update document status to PROCESSING in the database
        from src.infrastructure.database.document_repo import PostgresDocumentRepository
        doc_repo = PostgresDocumentRepository(session)
        await doc_repo.update_status(
            document_id=uuid.UUID(document_id),
            status=DocumentStatus.PROCESSING,
        )

        # Build a Document entity for the ingest pipeline
        doc = Document(
            id=uuid.UUID(document_id),
            filename=filename,
            file_path=file_path,
            status=DocumentStatus.PROCESSING,
        )

        await ingestion_service.ingest(doc)
        return {"status": "completed", "document_id": document_id}

    finally:
        await session.close()
        
        # Dispose global engine pool to prevent "attached to a different loop" errors
        # on subsequent Celery tasks running in new event loops.
        from src.infrastructure.database.session import engine
        await engine.dispose()


@celery_app.task(
    name="src.workers.tasks.ingest_task.ingest_document",
    bind=True,
    max_retries=3,
    default_retry_delay=30,  # seconds between retries
    queue="ingest",
)
def ingest_document(self, document_id: str, filename: str, file_path: str) -> dict:
    """
    Celery task: ingest a document into the vector store.

    Args:
        document_id: UUID string of the document record.
        filename: Original filename for logging/parsing hints.
        file_path: Path where the uploaded file is stored.

    Returns:
        dict with status and chunk_count on success.
    """
    logger.info("ingest_task_started", document_id=document_id, filename=filename)

    try:
        # Use asyncio.run() for clean event loop management (no memory leak)
        result = asyncio.run(
            _run_ingestion(document_id, filename, file_path)
        )
        logger.info("ingest_task_completed", document_id=document_id)
        return result

    except Exception as exc:
        logger.error("ingest_task_failed", document_id=document_id, error=str(exc))
        raise self.retry(exc=exc, countdown=30)
