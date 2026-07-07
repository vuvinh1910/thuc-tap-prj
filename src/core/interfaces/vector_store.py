"""
IVectorStore — abstract contract for vector similarity search.

Implementations: QdrantVectorStore
Future: PgVectorStore, ChromaVectorStore
"""

from abc import ABC, abstractmethod
from uuid import UUID

from src.core.entities.chunk import EmbeddedChunk
from src.core.entities.query import SearchResult


class IVectorStore(ABC):
    """
    Interface for storing and retrieving dense vectors.
    Supports metadata filtering for multi-document retrieval.
    """

    @abstractmethod
    async def upsert(
        self,
        chunks: list[EmbeddedChunk],
        filename: str = "unknown",
    ) -> None:
        """
        Insert or update a batch of embedded chunks.

        Args:
            chunks: List of EmbeddedChunk objects to store.
            filename: Original document filename — stored in payload for
                      citation reconstruction without extra DB lookups.
        """
        ...

    @abstractmethod
    async def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        score_threshold: float = 0.0,
        document_ids: list[UUID] | None = None,
    ) -> list[SearchResult]:
        """
        Find the top-k most similar chunks to a query vector.

        Args:
            query_vector: The query embedding to search against.
            top_k: Number of results to return.
            score_threshold: Minimum similarity score (0–1) to include.
            document_ids: Optional filter — restrict to specific documents.

        Returns:
            Ranked list of SearchResult, highest score first.
        """
        ...

    @abstractmethod
    async def delete_by_document(self, document_id: UUID) -> None:
        """
        Remove all vectors belonging to a specific document.
        Called when a document is deleted or re-ingested.

        Args:
            document_id: UUID of the document to remove.
        """
        ...

    @abstractmethod
    async def collection_exists(self) -> bool:
        """Check if the target collection/index is initialized."""
        ...

    @abstractmethod
    async def ensure_collection(self, dimension: int) -> None:
        """
        Create the collection if it does not exist.

        Args:
            dimension: Vector dimension (must match embedding model).
        """
        ...
