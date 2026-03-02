import litellm
import pytest

from src.ingest.model_fallback import LLMFallbackResolver
from src.llm.errors import LLMProviderError, LLMRateLimitError, LLMTimeoutError


class _FailingLLM:
    def __init__(self, error: Exception):
        self._error = error

    def generate_structured(self, *args, **kwargs):  # noqa: ANN002, ANN003
        _ = args
        _ = kwargs
        raise self._error


def test_resolve_name_coerces_rate_limit_to_app_error() -> None:
    resolver = LLMFallbackResolver(
        _FailingLLM(
            litellm.RateLimitError(
                message="rate limited",
                llm_provider="openai",
                model="gpt-4o-mini",
            )
        )
    )

    with pytest.raises(LLMRateLimitError, match="rate limited"):
        resolver.resolve_name(
            candidate_lines=["John Doe"],
            emails=[],
            phones=[],
            language="en",
        )


def test_classify_section_coerces_timeout_to_app_error() -> None:
    resolver = LLMFallbackResolver(
        _FailingLLM(
            litellm.Timeout(
                message="timed out",
                llm_provider="openai",
                model="gpt-4o-mini",
            )
        )
    )

    with pytest.raises(LLMTimeoutError, match="timed out"):
        resolver.classify_section(
            raw_heading="Experience",
            content_excerpt="Worked as engineer",
            language="en",
        )


def test_resolve_name_coerces_other_litellm_to_generic_provider_error() -> None:
    resolver = LLMFallbackResolver(
        _FailingLLM(
            litellm.BadRequestError(
                message="invalid request",
                llm_provider="openai",
                model="gpt-4o-mini",
            )
        )
    )

    with pytest.raises(LLMProviderError, match="invalid request"):
        resolver.resolve_name(
            candidate_lines=["John Doe"],
            emails=[],
            phones=[],
            language="en",
        )


def test_resolve_name_passthrough_for_non_litellm_error() -> None:
    resolver = LLMFallbackResolver(_FailingLLM(RuntimeError("boom")))

    with pytest.raises(RuntimeError, match="boom"):
        resolver.resolve_name(
            candidate_lines=["John Doe"],
            emails=[],
            phones=[],
            language="en",
        )
