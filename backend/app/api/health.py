"""Liveness + dependency health.

``GET /api/health`` reports whether PostgreSQL is reachable and whether
the pgvector extension is installed. Returns 200 when the database is
healthy, 503 otherwise — suitable for Docker/K8s healthchecks.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_app_settings, get_session
from app.config import Settings
from app.core.logging import logger
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


async def _check_database(session: AsyncSession) -> tuple[bool, bool]:
    """Return (db_reachable, pgvector_installed). Never raises.

    Catches broad ``Exception`` deliberately: asyncpg can surface raw
    socket errors (e.g. ConnectionRefusedError) that SQLAlchemy does not
    always wrap, and a health check must report instead of raise.
    """
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 — health check must not raise
        logger.warning("healthcheck: database unreachable (%s)", type(exc).__name__)
        return False, False
    try:
        row = (
            await session.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            )
        ).first()
        return True, row is not None
    except Exception as exc:  # noqa: BLE001 — health check must not raise
        logger.warning(
            "healthcheck: pg_extension query failed (%s)", type(exc).__name__
        )
        return True, False


@router.get("/health", response_model=HealthResponse)
async def health_check(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
) -> JSONResponse:
    db_ok, pgvector_ok = await _check_database(session)

    payload = HealthResponse(
        status="ok" if db_ok else "degraded",
        service=settings.app_name,
        env=settings.env,
        database="connected" if db_ok else "unreachable",
        pgvector="available" if pgvector_ok else "missing",
        # Placeholders until Phase 2/3 — never expose the actual key.
        embeddings="not loaded (Phase 2)",
        groq_configured=bool(settings.groq_api_key),
    )
    return JSONResponse(
        status_code=200 if db_ok else 503,
        content=payload.model_dump(),
    )
