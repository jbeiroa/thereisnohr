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
