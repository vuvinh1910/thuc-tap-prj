"""
PostgresDocumentRepository — SQLAlchemy implementation of IDocumentRepository.
Translates between DocumentModel (ORM) and Document (domain entity).
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.entities.document import Document, DocumentStatus
from src.core.interfaces.document_repo import IDocumentRepository
from src.infrastructure.database.models import DocumentModel


def _to_entity(model: DocumentModel) -> Document:
    """Map ORM model → domain entity."""
    return Document(
        id=model.id,
        filename=model.filename,
        file_path=model.file_path,
        status=DocumentStatus(model.status),
        chunk_count=model.chunk_count,
        file_size_bytes=model.file_size_bytes,
        content_type=model.content_type,
        error_message=model.error_message,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _to_model(entity: Document) -> DocumentModel:
    """Map domain entity → ORM model."""
    return DocumentModel(
        id=entity.id,
        filename=entity.filename,
        file_path=entity.file_path,
        status=entity.status.value,
        chunk_count=entity.chunk_count,
        file_size_bytes=entity.file_size_bytes,
        content_type=entity.content_type,
        error_message=entity.error_message,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


class PostgresDocumentRepository(IDocumentRepository):
    """Concrete repository backed by PostgreSQL via async SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, document: Document) -> Document:
        model = _to_model(document)
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return _to_entity(model)

    async def find_by_id(self, document_id: UUID) -> Document | None:
        result = await self._session.execute(
            select(DocumentModel).where(DocumentModel.id == document_id)
        )
        model = result.scalar_one_or_none()
        return _to_entity(model) if model else None

    async def update_status(
        self,
        document_id: UUID,
        status: DocumentStatus,
        chunk_count: int | None = None,
        error_message: str | None = None,
    ) -> None:
        values: dict = {"status": status.value, "updated_at": datetime.utcnow()}
        if chunk_count is not None:
            values["chunk_count"] = chunk_count
        if error_message is not None:
            values["error_message"] = error_message

        await self._session.execute(
            update(DocumentModel)
            .where(DocumentModel.id == document_id)
            .values(**values)
        )
        await self._session.commit()

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Document]:
        result = await self._session.execute(
            select(DocumentModel)
            .order_by(DocumentModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [_to_entity(m) for m in result.scalars().all()]

    async def delete(self, document_id: UUID) -> bool:
        model = await self._session.get(DocumentModel, document_id)
        if not model:
            return False
        await self._session.delete(model)
        await self._session.commit()
        return True
