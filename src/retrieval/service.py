"""Application module `src.retrieval.service`."""

from dataclasses import dataclass


@dataclass
class RetrievalService:
    """Represents RetrievalService."""

    def top_k(self, job_description: str, k: int) -> list[int]:
        """Run top k.

        Args:
            job_description: Input parameter.
            k: Input parameter.

        Returns:
            object: Computed result.

        """
        _ = job_description
        _ = k
        return []
