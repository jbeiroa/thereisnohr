"""Tests for LLM error taxonomy scaffolding."""

from src.llm.errors import (
    LLMConfigError,
    LLMError,
    LLMProviderError,
    LLMRateLimitError,
    LLMRetryExhaustedError,
    LLMSchemaValidationError,
    LLMStructuredOutputError,
    LLMTimeoutError,
    coerce_provider_exception,
)


def test_error_taxonomy_inheritance() -> None:
    """Ensure all custom exceptions inherit from the expected base classes."""
    assert issubclass(LLMConfigError, LLMError)
    assert issubclass(LLMProviderError, LLMError)
    assert issubclass(LLMTimeoutError, LLMProviderError)
    assert issubclass(LLMRateLimitError, LLMProviderError)
    assert issubclass(LLMStructuredOutputError, LLMError)
    assert issubclass(LLMSchemaValidationError, LLMError)
    assert issubclass(LLMRetryExhaustedError, LLMError)


def test_coerce_provider_exception_rate_limit() -> None:
    """Rate limit should map to LLMRateLimitError."""
    import litellm

    error = litellm.RateLimitError(
        message="too many requests",
        llm_provider="openai",
        model="gpt-4o-mini",
    )
    mapped = coerce_provider_exception(error)
    assert isinstance(mapped, LLMRateLimitError)
    assert "too many requests" in str(mapped)


def test_coerce_provider_exception_timeout() -> None:
    """Timeout should map to LLMTimeoutError."""
    import litellm

    error = litellm.Timeout(
        message="timed out",
        llm_provider="openai",
        model="gpt-4o-mini",
    )
    mapped = coerce_provider_exception(error)
    assert isinstance(mapped, LLMTimeoutError)
    assert "timed out" in str(mapped)


def test_coerce_provider_exception_other_litellm_error() -> None:
    """Other LiteLLM errors should map to generic LLMProviderError."""
    import litellm

    error = litellm.BadRequestError(
        message="bad request",
        llm_provider="openai",
        model="gpt-4o-mini",
    )
    mapped = coerce_provider_exception(error)
    assert isinstance(mapped, LLMProviderError)
    assert "bad request" in str(mapped)


def test_coerce_provider_exception_non_litellm_passthrough() -> None:
    """Non-provider exceptions should be returned unchanged."""
    error = RuntimeError("boom")
    assert coerce_provider_exception(error) is error
