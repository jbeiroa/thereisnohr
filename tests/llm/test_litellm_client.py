import pytest
from pathlib import Path

import litellm
from pydantic import BaseModel

from src.llm.client import LiteLLMClient
from src.llm.errors import LLMRateLimitError, LLMStructuredOutputError
from src.llm.registry import ModelAliasRegistry


class ResumeSummary(BaseModel):
    name: str
    score: float


def _make_registry(tmp_path: Path) -> ModelAliasRegistry:
    config = tmp_path / "model_aliases.yaml"
    config.write_text(
        "summarizer_default:\n"
        "  default_model: openai/gpt-4o-mini\n"
        "  default_litellm_params:\n"
        "    temperature: 0.1\n"
        "    max_tokens: 200\n"
        "  fallbacks:\n"
        "    - model: openai/gpt-4.1-mini\n"
        "      litellm_params:\n"
        "        temperature: 0.1\n"
        "  fallback_policy:\n"
        "    num_retries: 1\n"
        "    max_fallbacks: 1\n"
        "embedding_default:\n"
        "  default_model: text-embedding-3-small\n",
        encoding="utf-8",
    )
    return ModelAliasRegistry(config)


def test_generate_structured_retries_and_validates(monkeypatch, tmp_path: Path) -> None:
    calls = {"count": 0}
    captured = {}

    def fake_completion(self, **kwargs):  # noqa: ANN001
        _ = self
        captured.update(kwargs)
        calls["count"] += 1
        return {
            "model": "openai/gpt-4o-mini",
            "usage": {"prompt_tokens": 10, "completion_tokens": 7, "total_tokens": 17},
            "choices": [{"message": {"content": '{"name": "Ada", "score": 0.91}'}}],
        }

    monkeypatch.setattr(litellm.Router, "completion", fake_completion)

    client = LiteLLMClient(_make_registry(tmp_path), timeout_seconds=5, max_retries=1)
    result = client.generate_structured(
        prompt="Summarize candidate",
        schema=ResumeSummary,
        model_alias="summarizer_default",
        temperature=0.7,
    )

    assert result.name == "Ada"
    assert result.score == 0.91
    assert calls["count"] == 1
    assert captured["temperature"] == 0.7


def test_generate_structured_with_meta_returns_usage(monkeypatch, tmp_path: Path) -> None:
    def fake_completion(self, **_kwargs):  # noqa: ANN001
        _ = self
        return {
            "model": "openai/gpt-4o-mini",
            "usage": {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6},
            "choices": [{"message": {"content": '{"name": "Ada", "score": 0.91}'}}],
        }

    monkeypatch.setattr(litellm.Router, "completion", fake_completion)
    monkeypatch.setattr(litellm, "completion_cost", lambda **_kwargs: 0.000123)

    client = LiteLLMClient(_make_registry(tmp_path), timeout_seconds=5, max_retries=1)
    result, meta = client.generate_structured_with_meta(
        prompt="Summarize candidate",
        schema=ResumeSummary,
        model_alias="summarizer_default",
    )

    assert result.name == "Ada"
    assert meta.model_alias == "summarizer_default"
    assert meta.selected_model == "openai/gpt-4o-mini"
    assert meta.usage.total_tokens == 6
    assert meta.usage.estimated_cost_usd == pytest.approx(0.000123)


def test_generate_structured_with_meta_handles_cost_estimation_failures(
    monkeypatch, tmp_path: Path
) -> None:
    def fake_completion(self, **_kwargs):  # noqa: ANN001
        _ = self
        return {
            "model": "openai/gpt-4o-mini",
            "usage": {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6},
            "choices": [{"message": {"content": '{"name": "Ada", "score": 0.91}'}}],
        }

    def fake_cost(**_kwargs):  # noqa: ANN001
        raise RuntimeError("no pricing")

    monkeypatch.setattr(litellm.Router, "completion", fake_completion)
    monkeypatch.setattr(litellm, "completion_cost", fake_cost)

    client = LiteLLMClient(_make_registry(tmp_path), timeout_seconds=5, max_retries=1)
    _, meta = client.generate_structured_with_meta(
        prompt="Summarize candidate",
        schema=ResumeSummary,
        model_alias="summarizer_default",
    )

    assert meta.usage.estimated_cost_usd is None


def test_embed_uses_alias(monkeypatch, tmp_path: Path) -> None:
    captured = {}

    def fake_embedding(self, **kwargs):  # noqa: ANN001
        _ = self
        captured.update(kwargs)
        return {"data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]}

    monkeypatch.setattr(litellm.Router, "embedding", fake_embedding)

    client = LiteLLMClient(_make_registry(tmp_path), timeout_seconds=5, max_retries=0)
    vectors = client.embed(["a", "b"], "embedding_default")

    assert captured["model"] == "embedding_default"
    assert vectors == [[0.1, 0.2], [0.3, 0.4]]


def test_generate_structured_maps_provider_errors(monkeypatch, tmp_path: Path) -> None:
    def fake_completion(self, **_kwargs):  # noqa: ANN001
        _ = self
        raise litellm.RateLimitError(
            message="rate limited",
            llm_provider="openai",
            model="gpt-4o-mini",
        )

    monkeypatch.setattr(litellm.Router, "completion", fake_completion)

    client = LiteLLMClient(_make_registry(tmp_path), timeout_seconds=5, max_retries=0)
    with pytest.raises(LLMRateLimitError, match="rate limited"):
        client.generate_structured(
            prompt="Summarize candidate",
            schema=ResumeSummary,
            model_alias="summarizer_default",
        )


def test_generate_structured_raises_structured_output_for_parse_errors(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_completion(self, **_kwargs):  # noqa: ANN001
        _ = self
        return {"choices": [{"message": {"content": "not-json"}}]}

    monkeypatch.setattr(litellm.Router, "completion", fake_completion)

    client = LiteLLMClient(_make_registry(tmp_path), timeout_seconds=5, max_retries=1)
    with pytest.raises(LLMStructuredOutputError):
        client.generate_structured(
            prompt="Summarize candidate",
            schema=ResumeSummary,
            model_alias="summarizer_default",
        )
