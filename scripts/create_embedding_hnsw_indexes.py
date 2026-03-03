"""Create model-scoped HNSW indexes for embeddings."""

from __future__ import annotations

import argparse
import hashlib

from sqlalchemy import text

from src.storage.db import get_session


DEFAULT_OWNER_TYPES = ("resume_section", "job_posting")


def _index_name(*, model: str, dimensions: int, owner_type: str) -> str:
    """Builds a short deterministic index name within Postgres length limits."""
    digest = hashlib.sha1(model.encode("utf-8")).hexdigest()[:8]
    return f"ix_emb_hnsw_{owner_type}_{dimensions}_{digest}"


def _escape_literal(value: str) -> str:
    """Escapes SQL string literals for dynamic DDL construction."""
    return value.replace("'", "''")


def run(*, owner_types: tuple[str, ...]) -> int:
    """Creates missing HNSW indexes for each model+dimension pair."""
    session = get_session()
    created = 0
    try:
        rows = session.execute(
            text("SELECT model, dimensions FROM embedding_models ORDER BY model")
        ).fetchall()
        for model, dimensions in rows:
            model_str = str(model)
            dim = int(dimensions)
            for owner_type in owner_types:
                idx = _index_name(model=model_str, dimensions=dim, owner_type=owner_type)
                sql = (
                    f"CREATE INDEX IF NOT EXISTS {idx} "
                    f"ON embeddings USING hnsw ((vector::vector({dim})) vector_cosine_ops) "
                    f"WHERE model = '{_escape_literal(model_str)}' "
                    f"AND dimensions = {dim} "
                    f"AND owner_type = '{_escape_literal(owner_type)}'"
                )
                session.execute(text(sql))
                created += 1
        session.commit()
        print(f"indexes_attempted={created}")
        return 0
    finally:
        session.close()


def main() -> int:
    """Parses CLI options and executes the index creation script."""
    parser = argparse.ArgumentParser(description="Create model-scoped HNSW indexes for embeddings.")
    parser.add_argument(
        "--owner-type",
        action="append",
        dest="owner_types",
        help="Owner type to index (repeatable). Defaults to resume_section and job_posting.",
    )
    args = parser.parse_args()
    owner_types = tuple(args.owner_types) if args.owner_types else DEFAULT_OWNER_TYPES
    return run(owner_types=owner_types)


if __name__ == "__main__":
    raise SystemExit(main())
