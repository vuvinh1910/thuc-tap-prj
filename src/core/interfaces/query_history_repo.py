"""
IQueryHistoryRepository — interface for persisting Q&A history.
"""

from abc import ABC, abstractmethod
from uuid import UUID

from src.core.entities.query_history import QueryHistory


class IQueryHistoryRepository(ABC):
    @abstractmethod
    async def save(self, record: QueryHistory) -> QueryHistory:
        """Persist a QueryHistory record."""

    @abstractmethod
    async def list_recent(self, limit: int = 20, offset: int = 0) -> list[QueryHistory]:
        """Return most recent query records, newest first."""

    @abstractmethod
    async def find_by_id(self, record_id: UUID) -> QueryHistory | None:
        """Find a single record by ID."""
