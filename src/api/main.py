"""
FastAPI application factory.
Configures middleware, routers, lifespan events, and global error handlers.
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.api.rate_limit import limiter
from src.api.routers import documents, query
from src.config.settings import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "ragbot_starting",
        env=settings.app_env,
        llm_provider=settings.llm_provider,
        embedding_provider=settings.embedding_provider,
    )

    if settings.is_development:
        from src.infrastructure.database.models import Base
        from src.infrastructure.database.session import engine
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("db_tables_created_or_verified")

    yield

    logger.info("ragbot_shutting_down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="RAG Q&A Bot — Nghị định Xử phạt",
        description=(
            "Hệ thống hỏi đáp thông minh dựa trên RAG cho tài liệu pháp lý Việt Nam. "
            "Upload tài liệu PDF và đặt câu hỏi — hệ thống trả lời kèm trích dẫn nguồn."
        ),
        version="0.2.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── Rate Limiting ────────────────────────────────────────────────────────
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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

    # ── Static Files (Frontend) ─────────────────────────────────────────────
    import os
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.isdir(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir, html=True), name="static")

        @app.get("/", include_in_schema=False)
        async def serve_frontend():
            """Serve the frontend SPA at root URL."""
            from fastapi.responses import FileResponse
            return FileResponse(os.path.join(static_dir, "index.html"))

    # ── Health Check ────────────────────────────────────────────────────────
    @app.get("/health", tags=["System"])
    async def health_check() -> dict:
        """
        Kiểm tra trạng thái kết nối của tất cả các thành phần hệ thống.
        Trả về status=degraded nếu một trong các service phụ thuộc không khả dụng.
        """
        from sqlalchemy import text

        from src.infrastructure.database.session import AsyncSessionFactory
        from src.infrastructure.vector_store.qdrant_store import QdrantVectorStore

        checks: dict[str, str] = {}

        # Check PostgreSQL
        try:
            async with AsyncSessionFactory() as session:
                await session.execute(text("SELECT 1"))
            checks["postgres"] = "ok"
        except Exception as e:
            logger.warning("health_check_postgres_failed", error=str(e))
            checks["postgres"] = "error"

        # Check Qdrant
        try:
            qdrant = QdrantVectorStore()
            await qdrant.collection_exists()
            checks["qdrant"] = "ok"
        except Exception as e:
            logger.warning("health_check_qdrant_failed", error=str(e))
            checks["qdrant"] = "error"

        overall = "healthy" if all(v == "ok" for v in checks.values()) else "degraded"

        return {
            "status": overall,
            "version": "0.2.0",
            "env": settings.app_env,
            "llm_provider": settings.llm_provider,
            "checks": checks,
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
