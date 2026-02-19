from dataclasses import dataclass


@dataclass
class RetrievalService:
    def top_k(self, job_description: str, k: int) -> list[int]:
        _ = job_description
        _ = k
        return []
