"""
PromptBuilder — constructs RAG prompts for the LLM.
Centralized prompt engineering, easy to iterate without touching services.
"""

from src.core.entities.query import SearchResult


class PromptBuilder:
    """
    Builds structured prompts for the RAG pipeline.

    Design note: Prompt construction is separated from QueryService
    to make it easy to A/B test different prompt formats.
    """

    def build_rag_prompt(
        self,
        question: str,
        context_chunks: list[SearchResult],
    ) -> str:
        """
        Build a RAG prompt with retrieved context and user question.

        The prompt instructs the model to:
        1. Answer based ONLY on provided context
        2. Cite specific sections
        3. Refuse if context is insufficient

        Args:
            question: The user's question in Vietnamese.
            context_chunks: Retrieved chunks from the vector store.

        Returns:
            Complete prompt string ready for the LLM.
        """
        context_blocks: list[str] = []

        for i, result in enumerate(context_chunks, start=1):
            chunk = result.chunk
            block = (
                f"[Đoạn {i}] "
                f"(Tài liệu: {result.document_filename}, "
                f"Trang: {chunk.page_number}, "
                f"Đoạn số: {chunk.chunk_index})\n"
                f"{chunk.content}"
            )
            context_blocks.append(block)

        context_text = "\n\n---\n\n".join(context_blocks)

        prompt = f"""Dưới đây là các đoạn trích từ tài liệu pháp lý liên quan đến câu hỏi của bạn:

==================== NGỮ CẢNH ====================
{context_text}
==================== KẾT THÚC NGỮ CẢNH ====================

Câu hỏi: {question}

Hướng dẫn trả lời:
1. Chỉ trả lời dựa trên các đoạn ngữ cảnh được cung cấp ở trên.
2. Nếu thông tin không đủ để trả lời, hãy nói rõ điều đó.
3. Trích dẫn số đoạn (ví dụ: [Đoạn 1]) khi sử dụng thông tin từ đó.
4. Trả lời bằng tiếng Việt, ngắn gọn và chính xác.
5. KHÔNG suy diễn hoặc bổ sung thông tin ngoài ngữ cảnh.

Câu trả lời:"""

        return prompt

    def build_no_context_response_prompt(self, question: str) -> str:
        """
        Build a prompt that explicitly instructs refusal when no context is found.
        Only used when score_threshold filtering returns zero results.
        """
        return (
            f"Người dùng hỏi: '{question}'\n\n"
            "Không tìm thấy thông tin liên quan trong các tài liệu đã tải lên. "
            "Hãy thông báo lịch sự rằng bạn không có dữ liệu để trả lời câu hỏi này."
        )
