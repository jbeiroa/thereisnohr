"""Support multi-dimension embeddings with model-level dimension contracts."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260303_0003"
down_revision: Union[str, Sequence[str], None] = "20260223_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Runs upgrade logic."""
    op.create_table(
        "embedding_models",
        sa.Column("model", sa.String(length=128), primary_key=True),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("dimensions > 0", name="ck_embedding_models_dimensions_positive"),
    )
    op.create_index(
        "ux_embedding_models_model_dimensions",
        "embedding_models",
        ["model", "dimensions"],
        unique=True,
    )

    op.add_column("embeddings", sa.Column("dimensions", sa.Integer(), nullable=True))
    op.execute("UPDATE embeddings SET dimensions = vector_dims(vector) WHERE dimensions IS NULL")

    conn = op.get_bind()
    mixed_rows = conn.execute(
        sa.text(
            """
            SELECT model
            FROM embeddings
            GROUP BY model
            HAVING COUNT(DISTINCT dimensions) > 1
            """
        )
    ).fetchall()
    if mixed_rows:
        models = ", ".join(str(row[0]) for row in mixed_rows)
        raise RuntimeError(
            f"Cannot migrate embeddings: mixed dimensions found for model(s): {models}"
        )

    conn.execute(
        sa.text(
            """
            INSERT INTO embedding_models (model, dimensions, created_at)
            SELECT DISTINCT model, dimensions, NOW()
            FROM embeddings
            WHERE model IS NOT NULL AND dimensions IS NOT NULL
            ON CONFLICT (model) DO NOTHING
            """
        )
    )

    op.execute("ALTER TABLE embeddings ALTER COLUMN vector TYPE vector USING vector::vector")
    op.alter_column("embeddings", "dimensions", nullable=False)
    op.create_check_constraint(
        "ck_embeddings_dimensions_positive",
        "embeddings",
        "dimensions > 0",
    )
    op.create_check_constraint(
        "ck_embeddings_dimensions_match_vector",
        "embeddings",
        "dimensions = vector_dims(vector)",
    )
    op.create_foreign_key(
        "fk_embeddings_model_dimensions",
        "embeddings",
        "embedding_models",
        ["model", "dimensions"],
        ["model", "dimensions"],
    )
    op.create_index(
        "ix_embeddings_model_dimensions_owner",
        "embeddings",
        ["model", "dimensions", "owner_type", "owner_id"],
        unique=False,
    )


def downgrade() -> None:
    """Runs downgrade logic."""
    conn = op.get_bind()
    non_1536 = conn.execute(
        sa.text("SELECT COUNT(*) FROM embeddings WHERE dimensions <> 1536")
    ).scalar_one()
    if non_1536 > 0:
        raise RuntimeError(
            "Cannot downgrade to fixed vector(1536): embeddings with non-1536 dimensions exist."
        )

    op.drop_index("ix_embeddings_model_dimensions_owner", table_name="embeddings")
    op.drop_constraint("fk_embeddings_model_dimensions", "embeddings", type_="foreignkey")
    op.drop_constraint("ck_embeddings_dimensions_match_vector", "embeddings", type_="check")
    op.drop_constraint("ck_embeddings_dimensions_positive", "embeddings", type_="check")
    op.execute(
        "ALTER TABLE embeddings ALTER COLUMN vector TYPE vector(1536) USING vector::vector(1536)"
    )
    op.drop_column("embeddings", "dimensions")

    op.drop_index("ux_embedding_models_model_dimensions", table_name="embedding_models")
    op.drop_table("embedding_models")
