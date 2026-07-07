"""Core interfaces package."""

from src.core.interfaces.document_repo import IDocumentRepository
from src.core.interfaces.embedding import IEmbeddingProvider
from src.core.interfaces.file_storage import IFileStorage
from src.core.interfaces.llm import ILLMProvider
from src.core.interfaces.vector_store import IVectorStore

__all__ = [
    "IDocumentRepository",
    "IEmbeddingProvider",
    "IFileStorage",
    "ILLMProvider",
    "IVectorStore",
]
