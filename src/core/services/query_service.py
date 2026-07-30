"""
QueryService — handles the full RAG retrieval-augmented generation pipeline.
Receives a question, retrieves context, builds prompt, calls LLM.
"""

import structlog

from src.config.settings import get_settings
from src.core.entities.query import LLMResponse, SearchResult
from src.core.interfaces.embedding import IEmbeddingProvider
from src.core.interfaces.llm import ILLMProvider
from src.core.interfaces.vector_store import IVectorStore
from src.core.services.prompt_builder import PromptBuilder

logger = structlog.get_logger(__name__)


class QueryService:
    """
    Orchestrates the Q&A pipeline:
    embed question → retrieve → check grounding → build prompt → generate answer.
    """

    def __init__(
        self,
        embedding_provider: IEmbeddingProvider,
        vector_store: IVectorStore,
        llm_provider: ILLMProvider,
        prompt_builder: PromptBuilder | None = None,
    ) -> None:
        self._embedding = embedding_provider
        self._vector_store = vector_store
        self._llm = llm_provider
        self._prompt_builder = prompt_builder or PromptBuilder()
        self._settings = get_settings()

    async def ask(
        self,
        question: str,
        top_k: int | None = None,
        score_threshold: float | None = None,
        document_ids: list | None = None,
    ) -> LLMResponse:
        """
        Answer a question using RAG.

        Args:
            question: The user's question (in Vietnamese).
            top_k: Number of context chunks to retrieve. Defaults to settings.
            score_threshold: Minimum similarity score. Defaults to settings.
            document_ids: Optional list of UUID to restrict search scope.

        Returns:
            LLMResponse with answer + citations, or a refusal if no context found.
        """
        top_k = top_k if top_k is not None else self._settings.retrieval_top_k
        score_threshold = score_threshold if score_threshold is not None else self._settings.retrieval_score_threshold

        logger.info("query_started", question_preview=question[:80])

        # Step 1: Embed the question
        query_vector = await self._embedding.embed_text(question)

        # Step 2: Retrieve relevant chunks
        results = await self._vector_store.search(
            query_vector=query_vector,
            top_k=top_k,
            score_threshold=score_threshold,
            document_ids=document_ids,
        )

        logger.info("query_retrieved", result_count=len(results), top_k=top_k)

        # Step 3: Check if we have sufficient grounded context
        if not self._is_grounded(results, score_threshold):
            logger.info("query_no_grounded_context", question_preview=question[:80])
            return LLMResponse.not_found()

        # Step 4: Build prompt with context
        prompt = self._prompt_builder.build_rag_prompt(question, results)

        # Step 5: Generate answer
        llm_response = await self._llm.generate(prompt)

        # Step 6: Attach citations from retrieved chunks
        citations = [result.to_citation for result in results]

        logger.info(
            "query_completed",
            model=llm_response.model_used,
            citation_count=len(citations),
            tokens_used=llm_response.usage_tokens,
        )

        # Return response with citations merged
        return LLMResponse(
            answer=llm_response.answer,
            is_grounded=True,
            citations=citations,
            model_used=llm_response.model_used,
            usage_tokens=llm_response.usage_tokens,
        )

    def _is_grounded(
        self,
        results: list[SearchResult],
        score_threshold: float,
    ) -> bool:
        """
        Determine if retrieved results are sufficient to answer.
        Returns False if no results pass the minimum score threshold.
        """
        if not results:
            return False
        # At least one result must exceed the threshold
        return any(r.score >= score_threshold for r in results)
