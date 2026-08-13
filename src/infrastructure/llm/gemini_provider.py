"""
GeminiLLMProvider — implements ILLMProvider using Google Gemini API.
"""

import structlog
from google import genai
from google.genai import types

from src.config.settings import get_settings
from src.core.interfaces.llm import ILLMProvider

logger = structlog.get_logger(__name__)


class GeminiLLMProvider(ILLMProvider):
    """
    LLM Provider that uses Google's new genai SDK to interact with Gemini models.
    """

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required when using Gemini provider")

        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = settings.gemini_llm_model

    async def generate_answer(self, prompt: str) -> str:
        """
        Generate answer from Gemini using standard prompt.
        """
        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,
                ),
            )
            logger.info("gemini_llm_success", model=self._model)
            return response.text or ""
        except Exception as e:
            logger.error("gemini_llm_error", error=str(e))
            raise e
