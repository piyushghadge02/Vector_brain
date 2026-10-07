"""Chat / RAG endpoint.

``POST /api/v1/chat/query`` answers a question over the ingested corpus:

- ``document_ids`` omitted → searches **all** processed documents
  ("query all documents"); provided → scopes and validates the ids.
- Returns a grounded answer plus the cited sources. When nothing relevant
  is found, the answer says so instead of inventing information.
- Rate-limited: 20 requests/minute per IP (the endpoint costs money per call).
"""

from fastapi import APIRouter, Depends, Request

from app.api.deps import get_rag_service
from app.core.rate_limit import limiter
from app.schemas.chat import QueryRequest, QueryResponse, SourceOut
from app.services.rag import RAGService

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
@limiter.limit("20/minute")
async def query(
    request: Request,  # required by slowapi for rate limiting
    payload: QueryRequest,
    service: RAGService = Depends(get_rag_service),
):
    result = await service.ask(
        payload.question,
        document_ids=payload.document_ids,
        top_k=payload.top_k,
    )
    return QueryResponse(
        answer=result.answer,
        sources=[SourceOut.model_validate(s) for s in result.sources],
        model=result.model,
        latency_ms=result.latency_ms,
    )
