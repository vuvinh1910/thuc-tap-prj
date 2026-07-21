"""
OpenAIEmbeddingProvider — implements IEmbeddingProvider using OpenAI's API.
Uses text-embedding-3-small by default (cost-efficient, good multilingual quality).
"""

import structlog
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config.settings import get_settings
from src.core.interfaces.embedding import IEmbeddingProvider

logger = structlog.get_logger(__name__)


class OpenAIEmbeddingProvider(IEmbeddingProvider):
    """
    Generates embeddings via OpenAI's Embeddings API.
    Supports batch embedding for efficient ingestion.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_embedding_model
        self._dimension = settings.openai_embedding_dimension

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def embed_text(self, text: str) -> list[float]:
        """Embed a single text. Uses retry for transient API failures."""
        response = await self._client.embeddings.create(
            model=self._model,
            input=text,
            dimensions=self._dimension,
        )
        return response.data[0].embedding

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Embed multiple texts in one API call.
        OpenAI supports up to 2048 inputs per request.
        """
        if not texts:
            return []

        # OpenAI recommends batches ≤ 2048 items
        MAX_BATCH = 2048
        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), MAX_BATCH):
            batch = texts[i : i + MAX_BATCH]
            response = await self._client.embeddings.create(
                model=self._model,
                input=batch,
                dimensions=self._dimension,
            )
            # Results are ordered by index
            batch_embeddings = [d.embedding for d in sorted(response.data, key=lambda x: x.index)]
            all_embeddings.extend(batch_embeddings)

            logger.debug(
                "embed_batch_progress",
                processed=min(i + MAX_BATCH, len(texts)),
                total=len(texts),
            )

        return all_embeddings
