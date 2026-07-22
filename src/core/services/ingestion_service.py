"""
IngestionService — orchestrates the full document ingest pipeline:
parse → chunk → embed → upsert to vector store → update document status.
"""

import structlog

from src.core.entities.chunk import EmbeddedChunk
from src.core.entities.document import Document, DocumentStatus
from src.core.interfaces.document_repo import IDocumentRepository
from src.core.interfaces.embedding import IEmbeddingProvider
from src.core.interfaces.file_storage import IFileStorage
from src.core.interfaces.vector_store import IVectorStore
from src.core.services.chunking_service import ChunkingConfig, ChunkingService

logger = structlog.get_logger(__name__)


class IngestionService:
    """
    Orchestrates the document ingestion pipeline.

    Called by Celery workers after a file is uploaded.
    Updates document status at each stage for observability.
    """

    def __init__(
        self,
        chunking_service: ChunkingService,
        embedding_provider: IEmbeddingProvider,
        vector_store: IVectorStore,
        file_storage: IFileStorage,
        document_repo: IDocumentRepository,
    ) -> None:
        self._chunking = chunking_service
        self._embedding = embedding_provider
        self._vector_store = vector_store
        self._file_storage = file_storage
        self._doc_repo = document_repo

    async def ingest(self, document: Document) -> None:
        """
        Full ingestion pipeline for a single document.

        Pipeline:
            1. Read file from storage
            2. Parse to text (PDF → string)
            3. Split into chunks
            4. Embed chunks in batch
            5. Upsert to vector store
            6. Update document status

        Args:
            document: The Document entity to ingest (status=PENDING/PROCESSING).
        """
        logger.info("ingest_started", document_id=str(document.id), filename=document.filename)

        try:
            # Step 1: Read file
            raw_bytes = await self._file_storage.read(document.file_path)

            # Step 2: Parse to text (with page awareness)
            pages = self._parse_with_pages(raw_bytes, document.filename)
            logger.info("ingest_parsed", document_id=str(document.id), page_count=len(pages))

            # Step 3: Chunk with page metadata
            chunks = self._chunking.split_with_pages(pages, document.id)
            logger.info("ingest_chunked", document_id=str(document.id), chunk_count=len(chunks))

            if not chunks:
                raise ValueError("No text content extracted from document.")

            # Step 4: Ensure vector store collection exists
            await self._vector_store.ensure_collection(
                dimension=self._embedding.dimension
            )

            # Step 5: Embed in batches
            texts = [chunk.content for chunk in chunks]
            vectors = await self._embedding.embed_batch(texts)

            embedded_chunks: list[EmbeddedChunk] = [
                EmbeddedChunk(chunk=chunk, vector=vector)
                for chunk, vector in zip(chunks, vectors, strict=True)
            ]

            # Step 6: Upsert to Qdrant (pass filename for citation reconstruction)
            await self._vector_store.upsert(embedded_chunks, filename=document.filename)

            # Step 7: Update document status
            await self._doc_repo.update_status(
                document_id=document.id,
                status=DocumentStatus.COMPLETED,
                chunk_count=len(chunks),
            )
            logger.info(
                "ingest_completed",
                document_id=str(document.id),
                chunk_count=len(chunks),
            )

        except Exception as e:
            logger.error("ingest_failed", document_id=str(document.id), error=str(e))
            await self._doc_repo.update_status(
                document_id=document.id,
                status=DocumentStatus.FAILED,
                error_message=str(e),
            )
            raise

    def _parse_with_pages(
        self, raw_bytes: bytes, filename: str
    ) -> list[tuple[int, str]]:
        """
        Auto-detect parser based on content quality.
        Returns list of (page_number, text) tuples.
        """
        from src.infrastructure.parsers.pdf_parser import PdfParser
        from src.infrastructure.parsers.unstructured_parser import auto_parse

        if filename.lower().endswith(".pdf"):
            pdf_parser = PdfParser()
            pages = pdf_parser.parse_with_pages(raw_bytes)
            if pages:
                return pages
            # Fallback: treat entire document as page 1
            text = auto_parse(raw_bytes, filename)
            return [(1, text)] if text else []
        else:
            # Plain text file
            text = raw_bytes.decode("utf-8", errors="replace")
            return [(1, text)]
