"""
Unit tests for QueryService.
Tests grounding logic and full pipeline with mocked dependencies.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.entities.chunk import Chunk
from src.core.entities.query import LLMResponse, SearchResult
from src.core.interfaces.embedding import IEmbeddingProvider
from src.core.interfaces.llm import ILLMProvider
from src.core.interfaces.vector_store import IVectorStore
from src.core.services.query_service import QueryService


@pytest.fixture
def doc_id():
    return uuid.uuid4()


@pytest.fixture
def sample_search_results(doc_id):
    chunk = Chunk(
        document_id=doc_id,
        content="Mức phạt vi phạm tốc độ từ 10-20km/h là 3 triệu đồng.",
        chunk_index=0,
        page_number=5,
    )
    return [
        SearchResult(chunk=chunk, score=0.85, document_filename="nghi-dinh-100.pdf")
    ]


def make_query_service(
    search_results=None,
    llm_answer="Câu trả lời test",
    score_threshold=0.35,
) -> QueryService:
    embedding = MagicMock(spec=IEmbeddingProvider)
    embedding.embed_text = AsyncMock(return_value=[0.1, 0.2, 0.3, 0.4])

    vector_store = MagicMock(spec=IVectorStore)
    vector_store.search = AsyncMock(return_value=search_results or [])

    llm = MagicMock(spec=ILLMProvider)
    llm.model_name = "mock-llm"
    llm.generate = AsyncMock(
        return_value=LLMResponse(
            answer=llm_answer,
            is_grounded=True,
            model_used="mock-llm",
        )
    )

    return QueryService(
        embedding_provider=embedding,
        vector_store=vector_store,
        llm_provider=llm,
    )


class TestQueryServiceGrounding:
    async def test_returns_not_found_when_no_results(self):
        service = make_query_service(search_results=[])
        response = await service.ask("Mức phạt là bao nhiêu?")
        assert response.is_grounded is False
        assert "không tìm thấy" in response.answer.lower()

    async def test_returns_not_found_when_score_below_threshold(self, doc_id):
        chunk = Chunk(document_id=doc_id, content="test", chunk_index=0)
        low_score_results = [
            SearchResult(chunk=chunk, score=0.1, document_filename="test.pdf")
        ]
        service = make_query_service(search_results=low_score_results)
        response = await service.ask("test?", score_threshold=0.5)
        assert response.is_grounded is False

    async def test_returns_answer_when_context_found(self, sample_search_results):
        service = make_query_service(
            search_results=sample_search_results,
            llm_answer="Mức phạt là 3 triệu đồng.",
        )
        response = await service.ask("Mức phạt vi phạm tốc độ là bao nhiêu?")
        assert response.is_grounded is True
        assert "3 triệu" in response.answer

    async def test_citations_populated_from_search_results(self, sample_search_results):
        service = make_query_service(search_results=sample_search_results)
        response = await service.ask("Câu hỏi test?")
        assert len(response.citations) == len(sample_search_results)
        assert response.citations[0].filename == "nghi-dinh-100.pdf"
        assert response.citations[0].page_number == 5

    async def test_llm_not_called_when_no_grounded_context(self):
        """LLM should NOT be called when there's no context — saves API cost."""
        embedding = MagicMock(spec=IEmbeddingProvider)
        embedding.embed_text = AsyncMock(return_value=[0.1, 0.2, 0.3, 0.4])

        vector_store = MagicMock(spec=IVectorStore)
        vector_store.search = AsyncMock(return_value=[])

        llm = MagicMock(spec=ILLMProvider)
        llm.generate = AsyncMock()

        service = QueryService(
            embedding_provider=embedding,
            vector_store=vector_store,
            llm_provider=llm,
        )
        await service.ask("test?")
        llm.generate.assert_not_called()
