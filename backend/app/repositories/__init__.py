"""Repository layer — the ONLY place that talks to the database.

Separation of concerns:
- ``app/db/models.py``      → what the tables look like (ORM mappings)
- ``app/repositories/``     → how data is read/written (this package)
- ``app/services/``         → what it means (business logic, Phase 3+)
- ``app/api/``              → how it is exposed over HTTP

Repositories flush but never commit: the caller (service layer, or the
request lifecycle in Phase 3) owns the transaction boundary.
"""

from app.repositories.chunks import (
    ChunkCreate,
    ChunkRepository,
    ChunkSearchResult,
)
from app.repositories.documents import DocumentRepository

__all__ = [
    "ChunkCreate",
    "ChunkRepository",
    "ChunkSearchResult",
    "DocumentRepository",
]
