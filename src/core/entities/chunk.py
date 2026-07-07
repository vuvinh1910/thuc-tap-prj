"""
Chunk and EmbeddedChunk entities.
A Chunk is a text fragment extracted from a Document.
An EmbeddedChunk pairs a Chunk with its vector representation.
"""

from dataclasses import dataclass, field
from uuid import UUID, uuid4


@dataclass
class Chunk:
    """
    A text fragment from a Document, with positional metadata.
    chunk_index is the sequential position within the document.
    """

    document_id: UUID
    content: str
    chunk_index: int
    id: UUID = field(default_factory=uuid4)
    page_number: int = 0
    char_start: int = 0
    char_end: int = 0
    token_count: int = 0

    @property
    def content_preview(self) -> str:
        """Return first 100 chars for logging/display."""
        return self.content[:100] + ("..." if len(self.content) > 100 else "")

    def __len__(self) -> int:
        return len(self.content)


@dataclass
class EmbeddedChunk:
    """
    Chunk paired with its dense vector embedding.
    This is the unit that gets upserted into the vector store.
    """

    chunk: Chunk
    vector: list[float]

    @property
    def document_id(self) -> UUID:
        return self.chunk.document_id

    @property
    def chunk_id(self) -> UUID:
        return self.chunk.id

    @property
    def dimension(self) -> int:
        return len(self.vector)
