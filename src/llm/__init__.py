"""LLM abstractions and providers."""

from src.llm.client import LLMClient, LiteLLMClient
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
from src.llm.factory import build_default_llm_client
from src.llm.registry import ModelAliasRegistry

__all__ = [
    "LLMClient",
    "LiteLLMClient",
    "ModelAliasRegistry",
    "build_default_llm_client",
    "LLMError",
    "LLMConfigError",
    "LLMProviderError",
    "LLMTimeoutError",
    "LLMRateLimitError",
    "LLMStructuredOutputError",
    "LLMSchemaValidationError",
    "LLMRetryExhaustedError",
    "coerce_provider_exception",
]
