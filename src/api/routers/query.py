"""
Query router — handles the RAG Q&A and history endpoints.
POST /api/v1/query/ask
GET  /api/v1/query/history
"""

import structlog
from fastapi import APIRouter, HTTPException, Request, status

from src.api.dependencies import QueryHistoryRepoDep, QueryServiceDep
from src.api.main import limiter
from src.api.schemas.query import AskRequest, AskResponse, CitationResponse, QueryHistoryResponse

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/query", tags=["Q&A"])


@router.post(
    "/ask",
    response_model=AskResponse,
    summary="Đặt câu hỏi về nội dung tài liệu",
    description=(
        "Nhận câu hỏi, truy xuất đoạn văn liên quan từ tài liệu đã tải, "
        "và trả về câu trả lời kèm trích dẫn nguồn. "
        "Trả về `is_grounded=false` khi không tìm thấy ngữ cảnh phù hợp. "
        "Giới hạn: 20 yêu cầu/phút."
    ),
)
@limiter.limit("20/minute")
async def ask_question(
    request: Request,
    body: AskRequest,
    query_service: QueryServiceDep,
) -> AskResponse:
    try:
        llm_response = await query_service.ask(
            question=body.question,
            top_k=body.top_k,
            score_threshold=body.score_threshold,
            document_ids=body.document_ids,
        )
    except Exception as e:
        logger.error("ask_endpoint_error", error=str(e), question=body.question[:80])
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


@router.get(
    "/history",
    response_model=list[QueryHistoryResponse],
    summary="Lịch sử các câu hỏi đã hỏi",
    description="Trả về danh sách các câu hỏi và câu trả lời gần nhất, sắp xếp mới nhất trước.",
)
async def get_history(
    history_repo: QueryHistoryRepoDep,
    limit: int = 20,
    offset: int = 0,
) -> list[QueryHistoryResponse]:
    records = await history_repo.list_recent(limit=limit, offset=offset)
    return [
        QueryHistoryResponse(
            id=r.id,
            question=r.question,
            answer=r.answer,
            is_grounded=r.is_grounded,
            model_used=r.model_used,
            usage_tokens=r.usage_tokens,
            citation_count=len(r.citations),
            created_at=r.created_at,
        )
        for r in records
    ]
