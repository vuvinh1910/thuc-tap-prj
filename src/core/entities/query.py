"""
Query-related value objects: SearchResult, Citation, LLMResponse.
These are immutable outputs from the retrieval and generation pipeline.
"""

from dataclasses import dataclass, field
from uuid import UUID

from src.core.entities.chunk import Chunk


@dataclass(frozen=True)
class Citation:
    """
    A traceable reference to the source of an answer.
    Provides enough context for the user to verify the answer.
    """

    document_id: UUID
    chunk_id: UUID
    filename: str
    chunk_index: int
    page_number: int
    excerpt: str  # The relevant text fragment used in the answer


@dataclass(frozen=True)
class SearchResult:
    """
    A retrieved chunk from the vector store, with its similarity score.
    score is cosine similarity in [0, 1] — higher is more relevant.
    """

    chunk: Chunk
    score: float
    document_filename: str

    @property
    def to_citation(self) -> Citation:
        """Convert a search result into a user-facing citation."""
        return Citation(
            document_id=self.chunk.document_id,
            chunk_id=self.chunk.id,
            filename=self.document_filename,
            chunk_index=self.chunk.chunk_index,
            page_number=self.chunk.page_number,
            excerpt=self.chunk.content_preview,
        )


@dataclass(frozen=True)
class LLMResponse:
    """
    The final answer from the RAG pipeline.

    is_grounded=False means the system could not find relevant context
    and will return a refusal message instead of hallucinating.
    """

    answer: str
    is_grounded: bool
    citations: list[Citation] = field(default_factory=list)
    model_used: str = ""
    usage_tokens: int = 0

    @classmethod
    def not_found(cls) -> "LLMResponse":
        """Standard 'no context' refusal response."""
        return cls(
            answer=(
                "Xin lỗi, tôi không tìm thấy thông tin liên quan đến câu hỏi này "
                "trong các tài liệu đã tải lên. Vui lòng kiểm tra lại câu hỏi hoặc "
                "tải lên tài liệu có chứa thông tin cần thiết."
            ),
            is_grounded=False,
            citations=[],
        )
