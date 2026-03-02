"""LLM infrastructure for model routing, provider access, and error handling."""

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
    """Return all LiteLLM exception base types exposed by the SDK."""
    try:
        import litellm
    except ImportError:
        return ()

    known = getattr(litellm, "LITELLM_EXCEPTION_TYPES", ())
    return tuple(exc for exc in known if isinstance(exc, type) and issubclass(exc, Exception))


def coerce_provider_exception(error: BaseException) -> BaseException:
    """Normalize LiteLLM provider errors to a small app-level contract."""
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
