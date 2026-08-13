"""
API request/response schemas for query (Q&A) endpoints.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    """Request body for POST /ask."""

    question: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="Câu hỏi về nội dung tài liệu đã tải lên.",
        examples=["Mức phạt vi phạm tốc độ tối đa trên đường cao tốc là bao nhiêu?"],
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Số đoạn văn bản liên quan tối đa để truy xuất.",
    )
    score_threshold: float = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
        description="Ngưỡng điểm tương đồng tối thiểu (0–1).",
    )
    document_ids: list[UUID] | None = Field(
        default=None,
        description="Giới hạn tìm kiếm trong các tài liệu cụ thể (tùy chọn).",
    )


class CitationResponse(BaseModel):
    """A single source citation in the answer."""

    document_id: UUID
    filename: str
    page_number: int
    chunk_index: int
    excerpt: str


class AskResponse(BaseModel):
    """Response for POST /ask."""

    answer: str
    is_grounded: bool = Field(
        description="True nếu câu trả lời dựa trên tài liệu; False nếu không tìm thấy."
    )
    citations: list[CitationResponse] = Field(default_factory=list)
    model_used: str = ""
    usage_tokens: int = 0


class QueryHistoryResponse(BaseModel):
    """Summary of a past Q&A interaction for GET /query/history."""

    id: UUID
    question: str
    answer: str
    is_grounded: bool
    model_used: str
    usage_tokens: int
    citation_count: int
    created_at: datetime

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}
