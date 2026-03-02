"""LLM infrastructure for model routing, provider access, and error handling."""

from src.core.config import get_settings
from src.llm.client import LiteLLMClient
from src.llm.registry import ModelAliasRegistry


def build_default_llm_client() -> LiteLLMClient:
    """Runs build default llm client logic.

    Returns:
        LiteLLMClient: Return value for this function.
    """
    settings = get_settings()
    registry = ModelAliasRegistry(settings.model_aliases_path)
    return LiteLLMClient(
        registry=registry,
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )
