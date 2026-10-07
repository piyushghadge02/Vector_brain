"""Add sha256 content hash to documents (duplicate-upload detection).

Revision ID: 0002_document_sha256
Revises: 0001_initial_schema
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_document_sha256"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("sha256", sa.Text(), nullable=True))
    op.create_index(
        "uq_documents_sha256", "documents", ["sha256"], unique=True
    )


def downgrade() -> None:
    op.drop_index("uq_documents_sha256", table_name="documents")
    op.drop_column("documents", "sha256")
