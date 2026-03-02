"""Public exports for the provider-agnostic LLM package."""

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
    error_type_for_exception,
)
from src.llm.factory import build_default_llm_client
from src.llm.registry import ModelAliasRegistry
from src.llm.types import FallbackPolicy, LLMCallMetadata, LLMAttempt, LLMUsage, ModelAlias, ModelRoute

__all__ = [
    "LLMClient",
    "LiteLLMClient",
    "ModelAliasRegistry",
    "build_default_llm_client",
    "ModelAlias",
    "ModelRoute",
    "FallbackPolicy",
    "LLMUsage",
    "LLMAttempt",
    "LLMCallMetadata",
    "LLMError",
    "LLMConfigError",
    "LLMProviderError",
    "LLMTimeoutError",
    "LLMRateLimitError",
    "LLMStructuredOutputError",
    "LLMSchemaValidationError",
    "LLMRetryExhaustedError",
    "coerce_provider_exception",
    "error_type_for_exception",
]
