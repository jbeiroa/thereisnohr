"""Backfill missing non-skill resume-section embeddings."""

from __future__ import annotations

import argparse
import hashlib

from sqlalchemy import select

from src.core.config import get_settings
from src.llm.factory import build_default_llm_client
from src.storage.db import get_session
from src.storage.models import Embedding, ResumeSection
from src.storage.repositories import EmbeddingRepository


def run(
    *,
    embedding_alias: str | None,
    limit: int | None,
    resume_id: int | None,
    dry_run: bool,
) -> int:
    """Runs section-embedding backfill with optional scoping and dry-run mode."""
    session = get_session()
    inserted = 0
    skipped = 0
    failed = 0
    try:
        settings = get_settings()
        alias = embedding_alias or settings.embedding_model_alias
        client = build_default_llm_client()
        repo = EmbeddingRepository(session)

        existing = set(
            session.scalars(
                select(Embedding.owner_id).where(Embedding.owner_type == "resume_section")
            ).all()
        )

        stmt = select(ResumeSection).where(ResumeSection.section_type != "skills")
        if resume_id is not None:
            stmt = stmt.where(ResumeSection.resume_id == resume_id)
        stmt = stmt.order_by(ResumeSection.id)
        if limit is not None and limit > 0:
            stmt = stmt.limit(limit)

        sections = session.scalars(stmt).all()
        for section in sections:
            content = (section.content or "").strip()
            if not content or section.id in existing:
                skipped += 1
                continue
            try:
                vectors, meta = client.embed_with_meta(texts=[content], embedding_model_alias=alias)
                if len(vectors) != 1:
                    raise ValueError(f"Expected exactly one vector, got {len(vectors)}")
                model = meta.selected_model or alias
                repo.create(
                    owner_type="resume_section",
                    owner_id=int(section.id),
                    model=model,
                    vector=[float(v) for v in vectors[0]],
                    text_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                )
                inserted += 1
            except Exception as exc:
                failed += 1
                print(f"section_id={section.id} status=error error_type={type(exc).__name__} error={exc}")

        if dry_run:
            session.rollback()
        else:
            session.commit()

        print(f"inserted={inserted}")
        print(f"skipped={skipped}")
        print(f"failed={failed}")
        print(f"dry_run={dry_run}")
        return 0 if failed == 0 else 1
    finally:
        session.close()


def main() -> int:
    """Parses CLI arguments and runs the backfill command."""
    parser = argparse.ArgumentParser(description="Backfill non-skill resume section embeddings.")
    parser.add_argument("--embedding-alias", default=None, help="Embedding alias override.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of sections to process.")
    parser.add_argument("--resume-id", type=int, default=None, help="Restrict processing to one resume.")
    parser.add_argument("--dry-run", action="store_true", help="Run without committing changes.")
    args = parser.parse_args()
    return run(
        embedding_alias=args.embedding_alias,
        limit=args.limit,
        resume_id=args.resume_id,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
