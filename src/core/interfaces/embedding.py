"""
IEmbeddingProvider — abstract contract for generating text embeddings.

Implementations: OpenAIEmbeddingProvider
Future: HuggingFaceEmbeddingProvider, CohereEmbeddingProvider
"""

from abc import ABC, abstractmethod


class IEmbeddingProvider(ABC):
    """
    Interface for converting text into dense vector representations.
    Services depend on this interface, NOT on any concrete provider.
    """

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Identifier of the underlying embedding model."""
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Dimensionality of the output vectors."""
        ...

    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """
        Embed a single text string into a vector.

        Args:
            text: The input text to embed.

        Returns:
            A list of floats representing the dense vector.
        """
        ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Embed multiple texts in a single API call (more efficient).

        Args:
            texts: List of input strings.

        Returns:
            List of vectors, same order as input.
        """
        ...
