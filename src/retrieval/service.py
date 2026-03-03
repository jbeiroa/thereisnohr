"""Retrieval service boundary for selecting top candidate ids."""

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.llm.client import LLMClient
from src.llm.factory import build_default_llm_client
from src.llm.registry import ModelAliasRegistry
from src.storage.db import get_session


@dataclass
class RetrievalService:
    """Service object that orchestrates retrieval workflow operations."""

    session: Session | None = None
    llm_client: LLMClient | None = None
    registry: ModelAliasRegistry | None = None

    def top_k(self, job_description: str, k: int, embedding_model_alias: str | None = None) -> list[int]:
        """Runs top k logic.

        Args:
            job_description (str): Job description text used for retrieval/extraction.
            k (int): Maximum number of rows/items to return.
            embedding_model_alias (str | None): Optional embedding alias override.

        Returns:
            list[int]: Ordered list produced by this operation.
        """
        if k <= 0:
            return []

        alias = embedding_model_alias or get_settings().embedding_model_alias
        model = self._resolve_model_for_alias(alias)
        query_vector = self._embed_job_description(job_description=job_description, embedding_model_alias=alias)
        if not query_vector:
            return []
        return self._query_top_candidates(model=model, query_vector=query_vector, k=k)

    def _resolve_model_for_alias(self, alias_name: str) -> str:
        """Resolves configured default provider-model for an embedding alias."""
        registry = self.registry
        if registry is None:
            registry = ModelAliasRegistry(get_settings().model_aliases_path)
        alias = registry.get(alias_name)
        return alias.default_model

    def _resolve_llm_client(self) -> LLMClient:
        """Returns an LLM client instance."""
        if self.llm_client is not None:
            return self.llm_client
        return build_default_llm_client()

    def _query_top_candidates(self, *, model: str, query_vector: list[float], k: int) -> list[int]:
        """Queries top candidate ids for one model+dimension embedding space."""
        session = self.session or get_session()
        close_session = self.session is None
        dimension = len(query_vector)
        sql = text(
            f"""
            SELECT r.candidate_id
            FROM embeddings e
            JOIN resume_sections rs ON rs.id = e.owner_id
            JOIN resumes r ON r.id = rs.resume_id
            WHERE e.owner_type = 'resume_section'
              AND e.model = :model
              AND e.dimensions = :dimensions
            GROUP BY r.candidate_id
            ORDER BY MAX(1 - ((e.vector::vector({dimension})) <=> (:query_vector::vector({dimension})))) DESC
            LIMIT :k
            """
        )
        try:
            rows = session.execute(
                sql,
                {
                    "model": model,
                    "dimensions": dimension,
                    "query_vector": query_vector,
                    "k": k,
                },
            ).fetchall()
            return [int(row[0]) for row in rows]
        finally:
            if close_session:
                session.close()

    def _embed_job_description(self, *, job_description: str, embedding_model_alias: str) -> list[float]:
        """Embeds the input job text using the configured embedding alias."""
        vectors = self._resolve_llm_client().embed(
            texts=[job_description],
            embedding_model_alias=embedding_model_alias,
        )
        if not vectors:
            return []
        first = vectors[0]
        return [float(value) for value in first]
