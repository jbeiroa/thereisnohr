from dataclasses import dataclass


@dataclass
class RankingService:
    def rank(self, candidate_ids: list[int]) -> list[int]:
        return candidate_ids
