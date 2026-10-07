"""Versioned API router.

Phase 2+ routers register here under ``/api/v1``. The health endpoint
intentionally lives at ``/api/health`` (unversioned) so load balancers
and uptime monitors have a stable path.
"""

from fastapi import APIRouter

from app.api.v1 import chat, documents

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(documents.router, prefix="/documents", tags=["documents"])
v1_router.include_router(chat.router, prefix="/chat", tags=["chat"])
