"""Application module `src.ranking.service`."""

from dataclasses import dataclass


@dataclass
class RankingService:
    """Represents RankingService."""

    def rank(self, candidate_ids: list[int]) -> list[int]:
        """Run rank.

        Args:
            candidate_ids: Input parameter.

        Returns:
            object: Computed result.

        """
        return candidate_ids
