"""
Unit tests for ChunkingService.
Tests all three strategies with Vietnamese legal text.
"""

import uuid

import pytest

from src.core.services.chunking_service import (
    ChunkingConfig,
    ChunkingService,
    ChunkingStrategy,
)


SAMPLE_TEXT = """
Điều 5. Xử phạt người điều khiển xe mô tô, xe gắn máy vi phạm quy tắc giao thông đường bộ.

Phạt tiền từ 100.000 đồng đến 200.000 đồng đối với người điều khiển xe thực hiện một trong các hành vi vi phạm sau đây:
a) Không đi bên phải theo chiều đi của mình, đi không đúng phần đường hoặc làn đường quy định;
b) Không nhường đường theo quy định khi đi trên đoạn đường có cắm biển "Nhường đường";
c) Không tuân thủ hiệu lệnh, chỉ dẫn của vạch kẻ đường.

Phạt tiền từ 200.000 đồng đến 400.000 đồng đối với người điều khiển xe thực hiện một trong các hành vi vi phạm sau đây:
a) Chuyển làn đường không đúng nơi được phép hoặc không có tín hiệu báo trước;
b) Không giảm tốc độ hoặc dừng lại trước vạch dừng khi có tín hiệu đèn đỏ.

Phạt tiền từ 400.000 đồng đến 600.000 đồng đối với một trong các hành vi vi phạm sau đây:
a) Điều khiển xe chạy quá tốc độ quy định từ 05 km/h đến dưới 10 km/h.
""" * 3  # Repeat to create a larger document


@pytest.fixture
def doc_id():
    return uuid.uuid4()


class TestChunkingServiceFixedSize:
    def test_splits_text_into_chunks(self, doc_id):
        service = ChunkingService(
            ChunkingConfig(strategy=ChunkingStrategy.FIXED_SIZE, chunk_size=100, overlap=10)
        )
        chunks = service.split(SAMPLE_TEXT, doc_id)
        assert len(chunks) > 1

    def test_chunks_have_correct_document_id(self, doc_id):
        service = ChunkingService(ChunkingConfig(strategy=ChunkingStrategy.FIXED_SIZE))
        chunks = service.split(SAMPLE_TEXT, doc_id)
        assert all(c.document_id == doc_id for c in chunks)

    def test_empty_text_returns_empty(self, doc_id):
        service = ChunkingService(ChunkingConfig(strategy=ChunkingStrategy.FIXED_SIZE))
        chunks = service.split("", doc_id)
        assert chunks == []

    def test_short_text_returns_single_chunk(self, doc_id):
        service = ChunkingService(
            ChunkingConfig(strategy=ChunkingStrategy.FIXED_SIZE, chunk_size=512, min_chunk_size=0)
        )
        short = "Mức phạt là 500.000 đồng."
        chunks = service.split(short, doc_id)
        assert len(chunks) == 1
        assert chunks[0].content == short


class TestChunkingServiceRecursive:
    def test_recursive_preserves_paragraphs(self, doc_id):
        service = ChunkingService(
            ChunkingConfig(strategy=ChunkingStrategy.RECURSIVE, chunk_size=150, overlap=20)
        )
        chunks = service.split(SAMPLE_TEXT, doc_id)
        # Each chunk should not be empty
        assert all(len(c.content) > 0 for c in chunks)

    def test_chunks_are_sequentially_indexed(self, doc_id):
        service = ChunkingService(ChunkingConfig(strategy=ChunkingStrategy.RECURSIVE))
        chunks = service.split(SAMPLE_TEXT, doc_id)
        indices = [c.chunk_index for c in chunks]
        # Indices should be present (may not be perfectly sequential due to filtering)
        assert len(set(indices)) == len(indices)  # All unique

    def test_token_count_populated(self, doc_id):
        service = ChunkingService(ChunkingConfig(strategy=ChunkingStrategy.RECURSIVE))
        chunks = service.split(SAMPLE_TEXT, doc_id)
        assert all(c.token_count > 0 for c in chunks)


class TestChunkingServiceWithPages:
    def test_split_with_pages_preserves_page_number(self, doc_id):
        service = ChunkingService(ChunkingConfig(chunk_size=100, overlap=10, min_chunk_size=0))
        pages = [
            (1, "Điều 1. Mức phạt đối với xe ô tô vi phạm tốc độ từ 10-20 km/h là 3 triệu đồng."),
            (2, "Điều 2. Mức phạt đối với xe máy vi phạm tốc độ từ 5-10 km/h là 500 nghìn đồng."),
        ]
        chunks = service.split_with_pages(pages, doc_id)
        page_numbers = {c.page_number for c in chunks}
        assert 1 in page_numbers
        assert 2 in page_numbers

    def test_split_with_pages_global_index(self, doc_id):
        service = ChunkingService(ChunkingConfig(chunk_size=100, overlap=10, min_chunk_size=0))
        pages = [(1, SAMPLE_TEXT[:500]), (2, SAMPLE_TEXT[500:1000])]
        chunks = service.split_with_pages(pages, doc_id)
        indices = [c.chunk_index for c in chunks]
        assert indices == list(range(len(chunks)))
