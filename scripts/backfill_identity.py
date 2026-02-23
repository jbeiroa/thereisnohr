"""Utility script for `backfill_identity` workflows."""

from __future__ import annotations

import argparse
from collections import defaultdict

from src.ingest.identity import compute_content_hash
from src.storage.db import get_session
from src.storage.models import Candidate, Resume


def run_backfill(*, apply: bool) -> int:
    """Run run backfill.

    Args:
        apply: Input parameter.

    Returns:
        object: Computed result.

    """
    session = get_session()
    try:
        resumes = session.query(Resume).all()
        updated = 0
        for resume in resumes:
            if resume.content_hash:
                continue
            clean_text = (resume.parsed_json or {}).get("clean_text") if resume.parsed_json else None
            source = clean_text or resume.raw_text
            resume.content_hash = compute_content_hash(source)
            updated += 1

        duplicate_map: dict[str, list[int]] = defaultdict(list)
        for candidate_id, external_id in session.query(Candidate.id, Candidate.external_id).all():
            if external_id:
                duplicate_map[external_id].append(candidate_id)

        duplicate_groups = {key: ids for key, ids in duplicate_map.items() if len(ids) > 1}

        print(f"resumes_missing_hash_updated={updated}")
        print(f"duplicate_external_id_groups={len(duplicate_groups)}")
        for external_id, ids in sorted(duplicate_groups.items()):
            print(f"duplicate external_id={external_id} candidate_ids={ids}")

        if apply:
            session.commit()
        else:
            session.rollback()
        return 0
    finally:
        session.close()


def main() -> int:
    """Run main.

    Returns:
        object: Computed result.

    """
    parser = argparse.ArgumentParser(description="Backfill resume content hashes and report duplicate identity keys.")
    parser.add_argument("--apply", action="store_true", help="Persist changes. Default is dry-run.")
    args = parser.parse_args()
    return run_backfill(apply=args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
