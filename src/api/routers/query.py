"""
Query router — handles the RAG Q&A endpoint.
POST /api/v1/ask
"""

import structlog
from fastapi import APIRouter, HTTPException, status

from src.api.dependencies import QueryServiceDep
from src.api.schemas.query import AskRequest, AskResponse, CitationResponse

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/query", tags=["Q&A"])


@router.post(
    "/ask",
    response_model=AskResponse,
    summary="Đặt câu hỏi về nội dung tài liệu",
    description=(
        "Nhận câu hỏi, truy xuất đoạn văn liên quan từ tài liệu đã tải, "
        "và trả về câu trả lời kèm trích dẫn nguồn. "
        "Trả về `is_grounded=false` khi không tìm thấy ngữ cảnh phù hợp."
    ),
)
async def ask_question(
    request: AskRequest,
    query_service: QueryServiceDep,
) -> AskResponse:
    """
    RAG Q&A endpoint.

    Steps:
    1. Embed the question
    2. Retrieve top-k relevant chunks from Qdrant
    3. If no grounded context → return refusal
    4. Build prompt → call LLM → return answer + citations
    """
    try:
        llm_response = await query_service.ask(
            question=request.question,
            top_k=request.top_k,
            score_threshold=request.score_threshold,
            document_ids=request.document_ids,
        )
    except Exception as e:
        logger.error("ask_endpoint_error", error=str(e), question=request.question[:80])
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Lỗi xử lý câu hỏi. Vui lòng thử lại.",
        )

    return AskResponse(
        answer=llm_response.answer,
        is_grounded=llm_response.is_grounded,
        citations=[
            CitationResponse(
                document_id=c.document_id,
                filename=c.filename,
                page_number=c.page_number,
                chunk_index=c.chunk_index,
                excerpt=c.excerpt,
            )
            for c in llm_response.citations
        ],
        model_used=llm_response.model_used,
        usage_tokens=llm_response.usage_tokens,
    )
