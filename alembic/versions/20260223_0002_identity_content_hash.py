"""add content hash and candidate external-id uniqueness

Revision ID: 20260223_0002
Revises: 20260216_0001
Create Date: 2026-02-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260223_0002"
down_revision: Union[str, Sequence[str], None] = "20260216_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("resumes", sa.Column("content_hash", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_resumes_content_hash"), "resumes", ["content_hash"], unique=False)

    conn = op.get_bind()
    duplicate_count = conn.execute(
        sa.text(
            """
            SELECT COUNT(*) FROM (
                SELECT external_id
                FROM candidates
                WHERE external_id IS NOT NULL
                GROUP BY external_id
                HAVING COUNT(*) > 1
            ) dup
            """
        )
    ).scalar_one()
    if duplicate_count > 0:
        raise RuntimeError(
            "Cannot create unique index on candidates.external_id: duplicates exist. "
            "Run dedup/backfill before applying this migration."
        )

    op.create_index(
        "ux_candidates_external_id_not_null",
        "candidates",
        ["external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ux_candidates_external_id_not_null", table_name="candidates")
    op.drop_index(op.f("ix_resumes_content_hash"), table_name="resumes")
    op.drop_column("resumes", "content_hash")
