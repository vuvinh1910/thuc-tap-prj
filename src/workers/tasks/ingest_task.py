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
    from src.core.entities.document import Document, DocumentStatus

    logger.info("ingest_task_started", document_id=document_id, filename=filename)

    doc = Document(
        id=uuid.UUID(document_id),
        filename=filename,
        file_path=file_path,
        status=DocumentStatus.PROCESSING,
    )

    ingestion_service, session = _build_ingestion_service()

    try:
        # Run async ingestion in the sync Celery context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(ingestion_service.ingest(doc))
        finally:
            loop.run_until_complete(session.close())
            loop.close()

        logger.info("ingest_task_completed", document_id=document_id)
        return {"status": "completed", "document_id": document_id}

    except Exception as exc:
        logger.error("ingest_task_failed", document_id=document_id, error=str(exc))
        raise self.retry(exc=exc, countdown=30)
