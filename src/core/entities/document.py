"""
Document entity — represents an uploaded legal document.
Pure domain model with no infrastructure dependencies.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4


class DocumentStatus(str, Enum):
    """Lifecycle states of an ingested document."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Document:
    """
    Core domain entity representing an uploaded document.

    Immutable fields (id, created_at) are set at creation.
    Mutable fields (status, chunk_count) change during ingestion lifecycle.
    """

    filename: str
    file_path: str
    id: UUID = field(default_factory=uuid4)
    status: DocumentStatus = DocumentStatus.PENDING
    chunk_count: int = 0
    file_size_bytes: int = 0
    content_type: str = "application/pdf"
    error_message: str | None = None
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def mark_processing(self) -> None:
        self.status = DocumentStatus.PROCESSING
        self.updated_at = datetime.utcnow()

    def mark_completed(self, chunk_count: int) -> None:
        self.status = DocumentStatus.COMPLETED
        self.chunk_count = chunk_count
        self.updated_at = datetime.utcnow()

    def mark_failed(self, error: str) -> None:
        self.status = DocumentStatus.FAILED
        self.error_message = error
        self.updated_at = datetime.utcnow()

    @property
    def is_ready(self) -> bool:
        """True when document has been successfully ingested and can be queried."""
        return self.status == DocumentStatus.COMPLETED
