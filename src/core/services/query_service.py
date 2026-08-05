"""
QueryService — handles the full RAG retrieval-augmented generation pipeline.
Receives a question, retrieves context, builds prompt, calls LLM.
"""

import structlog

from src.config.settings import get_settings
from src.core.entities.query import LLMResponse, SearchResult
from src.core.entities.query_history import QueryHistory
from src.core.interfaces.embedding import IEmbeddingProvider
from src.core.interfaces.llm import ILLMProvider
from src.core.interfaces.query_history_repo import IQueryHistoryRepository
from src.core.interfaces.vector_store import IVectorStore
from src.core.services.prompt_builder import PromptBuilder

logger = structlog.get_logger(__name__)


class QueryService:
    """
    Orchestrates the Q&A pipeline:
    embed question → retrieve → check grounding → build prompt → generate answer → save history.
    """

    def __init__(
        self,
        embedding_provider: IEmbeddingProvider,
        vector_store: IVectorStore,
        llm_provider: ILLMProvider,
        prompt_builder: PromptBuilder | None = None,
        history_repo: IQueryHistoryRepository | None = None,
    ) -> None:
        self._embedding = embedding_provider
        self._vector_store = vector_store
        self._llm = llm_provider
        self._prompt_builder = prompt_builder or PromptBuilder()
        self._history_repo = history_repo
        self._settings = get_settings()

    async def ask(
        self,
        question: str,
        top_k: int | None = None,
        score_threshold: float | None = None,
        document_ids: list | None = None,
    ) -> LLMResponse:
        top_k = top_k if top_k is not None else self._settings.retrieval_top_k
        score_threshold = (
            score_threshold
            if score_threshold is not None
            else self._settings.retrieval_score_threshold
        )

        logger.info("query_started", question_preview=question[:80])

        query_vector = await self._embedding.embed_text(question)

        results = await self._vector_store.search(
            query_vector=query_vector,
            top_k=top_k,
            score_threshold=score_threshold,
            document_ids=document_ids,
        )

        logger.info("query_retrieved", result_count=len(results), top_k=top_k)

        if not self._is_grounded(results, score_threshold):
            logger.info("query_no_grounded_context", question_preview=question[:80])
            response = LLMResponse.not_found()
            await self._save_history(question, response)
            return response

        prompt = self._prompt_builder.build_rag_prompt(question, results)
        llm_response = await self._llm.generate(prompt)
        citations = [result.to_citation for result in results]

        logger.info(
            "query_completed",
            model=llm_response.model_used,
            citation_count=len(citations),
            tokens_used=llm_response.usage_tokens,
        )

        response = LLMResponse(
            answer=llm_response.answer,
            is_grounded=True,
            citations=citations,
            model_used=llm_response.model_used,
            usage_tokens=llm_response.usage_tokens,
        )
        await self._save_history(question, response)
        return response

    async def _save_history(self, question: str, response: LLMResponse) -> None:
        """Persist the Q&A record asynchronously. Failures are logged but never bubble up."""
        if self._history_repo is None:
            return
        try:
            record = QueryHistory(
                question=question,
                answer=response.answer,
                is_grounded=response.is_grounded,
                model_used=response.model_used,
                usage_tokens=response.usage_tokens,
                citations=list(response.citations),
            )
            await self._history_repo.save(record)
        except Exception as e:
            logger.warning("query_history_save_failed", error=str(e))

    def _is_grounded(self, results: list[SearchResult], score_threshold: float) -> bool:
        if not results:
            return False
        return any(r.score >= score_threshold for r in results)
