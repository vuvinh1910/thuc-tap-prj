"""
AnthropicLLMProvider — implements ILLMProvider using Anthropic Claude API.
Recommended for Vietnamese legal Q&A due to excellent instruction-following.
"""

import structlog
from anthropic import AsyncAnthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config.settings import get_settings
from src.core.entities.query import LLMResponse
from src.core.interfaces.llm import ILLMProvider

logger = structlog.get_logger(__name__)


class AnthropicLLMProvider(ILLMProvider):
    """
    Generates answers using Anthropic's Claude models.
    Default: claude-3-5-haiku-20241022 (fast, cheap, good Vietnamese).
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._model = settings.anthropic_llm_model

    @property
    def model_name(self) -> str:
        return self._model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def generate(self, prompt: str) -> LLMResponse:
        """
        Call Anthropic Messages API and parse response.
        The prompt contains context + question already constructed by PromptBuilder.
        """
        logger.debug("anthropic_generate_start", model=self._model)

        message = await self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=(
                "Bạn là trợ lý pháp lý chuyên nghiệp, chuyên về nghị định xử phạt "
                "vi phạm hành chính của Việt Nam. Trả lời chính xác, ngắn gọn bằng "
                "tiếng Việt dựa HOÀN TOÀN vào ngữ cảnh được cung cấp."
            ),
            messages=[{"role": "user", "content": prompt}],
        )

        answer = message.content[0].text
        usage_tokens = message.usage.input_tokens + message.usage.output_tokens

        logger.info(
            "anthropic_generate_complete",
            model=self._model,
            tokens_used=usage_tokens,
        )

        return LLMResponse(
            answer=answer,
            is_grounded=True,
            model_used=self._model,
            usage_tokens=usage_tokens,
        )
