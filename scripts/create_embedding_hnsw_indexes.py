"""Create model-scoped HNSW indexes for embeddings."""

from __future__ import annotations

import argparse
import hashlib

from sqlalchemy import text

from src.storage.db import get_session


def _index_name(*, model: str, dimensions: int) -> str:
    """Builds a short deterministic index name within Postgres length limits."""
    digest = hashlib.sha1(model.encode("utf-8")).hexdigest()[:8]
    return f"ix_emb_hnsw_{dimensions}_{digest}"


def _escape_literal(value: str) -> str:
    """Escapes SQL string literals for dynamic DDL construction."""
    return value.replace("'", "''")


def run() -> int:
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
            idx = _index_name(model=model_str, dimensions=dim)
            sql = (
                f"CREATE INDEX IF NOT EXISTS {idx} "
                f"ON embeddings USING hnsw ((vector::vector({dim})) vector_cosine_ops) "
                f"WHERE model = '{_escape_literal(model_str)}' "
                f"AND dimensions = {dim}"
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
    parser.parse_args()
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
