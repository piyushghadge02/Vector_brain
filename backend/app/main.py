"""VectorBrain FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from slowapi.errors import RateLimitExceeded

from app.api import health
from app.api.v1.router import v1_router
from app.config import get_settings
from app.core.errors import (
    AppError,
    app_error_handler,
    error_envelope,
    http_exception_handler,
    unhandled_error_handler,
)
from app.core.logging import configure_logging, logger
from app.core.middleware import RequestIdMiddleware
from app.db.session import create_engine, create_session_factory
from app.services import (
    DoclingHybridChunker,
    DoclingProcessor,
    GroqLLMProvider,
    MiniLMEmbeddingProvider,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logger.info("starting %s (env=%s)", settings.app_name, settings.env)
    # Engine is created here — inside the serving event loop — never at
    # import time, so it is always bound to the correct loop.
    engine = create_engine(settings.database_url)
    app.state.db_engine = engine
    app.state.session_factory = create_session_factory(engine)
    # Heavy ML singletons: constructed once, models load lazily on first use
    # so startup stays fast and tests can substitute stubs.
    app.state.docling_processor = DoclingProcessor()
    app.state.chunker = DoclingHybridChunker(
        tokenizer_id=settings.embedding_model,
        max_tokens=settings.chunk_max_tokens,
    )
    app.state.embedder = MiniLMEmbeddingProvider(model_id=settings.embedding_model)
    # The Groq client is created only when a key is configured; otherwise
    # chat endpoints fail fast with 503 (LLM_NOT_CONFIGURED).
    if settings.groq_api_key:
        app.state.llm = GroqLLMProvider(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
            timeout_seconds=settings.groq_timeout_seconds,
        )
        logger.info("groq client configured (model=%s)", settings.groq_model)
    else:
        app.state.llm = None
        logger.warning("GROQ_API_KEY not set — /api/v1/chat/query will return 503")
    # Warm up Docling converter in background to avoid first-request latency.
    # This runs in a thread pool to not block the event loop.
    import anyio
    try:
        await anyio.to_thread.run_sync(app.state.docling_processor.warmup)
        logger.info("Docling warmup completed")
    except Exception as exc:
        logger.warning("Docling warmup failed (non-fatal): %s", exc)
    yield
    await engine.dispose()
    logger.info("shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, json_logs=settings.env == "prod")

    app = FastAPI(
        title=settings.app_name,
        description="Multi-document AI research assistant (RAG over PDFs).",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.env != "prod" else None,
        redoc_url="/redoc" if settings.env != "prod" else None,
    )

    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Pydantic 422s use the same envelope as every other API error."""
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=422,
            content=error_envelope(
                "VALIDATION_ERROR",
                "The request was invalid.",
                request_id,
                details={"errors": jsonable_encoder(exc.errors())},
            ),
        )

    app.add_exception_handler(RequestValidationError, validation_error_handler)

    async def rate_limit_handler(
        request: Request, exc: RateLimitExceeded
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=429,
            content=error_envelope(
                "RATE_LIMITED",
                "Too many questions — please wait a moment and try again.",
                request_id,
            ),
        )

    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

    # Unversioned operational endpoints
    app.include_router(health.router, prefix="/api")
    # Versioned product API (Phase 2+)
    app.include_router(v1_router, prefix="/api")

    return app


app = create_app()
