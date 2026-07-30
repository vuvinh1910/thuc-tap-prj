"""
Unit tests for PromptBuilder.
Ensures prompt format contains required elements.
"""

import uuid

import pytest

from src.core.entities.chunk import Chunk
from src.core.entities.query import SearchResult
from src.core.services.prompt_builder import PromptBuilder


@pytest.fixture
def sample_results():
    doc_id = uuid.uuid4()
    chunks = [
        Chunk(
            document_id=doc_id,
            content=f"Nội dung đoạn {i}: Mức phạt là {i * 100}.000 đồng.",
            chunk_index=i,
            page_number=i + 1,
        )
        for i in range(3)
    ]
    return [
        SearchResult(chunk=chunk, score=0.9 - i * 0.1, document_filename="nghi-dinh.pdf")
        for i, chunk in enumerate(chunks)
    ]


class TestPromptBuilder:
    def test_prompt_contains_question(self, sample_results):
        builder = PromptBuilder()
        question = "Mức phạt vi phạm tốc độ là bao nhiêu?"
        prompt = builder.build_rag_prompt(question, sample_results)
        assert question in prompt

    def test_prompt_contains_context_chunks(self, sample_results):
        builder = PromptBuilder()
        prompt = builder.build_rag_prompt("câu hỏi?", sample_results)
        for i in range(len(sample_results)):
            assert f"[Đoạn {i + 1}]" in prompt

    def test_prompt_contains_filename(self, sample_results):
        builder = PromptBuilder()
        prompt = builder.build_rag_prompt("câu hỏi?", sample_results)
        assert "nghi-dinh.pdf" in prompt

    def test_prompt_contains_page_numbers(self, sample_results):
        builder = PromptBuilder()
        prompt = builder.build_rag_prompt("câu hỏi?", sample_results)
        for result in sample_results:
            assert f"Trang: {result.chunk.page_number}" in prompt

    def test_empty_context_still_builds_prompt(self):
        builder = PromptBuilder()
        prompt = builder.build_rag_prompt("câu hỏi?", [])
        assert "câu hỏi?" in prompt
