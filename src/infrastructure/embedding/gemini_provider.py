"""
GeminiEmbeddingProvider — implements IEmbeddingProvider using Google Gemini API.
"""

import structlog
from google import genai

from src.config.settings import get_settings
from src.core.interfaces.embedding import IEmbeddingProvider

logger = structlog.get_logger(__name__)


class GeminiEmbeddingProvider(IEmbeddingProvider):
    """
    Embedding Provider that uses Google's genai SDK.
    """

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required when using Gemini provider")

        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = settings.gemini_embedding_model

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single string."""
        response = await self._client.aio.models.embed_content(
            model=self._model,
            contents=text,
        )
        return response.embeddings[0].values

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for a batch of strings.
        Note: gemini-1.5 API accepts multiple contents for embedding.
        """
        if not texts:
            return []
            
        try:
            response = await self._client.aio.models.embed_content(
                model=self._model,
                contents=texts,
            )
            logger.info("gemini_embed_batch_success", count=len(texts))
            return [emb.values for emb in response.embeddings]
        except Exception as e:
            logger.error("gemini_embed_batch_error", error=str(e))
            raise e
