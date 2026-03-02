"""Factory helpers for constructing default LLM client instances."""

from src.core.config import get_settings
from src.llm.client import LiteLLMClient
from src.llm.registry import ModelAliasRegistry


def build_default_llm_client() -> LiteLLMClient:
    """Builds the default LiteLLM client using runtime settings.

    Returns:
        LiteLLMClient: Client configured with registry path, timeout, and
            retry defaults from app settings.
    """
    settings = get_settings()
    registry = ModelAliasRegistry(settings.model_aliases_path)
    return LiteLLMClient(
        registry=registry,
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )
