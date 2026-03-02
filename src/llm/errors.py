"""Application-level error taxonomy for the LLM layer.

This module normalizes provider exceptions into a small stable error contract
that service-layer code can rely on without depending on provider-specific
classes.
"""

from functools import lru_cache


class LLMError(Exception):
    """Base exception for all LLM-layer failures."""

    def __init__(self, message: str | None = None):
        self.message = message or self.__doc__
        super().__init__(self.message.strip())


class LLMConfigError(LLMError):
    """Model configuration is invalid or missing."""


class LLMProviderError(LLMError):
    """Raised for provider-side failures that are not more specific."""


class LLMTimeoutError(LLMProviderError):
    """Raised when an LLM request times out."""


class LLMRateLimitError(LLMProviderError):
    """Raised when the provider rejects requests due to rate limits."""


class LLMStructuredOutputError(LLMError):
    """The model's response could not be parsed to JSON."""


class LLMSchemaValidationError(LLMError):
    """Parsed JSON schema failed validation."""


class LLMRetryExhaustedError(LLMError):
    """All retries and fallbacks were exhausted."""


@lru_cache(maxsize=1)
def _litellm_exception_types() -> tuple[type[Exception], ...]:
    """Returns LiteLLM exception base types exposed by the SDK."""
    try:
        import litellm
    except ImportError:
        return ()

    known = getattr(litellm, "LITELLM_EXCEPTION_TYPES", ())
    return tuple(exc for exc in known if isinstance(exc, type) and issubclass(exc, Exception))


def coerce_provider_exception(error: BaseException) -> BaseException:
    """Normalizes provider exceptions into app-level error types.

    Args:
        error: Exception instance raised by provider/runtime code.

    Returns:
        BaseException: Mapped application exception when recognized, otherwise
            the original exception.
    """
    if not isinstance(error, Exception):
        return error

    try:
        import litellm
    except ImportError:
        return error

    timeout_type = getattr(litellm, "Timeout", None)
    rate_limit_type = getattr(litellm, "RateLimitError", None)

    if isinstance(timeout_type, type) and isinstance(error, timeout_type):
        return LLMTimeoutError(str(error))
    if isinstance(rate_limit_type, type) and isinstance(error, rate_limit_type):
        return LLMRateLimitError(str(error))
    if _litellm_exception_types() and isinstance(error, _litellm_exception_types()):
        return LLMProviderError(str(error))
    return error


def error_type_for_exception(error: BaseException) -> str:
    """Maps exceptions to normalized metadata error labels.

    Args:
        error: Exception to classify.

    Returns:
        str: Error-category label suitable for telemetry metadata.
    """
    normalized = coerce_provider_exception(error)
    if isinstance(normalized, LLMTimeoutError):
        return "timeout"
    if isinstance(normalized, LLMRateLimitError):
        return "rate_limit"
    if isinstance(normalized, LLMProviderError):
        return "provider"
    if isinstance(normalized, LLMStructuredOutputError):
        return "structured_output"
    if isinstance(normalized, LLMSchemaValidationError):
        return "schema_validation"
    if isinstance(normalized, LLMRetryExhaustedError):
        return "retry_exhausted"
    return normalized.__class__.__name__.lower()
