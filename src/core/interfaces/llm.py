"""
ILLMProvider — abstract contract for Large Language Model inference.

Implementations: AnthropicLLMProvider, OpenAILLMProvider, OllamaLLMProvider
"""

from abc import ABC, abstractmethod

from src.core.entities.query import LLMResponse


class ILLMProvider(ABC):
    """
    Interface for generating natural language answers from a prompt.
    Decouples business logic from any specific LLM vendor.
    """

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Identifier of the underlying LLM."""
        ...

    @abstractmethod
    async def generate(self, prompt: str) -> LLMResponse:
        """
        Generate an answer given a fully-constructed RAG prompt.

        The prompt already contains the retrieved context and question.
        This method is responsible only for calling the model and
        parsing the response into an LLMResponse.

        Args:
            prompt: The complete prompt string with context and question.

        Returns:
            LLMResponse with answer, citations metadata, and token usage.
        """
        ...
