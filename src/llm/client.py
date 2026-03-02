"""LLM infrastructure for model routing, provider access, and error handling."""

import json
from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from src.llm.errors import (
    LLMRetryExhaustedError,
    LLMSchemaValidationError,
    LLMStructuredOutputError,
)
from src.llm.registry import ModelAliasRegistry

SchemaModelT = TypeVar("SchemaModelT", bound=BaseModel)


class LLMClient(ABC):
    """Minimal client contract used by ingestion and fallback logic."""

    @abstractmethod
    def generate_structured(
        self,
        prompt: str,
        schema: type[SchemaModelT],
        model_alias: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> SchemaModelT:
        """Generate and validate structured output against a schema."""

    @abstractmethod
    def embed(
        self,
        texts: list[str],
        embedding_model_alias: str,
    ) -> list[list[float]]:
        """Generate embeddings for one or many text inputs."""


class LiteLLMClient(LLMClient):
    """LiteLLM-backed implementation of the minimal LLM client contract."""

    def __init__(self, registry: ModelAliasRegistry, *, timeout_seconds: float, max_retries: int) -> None:
        self._registry = registry
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries

    def generate_structured(
        self,
        prompt: str,
        schema: type[SchemaModelT],
        model_alias: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> SchemaModelT:
        """Generate validated JSON output for the given prompt and schema."""
        from litellm import completion

        alias = self._registry.get(model_alias)
        attempts = self._max_retries + 1
        errors: list[str] = []

        for _ in range(attempts):
            call_params: dict[str, Any] = dict(alias.params)
            if temperature is not None:
                call_params["temperature"] = temperature
            if max_tokens is not None:
                call_params["max_tokens"] = max_tokens

            try:
                response = completion(
                    model=alias.model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Return valid JSON only. Match the requested schema exactly. "
                                "Do not include markdown fences."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    timeout=self._timeout_seconds,
                    **call_params,
                )
                raw_text = _extract_text(response)
                payload = json.loads(raw_text)
                return schema.model_validate(payload)
            except Exception as exc:
                if isinstance(exc, json.JSONDecodeError):
                    errors.append(str(LLMStructuredOutputError(str(exc))))
                    continue
                if isinstance(exc, ValidationError):
                    errors.append(str(LLMSchemaValidationError(str(exc))))
                    continue
                if isinstance(exc, (LLMStructuredOutputError, LLMSchemaValidationError)):
                    errors.append(str(exc))
                    continue
                raise

        raise LLMRetryExhaustedError(
            f"Structured generation failed after {attempts} attempts for alias '{model_alias}': "
            + " | ".join(errors)
        )

    def embed(self, texts: list[str], embedding_model_alias: str) -> list[list[float]]:
        """Generate embeddings using the configured alias."""
        from litellm import embedding

        if not texts:
            return []

        alias = self._registry.get(embedding_model_alias)
        response = embedding(
            model=alias.model,
            input=texts,
            timeout=self._timeout_seconds,
            **alias.params,
        )
        data = _coerce_mapping(response).get("data", [])
        vectors: list[list[float]] = []
        for row in data:
            embedding_values = row.get("embedding")
            if not isinstance(embedding_values, list):
                raise LLMStructuredOutputError("Embedding response row is missing 'embedding' list")
            vectors.append([float(value) for value in embedding_values])
        return vectors


def _extract_text(response: Any) -> str:
    """Extract message text from provider completion payloads."""
    payload = _coerce_mapping(response)
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LLMStructuredOutputError("Completion response does not contain choices")
    first_choice = choices[0]
    message = first_choice.get("message", {})
    content = message.get("content")

    if isinstance(content, str):
        return content

    # Some providers return segmented content blocks.
    if isinstance(content, list):
        fragments: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                fragments.append(item["text"])
        if fragments:
            return "".join(fragments)

    raise LLMStructuredOutputError("Completion response message content is missing or unsupported")


def _coerce_mapping(response: Any) -> Mapping[str, Any]:
    """Normalize a LiteLLM response object into a dictionary-like payload."""
    if isinstance(response, Mapping):
        return response
    if hasattr(response, "model_dump"):
        return response.model_dump()
    raise LLMStructuredOutputError("Unsupported LiteLLM response object")
