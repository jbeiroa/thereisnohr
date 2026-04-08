from pathlib import Path

from src.retrieval.service import RetrievalService
from src.llm.registry import ModelAliasRegistry


def _make_registry(tmp_path: Path) -> ModelAliasRegistry:
    config = tmp_path / "model_aliases.yaml"
    config.write_text(
        "embedding_default:\n  default_model: openai/text-embedding-3-small\n",
        encoding="utf-8",
    )
    return ModelAliasRegistry(config)


def test_top_k_returns_empty_when_k_non_positive() -> None:
    service = RetrievalService()
    assert service.top_k("text", 0) == []


def test_top_k_resolves_model_and_queries(monkeypatch, tmp_path: Path) -> None:
    captured = {}
    service = RetrievalService(registry=_make_registry(tmp_path))

    monkeypatch.setattr(
        service,
        "_embed_job_description",
        lambda *, job_description, embedding_model_alias: [0.1, 0.2],  # noqa: ARG005
    )

    def fake_query_top_candidates(*, model: str, query_vector: list[float], k: int) -> list[int]:
        captured["model"] = model
        captured["query_vector"] = query_vector
        captured["k"] = k
        return [10, 20]

    monkeypatch.setattr(service, "_query_top_candidates", fake_query_top_candidates)

    result = service.top_k("backend engineer", 2, embedding_model_alias="embedding_default")
    assert result == [10, 20]
    assert captured["model"] == "openai/text-embedding-3-small"
    assert captured["query_vector"] == [0.1, 0.2]
    assert captured["k"] == 2


def test_top_k_returns_empty_when_embedding_missing(monkeypatch, tmp_path: Path) -> None:
    service = RetrievalService(registry=_make_registry(tmp_path))
    monkeypatch.setattr(
        service,
        "_embed_job_description",
        lambda *, job_description, embedding_model_alias: [],  # noqa: ARG005
    )
    assert service.top_k("backend engineer", 5, embedding_model_alias="embedding_default") == []
