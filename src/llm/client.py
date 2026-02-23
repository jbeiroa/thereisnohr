"""Application module `src.llm.client`."""

import json
from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from src.llm.registry import ModelAliasRegistry

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
            try:
                payload = json.loads(raw_text)
                return schema.model_validate(payload)
            except (json.JSONDecodeError, ValidationError) as exc:
                errors.append(str(exc))

        raise ValueError(
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
                raise ValueError("Embedding response row is missing 'embedding' list")
            vectors.append([float(value) for value in embedding_values])
        return vectors


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
        raise ValueError("Completion response does not contain choices")
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

    raise ValueError("Completion response message content is missing or unsupported")


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
    raise ValueError("Unsupported LiteLLM response object")
