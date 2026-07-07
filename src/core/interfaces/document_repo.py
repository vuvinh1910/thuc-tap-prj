"""
IDocumentRepository — abstract contract for document persistence.

Implementations: PostgresDocumentRepository
Future: MongoDocumentRepository, InMemoryDocumentRepository (tests)
"""

from abc import ABC, abstractmethod
from uuid import UUID

from src.core.entities.document import Document, DocumentStatus


class IDocumentRepository(ABC):
    """
    Interface for CRUD operations on Document entities.
    Isolates the domain from the underlying database technology.
    """

    @abstractmethod
    async def save(self, document: Document) -> Document:
        """
        Persist a new document record.

        Args:
            document: The Document entity to save.

        Returns:
            The saved Document (with any DB-generated fields populated).
        """
        ...

    @abstractmethod
    async def find_by_id(self, document_id: UUID) -> Document | None:
        """
        Retrieve a document by its UUID.

        Args:
            document_id: The document UUID.

        Returns:
            The Document if found, None otherwise.
        """
        ...

    @abstractmethod
    async def update_status(
        self,
        document_id: UUID,
        status: DocumentStatus,
        chunk_count: int | None = None,
        error_message: str | None = None,
    ) -> None:
        """
        Update the status (and optionally chunk_count/error) of a document.

        Args:
            document_id: Target document UUID.
            status: New DocumentStatus value.
            chunk_count: Number of chunks after successful ingestion.
            error_message: Error description if status is FAILED.
        """
        ...

    @abstractmethod
    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Document]:
        """
        Paginated list of all documents.

        Args:
            limit: Maximum number of results.
            offset: Number of records to skip.

        Returns:
            List of Document entities.
        """
        ...

    @abstractmethod
    async def delete(self, document_id: UUID) -> bool:
        """
        Delete a document record.

        Args:
            document_id: UUID of the document to delete.

        Returns:
            True if deleted, False if not found.
        """
        ...
