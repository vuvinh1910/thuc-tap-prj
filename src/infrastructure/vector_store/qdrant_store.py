"""
QdrantVectorStore — implements IVectorStore using Qdrant vector database.
Supports cosine similarity search with metadata filtering.
"""

import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointStruct,
    VectorParams,
)
from uuid import UUID

from src.config.settings import get_settings
from src.core.entities.chunk import Chunk, EmbeddedChunk
from src.core.entities.query import SearchResult
from src.core.interfaces.vector_store import IVectorStore

logger = structlog.get_logger(__name__)


def _chunk_from_payload(payload: dict, chunk_id: str) -> Chunk:
    """Reconstruct a Chunk from Qdrant point payload."""
    return Chunk(
        id=UUID(chunk_id),
        document_id=UUID(payload["document_id"]),
        content=payload["content"],
        chunk_index=payload["chunk_index"],
        page_number=payload.get("page_number", 0),
        char_start=payload.get("char_start", 0),
        char_end=payload.get("char_end", 0),
        token_count=payload.get("token_count", 0),
    )


class QdrantVectorStore(IVectorStore):
    """
    Vector store backed by Qdrant with cosine similarity.
    All chunks are stored with metadata payload for citation reconstruction.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._client = AsyncQdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            grpc_port=settings.qdrant_grpc_port,
            prefer_grpc=True,  # gRPC is faster for large batches
        )
        self._collection = settings.qdrant_collection_name

    async def ensure_collection(self, dimension: int) -> None:
        """Create collection if it doesn't exist."""
        exists = await self.collection_exists()
        if not exists:
            await self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(
                    size=dimension,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(
                "qdrant_collection_created",
                collection=self._collection,
                dimension=dimension,
            )

    async def collection_exists(self) -> bool:
        collections = await self._client.get_collections()
        return any(c.name == self._collection for c in collections.collections)

    async def upsert(
        self,
        chunks: list[EmbeddedChunk],
        filename: str = "unknown",
    ) -> None:
        """
        Upsert embedded chunks as Qdrant points with full metadata payload.

        Args:
            chunks: List of EmbeddedChunk to store.
            filename: Original filename of the source document (stored in payload
                      so citations can reconstruct it without hitting Postgres).
        """
        if not chunks:
            return

        points = [
            PointStruct(
                id=str(ec.chunk_id),
                vector=ec.vector,
                payload={
                    "document_id": str(ec.chunk.document_id),
                    "filename": filename,          # ← stored for citation reconstruction
                    "content": ec.chunk.content,
                    "chunk_index": ec.chunk.chunk_index,
                    "page_number": ec.chunk.page_number,
                    "char_start": ec.chunk.char_start,
                    "char_end": ec.chunk.char_end,
                    "token_count": ec.chunk.token_count,
                },
            )
            for ec in chunks
        ]

        await self._client.upsert(
            collection_name=self._collection,
            points=points,
            wait=True,  # Wait for indexing to complete
        )
        logger.info("qdrant_upsert_complete", count=len(points))

    async def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        score_threshold: float = 0.0,
        document_ids: list[UUID] | None = None,
    ) -> list[SearchResult]:
        """Search for similar chunks, optionally filtered by document."""
        query_filter = None
        if document_ids:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=str(doc_id)),
                    )
                    for doc_id in document_ids
                ]
            )

        results = await self._client.search(
            collection_name=self._collection,
            query_vector=query_vector,
            limit=top_k,
            score_threshold=score_threshold,
            query_filter=query_filter,
            with_payload=True,
        )

        search_results: list[SearchResult] = []
        for hit in results:
            payload = hit.payload or {}
            chunk = _chunk_from_payload(payload, str(hit.id))
            search_results.append(
                SearchResult(
                    chunk=chunk,
                    score=hit.score,
                    document_filename=payload.get("filename", "unknown"),
                )
            )

        logger.debug("qdrant_search_complete", hits=len(search_results))
        return search_results

    async def delete_by_document(self, document_id: UUID) -> None:
        """Remove all vectors belonging to a document."""
        await self._client.delete(
            collection_name=self._collection,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=str(document_id)),
                        )
                    ]
                )
            ),
        )
        logger.info("qdrant_delete_by_document", document_id=str(document_id))
