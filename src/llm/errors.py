"""Application module `src.llm.errors`."""

from __future__ import annotations


class LLMError(Exception):
    """Base exception for all LLM-layer failures."""


class LLMConfigError(LLMError):
    """Raised when model alias configuration is invalid or missing."""


class LLMProviderError(LLMError):
    """Raised for provider-side failures that are not more specific."""


class LLMTimeoutError(LLMProviderError):
    """Raised when an LLM request times out."""


class LLMRateLimitError(LLMProviderError):
    """Raised when the provider rejects requests due to rate limits."""


class LLMStructuredOutputError(LLMError):
    """Raised when the model response cannot be parsed as valid JSON."""


class LLMSchemaValidationError(LLMError):
    """Raised when parsed JSON fails schema validation."""


class LLMRetryExhaustedError(LLMError):
    """Raised when all retries and fallback routes are exhausted."""
