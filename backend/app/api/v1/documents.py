"""Document ingestion endpoints.

- ``POST /upload``          — accept 1..N PDFs, validate, enqueue processing (202)
- ``GET /``                 — paginated document list with metadata + status
- ``GET /{document_id}``    — one document's metadata + ingestion status
- ``POST /{document_id}/retry`` — re-enqueue a failed document (202)
- ``DELETE /{document_id}`` — delete document, chunks, and file (204)
"""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_ingestion_service, get_session
from app.core.errors import NotFoundError
from app.repositories import DocumentRepository
from app.schemas.documents import DocumentListOut, DocumentOut, UploadResponse
from app.services.ingestion import IngestionService

router = APIRouter()


@router.post(
    "/upload", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED
)
async def upload_documents(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(description="One or more PDF files"),
    session: AsyncSession = Depends(get_session),
    service: IngestionService = Depends(get_ingestion_service),
):
    """Accept PDFs and start background ingestion. Returns immediately (202)."""
    documents = await service.submit_uploads(session, files)
    await session.commit()
    service.enqueue(background_tasks, [d.id for d in documents])
    return UploadResponse(documents=[DocumentOut.model_validate(d) for d in documents])


@router.get("", response_model=DocumentListOut)
async def list_documents(
    status: str | None = Query(default=None, description="filter by ingestion status"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    repo = DocumentRepository(session)
    items, total = await repo.list(status=status, page=page, size=size)
    return DocumentListOut(
        items=[DocumentOut.model_validate(d) for d in items],
        total=total,
        page=page,
        size=size,
    )


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    doc = await DocumentRepository(session).get(document_id)
    if doc is None:
        raise NotFoundError(f"Document {document_id} not found.")
    return DocumentOut.model_validate(doc)


@router.post(
    "/{document_id}/retry",
    response_model=DocumentOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_document(
    document_id: UUID,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    service: IngestionService = Depends(get_ingestion_service),
):
    """Re-enqueue a failed document for processing."""
    doc = await service.retry_failed(session, document_id)
    await session.commit()
    # Refresh: server-side onupdate columns (updated_at) are stale after flush.
    await session.refresh(doc)
    service.enqueue(background_tasks, [doc.id])
    return DocumentOut.model_validate(doc)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    session: AsyncSession = Depends(get_session),
    service: IngestionService = Depends(get_ingestion_service),
):
    deleted = await service.delete_document(session, document_id)
    await session.commit()
    if not deleted:
        raise NotFoundError(f"Document {document_id} not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
