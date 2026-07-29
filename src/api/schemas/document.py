"""
API request/response schemas for document endpoints.
Separate from domain entities to allow API versioning independently.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentUploadResponse(BaseModel):
    """Response after uploading a document (202 Accepted)."""

    document_id: UUID
    filename: str
    status: str
    message: str = "Tài liệu đang được xử lý. Kiểm tra trạng thái qua endpoint /status."


class DocumentStatusResponse(BaseModel):
    """Response for document status polling."""

    document_id: UUID
    filename: str
    status: str
    chunk_count: int
    file_size_bytes: int
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    """Paginated list of documents."""

    items: list[DocumentStatusResponse]
    total: int
    limit: int = Field(default=100)
    offset: int = Field(default=0)
