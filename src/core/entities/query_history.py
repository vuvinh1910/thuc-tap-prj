"""
QueryHistory domain entity.
Represents a persisted record of a user question and the system's response.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from src.core.entities.query import Citation


@dataclass
class QueryHistory:
    """
    Immutable record of a single Q&A interaction.
    Stored in PostgreSQL for auditing and analytics.
    """

    question: str
    answer: str
    is_grounded: bool
    model_used: str
    usage_tokens: int
    citations: list[Citation] = field(default_factory=list)
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=datetime.utcnow)
