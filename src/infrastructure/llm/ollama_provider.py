"""
OllamaLLMProvider — implements ILLMProvider using Ollama local models.
Use for offline/air-gapped environments. Requires Ollama running locally.
"""

import structlog
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config.settings import get_settings
from src.core.entities.query import LLMResponse
from src.core.interfaces.llm import ILLMProvider

logger = structlog.get_logger(__name__)


class OllamaLLMProvider(ILLMProvider):
    """
    Generates answers using a local Ollama instance.
    No API key required. Model must be pulled locally first.
    Example: `ollama pull llama3.2`
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._base_url = settings.ollama_base_url
        self._model = settings.ollama_llm_model

    @property
    def model_name(self) -> str:
        return self._model

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5),
    )
    async def generate(self, prompt: str) -> LLMResponse:
        """Call Ollama's /api/generate endpoint."""
        system_prompt = (
            "Bạn là trợ lý pháp lý chuyên nghiệp, chuyên về nghị định xử phạt "
            "vi phạm hành chính của Việt Nam. Trả lời chính xác, ngắn gọn bằng "
            "tiếng Việt dựa HOÀN TOÀN vào ngữ cảnh được cung cấp."
        )

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": self._model,
                    "prompt": f"{system_prompt}\n\n{prompt}",
                    "stream": False,
                    "options": {"temperature": 0.1},
                },
            )
            response.raise_for_status()
            data = response.json()

        answer = data.get("response", "")
        logger.info("ollama_generate_complete", model=self._model)

        return LLMResponse(
            answer=answer,
            is_grounded=True,
            model_used=self._model,
            usage_tokens=0,  # Ollama doesn't always report token count
        )
