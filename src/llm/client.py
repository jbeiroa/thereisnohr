"""Application module `src.llm.client`."""

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
from src.llm.types import LLMCallMetadata

SchemaModelT = TypeVar("SchemaModelT", bound=BaseModel)


class LLMClient(ABC):
    """Represents LLMClient."""

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

    @abstractmethod
    async def agenerate_structured(
        self,
        prompt: str,
        schema: type[SchemaModelT],
        model_alias: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> SchemaModelT:
        """Generate and validate structured output against a schema asynchronously."""

    @abstractmethod
    async def aembed(
        self,
        texts: list[str],
        embedding_model_alias: str,
    ) -> list[list[float]]:
        """Generate embeddings for one or many text inputs asynchronously."""

    @abstractmethod
    def generate_structured_with_meta(
        self,
        prompt: str,
        schema: type[SchemaModelT],
        model_alias: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> tuple[SchemaModelT, LLMCallMetadata]:
        """Generate structured output and return call metadata."""

    @abstractmethod
    def embed_with_meta(
        self,
        texts: list[str],
        embedding_model_alias: str,
    ) -> tuple[list[list[float]], LLMCallMetadata]:
        """Generate embeddings and return call metadata."""


class LiteLLMClient(LLMClient):
    """Represents LiteLLMClient."""

    def __init__(self, registry: ModelAliasRegistry, *, timeout_seconds: float, max_retries: int) -> None:
        """Initialize the instance.

        Args:
            registry: Input parameter.
            timeout_seconds: Input parameter.
            max_retries: Input parameter.

        """
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
        """Run generate structured.

        Args:
            prompt: Input parameter.
            schema: Input parameter.
            model_alias: Input parameter.
            temperature: Input parameter.
            max_tokens: Input parameter.

        Returns:
            object: Computed result.

        """
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
        """Run embed.

        Args:
            texts: Input parameter.
            embedding_model_alias: Input parameter.

        Returns:
            object: Computed result.

        """
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

    async def agenerate_structured(
        self,
        prompt: str,
        schema: type[SchemaModelT],
        model_alias: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> SchemaModelT:
        """Boilerplate async structured generation stub for future implementation."""
        _ = prompt
        _ = schema
        _ = model_alias
        _ = temperature
        _ = max_tokens
        raise NotImplementedError("Async structured generation is not implemented yet.")

    async def aembed(
        self,
        texts: list[str],
        embedding_model_alias: str,
    ) -> list[list[float]]:
        """Boilerplate async embedding stub for future implementation."""
        _ = texts
        _ = embedding_model_alias
        raise NotImplementedError("Async embedding generation is not implemented yet.")

    def generate_structured_with_meta(
        self,
        prompt: str,
        schema: type[SchemaModelT],
        model_alias: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> tuple[SchemaModelT, LLMCallMetadata]:
        """Boilerplate metadata wrapper stub for future implementation."""
        _ = prompt
        _ = schema
        _ = model_alias
        _ = temperature
        _ = max_tokens
        raise NotImplementedError("Structured generation with metadata is not implemented yet.")

    def embed_with_meta(
        self,
        texts: list[str],
        embedding_model_alias: str,
    ) -> tuple[list[list[float]], LLMCallMetadata]:
        """Boilerplate metadata wrapper stub for future implementation."""
        _ = texts
        _ = embedding_model_alias
        raise NotImplementedError("Embedding generation with metadata is not implemented yet.")


def _extract_text(response: Any) -> str:
    """Helper for  extract text.

    Args:
        response: Input parameter.

    Returns:
        object: Computed result.

    """
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
    """Helper for  coerce mapping.

    Args:
        response: Input parameter.

    Returns:
        object: Computed result.

    """
    if isinstance(response, Mapping):
        return response
    if hasattr(response, "model_dump"):
        return response.model_dump()
    raise LLMStructuredOutputError("Unsupported LiteLLM response object")
