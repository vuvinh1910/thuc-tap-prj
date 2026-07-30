"""
Documents router — handles file upload and status endpoints.
POST /api/v1/documents/upload
GET  /api/v1/documents/{document_id}/status
GET  /api/v1/documents/
DELETE /api/v1/documents/{document_id}
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, File, HTTPException, UploadFile, status

from src.api.dependencies import DocumentRepoDep, FileStorageDep, SettingsDep
from src.api.schemas.document import (
    DocumentListResponse,
    DocumentStatusResponse,
    DocumentUploadResponse,
)
from src.core.entities.document import Document, DocumentStatus

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents"])

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "text/plain",
    "text/plain; charset=utf-8",
}


def _to_status_response(doc: Document) -> DocumentStatusResponse:
    return DocumentStatusResponse(
        document_id=doc.id,
        filename=doc.filename,
        status=doc.status.value,
        chunk_count=doc.chunk_count,
        file_size_bytes=doc.file_size_bytes,
        error_message=doc.error_message,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload tài liệu để xử lý",
)
async def upload_document(
    settings: SettingsDep,
    doc_repo: DocumentRepoDep,
    file_storage: FileStorageDep,
    file: UploadFile = File(..., description="PDF hoặc text file (tối đa 50MB)"),
) -> DocumentUploadResponse:
    """
    Upload a legal document for ingestion.

    The file is saved and an async ingest job is queued.
    Returns 202 immediately with a document_id for status polling.
    """
    # Validate content type
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Chỉ hỗ trợ PDF và text. Nhận được: {file.content_type}",
        )

    # Read and validate size
    content = await file.read()
    if len(content) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File quá lớn. Tối đa {settings.max_file_size_mb}MB.",
        )

    # Save file via injected storage
    file_path = await file_storage.save(file.filename or "document.pdf", content)

    # Create document record
    document = Document(
        filename=file.filename or "document.pdf",
        file_path=file_path,
        status=DocumentStatus.PENDING,
        file_size_bytes=len(content),
        content_type=file.content_type or "application/pdf",
    )
    saved_doc = await doc_repo.save(document)

    # Enqueue ingest job
    from src.workers.tasks.ingest_task import ingest_document
    ingest_document.delay(
        document_id=str(saved_doc.id),
        filename=saved_doc.filename,
        file_path=saved_doc.file_path,
    )

    logger.info(
        "document_upload_accepted",
        document_id=str(saved_doc.id),
        filename=saved_doc.filename,
        size_bytes=len(content),
    )

    return DocumentUploadResponse(
        document_id=saved_doc.id,
        filename=saved_doc.filename,
        status=saved_doc.status.value,
    )


@router.get(
    "/{document_id}/status",
    response_model=DocumentStatusResponse,
    summary="Kiểm tra trạng thái xử lý tài liệu",
)
async def get_document_status(
    document_id: UUID,
    doc_repo: DocumentRepoDep,
) -> DocumentStatusResponse:
    """Poll the processing status of an uploaded document."""
    doc = await doc_repo.find_by_id(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy tài liệu: {document_id}",
        )
    return _to_status_response(doc)


@router.get(
    "/",
    response_model=DocumentListResponse,
    summary="Danh sách tài liệu đã tải lên",
)
async def list_documents(
    doc_repo: DocumentRepoDep,
    limit: int = 100,
    offset: int = 0,
) -> DocumentListResponse:
    """Return paginated list of all documents."""
    docs = await doc_repo.list_all(limit=limit, offset=offset)
    return DocumentListResponse(
        items=[_to_status_response(d) for d in docs],
        total=len(docs),
        limit=limit,
        offset=offset,
    )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Xóa tài liệu và vector của nó",
)
async def delete_document(
    document_id: UUID,
    doc_repo: DocumentRepoDep,
    file_storage: FileStorageDep,
) -> None:
    """Delete a document and remove its vectors from Qdrant."""
    from src.infrastructure.vector_store.qdrant_store import QdrantVectorStore

    doc = await doc_repo.find_by_id(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy tài liệu: {document_id}",
        )

    # Remove vectors from Qdrant
    vector_store = QdrantVectorStore()
    await vector_store.delete_by_document(document_id)

    # Delete file from storage
    if await file_storage.exists(doc.file_path):
        await file_storage.delete(doc.file_path)

    # Delete DB record
    await doc_repo.delete(document_id)
    logger.info("document_deleted", document_id=str(document_id))
