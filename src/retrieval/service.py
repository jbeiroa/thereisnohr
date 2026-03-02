"""Retrieval service boundary for selecting top candidate ids."""

from dataclasses import dataclass


@dataclass
class RetrievalService:
    """Service object that orchestrates retrieval workflow operations."""

    def top_k(self, job_description: str, k: int) -> list[int]:
        """Runs top k logic.

        Args:
            job_description (str): Job description text used for retrieval/extraction.
            k (int): Maximum number of rows/items to return.

        Returns:
            list[int]: Ordered list produced by this operation.
        """
        _ = job_description
        _ = k
        return []
