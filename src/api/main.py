"""
FastAPI application factory.
Configures middleware, routers, lifespan events, and global error handlers.
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.routers import documents, query
from src.config.settings import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Runs startup logic before yield, teardown after.
    """
    logger.info(
        "ragbot_starting",
        env=settings.app_env,
        llm_provider=settings.llm_provider,
        embedding_provider=settings.embedding_provider,
    )

    # Ensure DB tables exist (for development convenience)
    if settings.is_development:
        from src.infrastructure.database.models import Base
        from src.infrastructure.database.session import engine
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("db_tables_created_or_verified")

    yield

    logger.info("ragbot_shutting_down")


def create_app() -> FastAPI:
    """Application factory — creates and configures the FastAPI app."""
    app = FastAPI(
        title="RAG Q&A Bot — Nghị định Xử phạt",
        description=(
            "Hệ thống hỏi đáp thông minh dựa trên RAG cho tài liệu pháp lý Việt Nam. "
            "Upload tài liệu PDF và đặt câu hỏi — hệ thống trả lời kèm trích dẫn nguồn."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS ────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ─────────────────────────────────────────────────────────────
    app.include_router(documents.router, prefix="/api/v1")
    app.include_router(query.router, prefix="/api/v1")

    # ── Health Check ────────────────────────────────────────────────────────
    @app.get("/health", tags=["System"])
    async def health_check() -> dict:
        return {
            "status": "healthy",
            "version": "0.1.0",
            "env": settings.app_env,
            "llm_provider": settings.llm_provider,
        }

    # ── Global Exception Handler ─────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "unhandled_exception",
            path=request.url.path,
            error=str(exc),
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Lỗi hệ thống. Vui lòng thử lại sau."},
        )

    return app


app = create_app()
