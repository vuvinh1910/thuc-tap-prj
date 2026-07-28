"""
OpenAILLMProvider — implements ILLMProvider using OpenAI Chat Completions API.
Alternative to AnthropicLLMProvider — switch via LLM_PROVIDER env var.
"""

import structlog
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config.settings import get_settings
from src.core.entities.query import LLMResponse
from src.core.interfaces.llm import ILLMProvider

logger = structlog.get_logger(__name__)


class OpenAILLMProvider(ILLMProvider):
    """
    Generates answers using OpenAI's Chat Completions API.
    Default: gpt-4o-mini (cost-efficient, good Vietnamese support).
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_llm_model

    @property
    def model_name(self) -> str:
        return self._model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def generate(self, prompt: str) -> LLMResponse:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Bạn là trợ lý pháp lý chuyên nghiệp, chuyên về nghị định "
                        "xử phạt vi phạm hành chính của Việt Nam. Trả lời chính xác, "
                        "ngắn gọn bằng tiếng Việt dựa HOÀN TOÀN vào ngữ cảnh được cung cấp."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=2048,
            temperature=0.1,  # Low temperature for factual legal answers
        )

        answer = response.choices[0].message.content or ""
        usage_tokens = (response.usage.total_tokens if response.usage else 0)

        logger.info(
            "openai_generate_complete",
            model=self._model,
            tokens_used=usage_tokens,
        )

        return LLMResponse(
            answer=answer,
            is_grounded=True,
            model_used=self._model,
            usage_tokens=usage_tokens,
        )
