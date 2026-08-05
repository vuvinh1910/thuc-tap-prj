"""
PostgresQueryHistoryRepository — persists Q&A history to PostgreSQL.
"""

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.entities.query import Citation
from src.core.entities.query_history import QueryHistory
from src.core.interfaces.query_history_repo import IQueryHistoryRepository
from src.infrastructure.database.models import QueryHistoryModel

logger = structlog.get_logger(__name__)


def _to_entity(model: QueryHistoryModel) -> QueryHistory:
    citations = [
        Citation(
            document_id=uuid.UUID(c["document_id"]),
            chunk_id=uuid.UUID(c["chunk_id"]),
            filename=c["filename"],
            chunk_index=c["chunk_index"],
            page_number=c["page_number"],
            excerpt=c["excerpt"],
        )
        for c in (model.citations_json or [])
    ]
    return QueryHistory(
        id=model.id,
        question=model.question,
        answer=model.answer,
        is_grounded=model.is_grounded,
        model_used=model.model_used,
        usage_tokens=model.usage_tokens,
        citations=citations,
        created_at=model.created_at,
    )


class PostgresQueryHistoryRepository(IQueryHistoryRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, record: QueryHistory) -> QueryHistory:
        citations_json = [
            {
                "document_id": str(c.document_id),
                "chunk_id": str(c.chunk_id),
                "filename": c.filename,
                "chunk_index": c.chunk_index,
                "page_number": c.page_number,
                "excerpt": c.excerpt,
            }
            for c in record.citations
        ]
        model = QueryHistoryModel(
            id=record.id,
            question=record.question,
            answer=record.answer,
            is_grounded=record.is_grounded,
            model_used=record.model_used,
            usage_tokens=record.usage_tokens,
            citations_json=citations_json,
            created_at=record.created_at,
        )
        self._session.add(model)
        await self._session.commit()
        logger.info("query_history_saved", record_id=str(record.id))
        return record

    async def list_recent(self, limit: int = 20, offset: int = 0) -> list[QueryHistory]:
        result = await self._session.execute(
            select(QueryHistoryModel)
            .order_by(QueryHistoryModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [_to_entity(m) for m in result.scalars().all()]

    async def find_by_id(self, record_id: uuid.UUID) -> QueryHistory | None:
        result = await self._session.execute(
            select(QueryHistoryModel).where(QueryHistoryModel.id == record_id)
        )
        model = result.scalar_one_or_none()
        return _to_entity(model) if model else None
