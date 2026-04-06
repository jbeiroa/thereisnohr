"""Backfill missing non-skill resume-section embeddings."""

from __future__ import annotations

import argparse
import hashlib

from sqlalchemy import delete, select

from src.core.config import get_settings
from src.llm.factory import build_default_llm_client
from src.llm.registry import ModelAliasRegistry
from src.storage.db import get_session
from src.storage.models import Embedding, ResumeSection
from src.storage.repositories import EmbeddingRepository


def run(
    *,
    embedding_alias: str | None,
    limit: int | None,
    resume_id: int | None,
    replace_existing: bool,
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
        target_model = ModelAliasRegistry(settings.model_aliases_path).get(alias).default_model
        client = build_default_llm_client()
        repo = EmbeddingRepository(session)

        if replace_existing:
            if resume_id is None:
                session.execute(
                    delete(Embedding).where(
                        Embedding.model == target_model,
                    )
                )
            else:
                section_ids = select(ResumeSection.id).where(ResumeSection.resume_id == resume_id)
                session.execute(
                    delete(Embedding).where(
                        Embedding.model == target_model,
                        Embedding.owner_id.in_(section_ids),
                    )
                )
            session.flush()

        existing = set(
            session.execute(
                select(Embedding.owner_id, Embedding.model)
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
            if not content:
                skipped += 1
                continue
            try:
                vectors, meta = client.embed_with_meta(texts=[content], embedding_model_alias=alias)
                if len(vectors) != 1:
                    raise ValueError(f"Expected exactly one vector, got {len(vectors)}")
                model = meta.selected_model or alias
                if (section.id, model) in existing:
                    skipped += 1
                    continue
                repo.create(
                    owner_id=int(section.id),
                    model=model,
                    vector=[float(v) for v in vectors[0]],
                    text_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                )
                inserted += 1
                existing.add((section.id, model))
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
        print(f"target_model={target_model}")
        print(f"replace_existing={replace_existing}")
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
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="Delete existing embeddings for the selected model before backfilling.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Run without committing changes.")
    args = parser.parse_args()
    return run(
        embedding_alias=args.embedding_alias,
        limit=args.limit,
        resume_id=args.resume_id,
        replace_existing=args.replace_existing,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
