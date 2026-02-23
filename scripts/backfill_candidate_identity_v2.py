from __future__ import annotations

import argparse
from collections import defaultdict

from src.ingest.identity import estimate_name_quality, normalize_email, normalize_phone
from src.storage.db import get_session
from src.storage.models import Candidate, Embedding, Match, Resume


def _link_list(value: list[str] | dict | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    if isinstance(value, dict):
        urls = value.get("urls")
        if isinstance(urls, list):
            return [str(v) for v in urls if str(v).strip()]
    return []


def _group_key(candidate: Candidate) -> str | None:
    email = normalize_email(candidate.email)
    if email:
        return f"email:{email}"
    phone = normalize_phone(candidate.phone)
    if phone:
        return f"phone:{phone}"
    return None


def _candidate_rank(candidate: Candidate, resume_counts: dict[int, int]) -> tuple[float, int, int]:
    quality = estimate_name_quality(candidate.name)
    resumes = resume_counts.get(candidate.id, 0)
    return quality, resumes, -candidate.id


def run_backfill(*, apply: bool) -> int:
    session = get_session()
    try:
        candidates = session.query(Candidate).all()
        resume_counts: dict[int, int] = defaultdict(int)
        for candidate_id, in session.query(Resume.candidate_id).all():
            resume_counts[int(candidate_id)] += 1
        grouped: dict[str, list[Candidate]] = defaultdict(list)
        for candidate in candidates:
            key = _group_key(candidate)
            if key:
                grouped[key].append(candidate)

        merge_groups = {key: rows for key, rows in grouped.items() if len(rows) > 1}
        merged_candidates = 0
        moved_resumes = 0
        moved_matches = 0
        moved_candidate_embeddings = 0

        for key, rows in sorted(merge_groups.items()):
            canonical = sorted(rows, key=lambda row: _candidate_rank(row, resume_counts), reverse=True)[0]
            duplicates = [row for row in rows if row.id != canonical.id]
            all_links = set(_link_list(canonical.links))

            best_name = canonical.name
            best_quality = estimate_name_quality(best_name)
            for dup in duplicates:
                all_links.update(_link_list(dup.links))
                quality = estimate_name_quality(dup.name)
                if quality > best_quality:
                    best_name = dup.name
                    best_quality = quality
                if not canonical.email and dup.email:
                    canonical.email = dup.email
                if not canonical.phone and dup.phone:
                    canonical.phone = dup.phone

            canonical.name = best_name
            canonical.links = sorted(all_links) if all_links else None

            for dup in duplicates:
                moved_resumes += (
                    session.query(Resume)
                    .filter(Resume.candidate_id == dup.id)
                    .update({"candidate_id": canonical.id}, synchronize_session=False)
                )
                moved_matches += (
                    session.query(Match)
                    .filter(Match.candidate_id == dup.id)
                    .update({"candidate_id": canonical.id}, synchronize_session=False)
                )
                moved_candidate_embeddings += (
                    session.query(Embedding)
                    .filter(Embedding.owner_type == "candidate", Embedding.owner_id == dup.id)
                    .update({"owner_id": canonical.id}, synchronize_session=False)
                )
                session.delete(dup)
                merged_candidates += 1

            print(
                f"group={key} canonical={canonical.id} merged={len(duplicates)} "
                f"best_name={canonical.name!r} links={len(canonical.links or [])}"
            )

        print(f"merge_groups={len(merge_groups)}")
        print(f"merged_candidates={merged_candidates}")
        print(f"moved_resumes={moved_resumes}")
        print(f"moved_matches={moved_matches}")
        print(f"moved_candidate_embeddings={moved_candidate_embeddings}")

        if apply:
            session.commit()
        else:
            session.rollback()
        return 0
    finally:
        session.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge duplicate candidates using email/phone primary identity keys.")
    parser.add_argument("--apply", action="store_true", help="Persist changes. Default is dry-run.")
    args = parser.parse_args()
    return run_backfill(apply=args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
