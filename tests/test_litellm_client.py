import pytest
from pathlib import Path

import litellm
from pydantic import BaseModel

from src.llm.client import LiteLLMClient
from src.llm.errors import LLMRetryExhaustedError
from src.llm.registry import ModelAliasRegistry


class ResumeSummary(BaseModel):
    name: str
    score: float


def _make_registry(tmp_path: Path) -> ModelAliasRegistry:
    config = tmp_path / "model_aliases.yaml"
    config.write_text(
        "summarizer_default:\n"
        "  model: openai/gpt-4o-mini\n"
        "  params:\n"
        "    temperature: 0.1\n"
        "    max_tokens: 200\n"
        "embedding_default:\n"
        "  model: text-embedding-3-small\n",
        encoding="utf-8",
    )
    return ModelAliasRegistry(config)


def test_generate_structured_retries_and_validates(monkeypatch, tmp_path: Path) -> None:
    calls = {"count": 0}
    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        calls["count"] += 1
        if calls["count"] == 1:
            return {"choices": [{"message": {"content": "not-json"}}]}
        return {"choices": [{"message": {"content": '{"name": "Ada", "score": 0.91}'}}]}

    monkeypatch.setattr("litellm.completion", fake_completion)

    client = LiteLLMClient(_make_registry(tmp_path), timeout_seconds=5, max_retries=1)
    result = client.generate_structured(
        prompt="Summarize candidate",
        schema=ResumeSummary,
        model_alias="summarizer_default",
        temperature=0.7,
    )

    assert result.name == "Ada"
    assert result.score == 0.91
    assert calls["count"] == 2
    assert captured["temperature"] == 0.7
    assert captured["max_tokens"] == 200


def test_embed_uses_alias(monkeypatch, tmp_path: Path) -> None:
    captured = {}

    def fake_embedding(**kwargs):
        captured.update(kwargs)
        return {"data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]}

    monkeypatch.setattr("litellm.embedding", fake_embedding)

    client = LiteLLMClient(_make_registry(tmp_path), timeout_seconds=5, max_retries=0)
    vectors = client.embed(["a", "b"], "embedding_default")

    assert captured["model"] == "text-embedding-3-small"
    assert vectors == [[0.1, 0.2], [0.3, 0.4]]


def test_generate_structured_maps_provider_errors(monkeypatch, tmp_path: Path) -> None:
    def fake_completion(**_kwargs):
        raise litellm.RateLimitError(
            message="rate limited",
            llm_provider="openai",
            model="gpt-4o-mini",
        )

    monkeypatch.setattr("litellm.completion", fake_completion)

    client = LiteLLMClient(_make_registry(tmp_path), timeout_seconds=5, max_retries=0)
    with pytest.raises(litellm.RateLimitError, match="rate limited"):
        client.generate_structured(
            prompt="Summarize candidate",
            schema=ResumeSummary,
            model_alias="summarizer_default",
        )


def test_generate_structured_raises_retry_exhausted_for_parse_errors(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_completion(**_kwargs):
        return {"choices": [{"message": {"content": "not-json"}}]}

    monkeypatch.setattr("litellm.completion", fake_completion)

    client = LiteLLMClient(_make_registry(tmp_path), timeout_seconds=5, max_retries=1)
    with pytest.raises(LLMRetryExhaustedError, match="Structured generation failed after 2 attempts"):
        client.generate_structured(
            prompt="Summarize candidate",
            schema=ResumeSummary,
            model_alias="summarizer_default",
        )
