"""LLM clients backed by LiteLLM Router for routing and failover."""

import json
import time
from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from src.llm.errors import (
    LLMSchemaValidationError,
    LLMStructuredOutputError,
    coerce_provider_exception,
    error_type_for_exception,
)
from src.llm.registry import ModelAliasRegistry
from src.llm.types import LLMCallMetadata, LLMAttempt, LLMUsage

SchemaModelT = TypeVar("SchemaModelT", bound=BaseModel)


class LLMClient(ABC):
    """Client contract for structured generation and embedding calls."""

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
        """Generates schema-validated structured output.

        Args:
            prompt: Prompt text sent to the language model.
            schema: Pydantic schema used to validate parsed JSON output.
            model_alias: Alias key used to resolve model routing config.
            temperature: Optional sampling temperature override.
            max_tokens: Optional token limit override.

        Returns:
            SchemaModelT: Validated structured model instance.
        """

    @abstractmethod
    def embed(
        self,
        texts: list[str],
        embedding_model_alias: str,
    ) -> list[list[float]]:
        """Generates vector embeddings for one or many input texts."""

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
        """Asynchronously generates schema-validated structured output."""

    @abstractmethod
    async def aembed(
        self,
        texts: list[str],
        embedding_model_alias: str,
    ) -> list[list[float]]:
        """Asynchronously generates embeddings for one or many input texts."""

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
        """Generates structured output and returns call metadata."""

    @abstractmethod
    def embed_with_meta(
        self,
        texts: list[str],
        embedding_model_alias: str,
    ) -> tuple[list[list[float]], LLMCallMetadata]:
        """Generates embeddings and returns call metadata."""


class LiteLLMClient(LLMClient):
    """LiteLLM Router-backed client implementation.

    Router is responsible for retries and fallback traversal according to alias
    policy. This client focuses on prompt/schema handling and metadata
    normalization.
    """

    def __init__(self, registry: ModelAliasRegistry, *, timeout_seconds: float, max_retries: int) -> None:
        """Initializes the client with alias registry and runtime defaults.

        Args:
            registry: Alias registry used to resolve route definitions.
            timeout_seconds: Default timeout applied to Router calls.
            max_retries: Global retry fallback when alias policy omits retries.
        """
        self._registry = registry
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._routers: dict[str, Any] = {}

    def generate_structured(
        self,
        prompt: str,
        schema: type[SchemaModelT],
        model_alias: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> SchemaModelT:
        """Generates structured output without metadata wrapper."""
        result, _ = self.generate_structured_with_meta(
            prompt=prompt,
            schema=schema,
            model_alias=model_alias,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return result

    def embed(
        self,
        texts: list[str],
        embedding_model_alias: str,
    ) -> list[list[float]]:
        """Generates embeddings without metadata wrapper."""
        vectors, _ = self.embed_with_meta(texts=texts, embedding_model_alias=embedding_model_alias)
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
        """Asynchronously generates structured output without metadata wrapper."""
        result, _ = await self.agenerate_structured_with_meta(
            prompt=prompt,
            schema=schema,
            model_alias=model_alias,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return result

    async def aembed(
        self,
        texts: list[str],
        embedding_model_alias: str,
    ) -> list[list[float]]:
        """Asynchronously generates embeddings without metadata wrapper."""
        vectors, _ = await self.aembed_with_meta(texts=texts, embedding_model_alias=embedding_model_alias)
        return vectors

    def generate_structured_with_meta(
        self,
        prompt: str,
        schema: type[SchemaModelT],
        model_alias: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> tuple[SchemaModelT, LLMCallMetadata]:
        """Generates structured output and returns normalized call metadata.

        Raises:
            LLMStructuredOutputError: If the provider output is not valid JSON.
            LLMSchemaValidationError: If JSON payload fails schema validation.
            Exception: Provider exceptions after normalization where applicable.
        """
        router = self._router_for_alias(model_alias)
        alias_config = self._registry.get(model_alias)
        start = time.perf_counter()

        call_kwargs: dict[str, Any] = {}
        if temperature is not None:
            call_kwargs["temperature"] = temperature
        if max_tokens is not None:
            call_kwargs["max_tokens"] = max_tokens

        try:
            response = router.completion(
                model=model_alias,
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
                fallbacks=alias_config.get_fallback_names(model_alias),
                **call_kwargs,
            )
        except Exception as exc:
            normalized = coerce_provider_exception(exc)
            if normalized is not exc:
                raise normalized from exc
            raise

        payload = _coerce_mapping(response)
        raw_text = _extract_text(payload)
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise LLMStructuredOutputError(str(exc)) from exc
        try:
            parsed = schema.model_validate(data)
        except ValidationError as exc:
            raise LLMSchemaValidationError(str(exc)) from exc

        metadata = _build_metadata(
            payload=payload,
            model_alias=model_alias,
            started_at=start,
            failure=None,
        )
        return parsed, metadata

    def embed_with_meta(
        self,
        texts: list[str],
        embedding_model_alias: str,
    ) -> tuple[list[list[float]], LLMCallMetadata]:
        """Generates embeddings and returns normalized call metadata."""
        if not texts:
            return [], LLMCallMetadata(model_alias=embedding_model_alias)

        router = self._router_for_alias(embedding_model_alias)
        alias_config = self._registry.get(embedding_model_alias)
        start = time.perf_counter()
        try:
            response = router.embedding(
                model=embedding_model_alias,
                input=texts,
                timeout=self._timeout_seconds,
                fallbacks=alias_config.get_fallback_names(embedding_model_alias),
            )
        except Exception as exc:
            normalized = coerce_provider_exception(exc)
            if normalized is not exc:
                raise normalized from exc
            raise

        payload = _coerce_mapping(response)
        data = payload.get("data", [])
        vectors: list[list[float]] = []
        for row in data:
            embedding_values = row.get("embedding")
            if not isinstance(embedding_values, list):
                raise LLMStructuredOutputError("Embedding response row is missing 'embedding' list")
            vectors.append([float(value) for value in embedding_values])

        metadata = _build_metadata(
            payload=payload,
            model_alias=embedding_model_alias,
            started_at=start,
            failure=None,
        )
        return vectors, metadata

    async def agenerate_structured_with_meta(
        self,
        prompt: str,
        schema: type[SchemaModelT],
        model_alias: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> tuple[SchemaModelT, LLMCallMetadata]:
        """Async variant of structured generation with metadata."""
        router = self._router_for_alias(model_alias)
        alias_config = self._registry.get(model_alias)
        start = time.perf_counter()

        call_kwargs: dict[str, Any] = {}
        if temperature is not None:
            call_kwargs["temperature"] = temperature
        if max_tokens is not None:
            call_kwargs["max_tokens"] = max_tokens

        try:
            response = await router.acompletion(
                model=model_alias,
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
                fallbacks=alias_config.get_fallback_names(model_alias),
                **call_kwargs,
            )
        except Exception as exc:
            normalized = coerce_provider_exception(exc)
            if normalized is not exc:
                raise normalized from exc
            raise

        payload = _coerce_mapping(response)
        raw_text = _extract_text(payload)
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise LLMStructuredOutputError(str(exc)) from exc
        try:
            parsed = schema.model_validate(data)
        except ValidationError as exc:
            raise LLMSchemaValidationError(str(exc)) from exc

        metadata = _build_metadata(
            payload=payload,
            model_alias=model_alias,
            started_at=start,
            failure=None,
        )
        return parsed, metadata

    async def aembed_with_meta(
        self,
        texts: list[str],
        embedding_model_alias: str,
    ) -> tuple[list[list[float]], LLMCallMetadata]:
        """Async variant of embedding generation with metadata."""
        if not texts:
            return [], LLMCallMetadata(model_alias=embedding_model_alias)

        router = self._router_for_alias(embedding_model_alias)
        alias_config = self._registry.get(embedding_model_alias)
        start = time.perf_counter()
        try:
            response = await router.aembedding(
                model=embedding_model_alias,
                input=texts,
                timeout=self._timeout_seconds,
                fallbacks=alias_config.get_fallback_names(embedding_model_alias),
            )
        except Exception as exc:
            normalized = coerce_provider_exception(exc)
            if normalized is not exc:
                raise normalized from exc
            raise

        payload = _coerce_mapping(response)
        data = payload.get("data", [])
        vectors: list[list[float]] = []
        for row in data:
            embedding_values = row.get("embedding")
            if not isinstance(embedding_values, list):
                raise LLMStructuredOutputError("Embedding response row is missing 'embedding' list")
            vectors.append([float(value) for value in embedding_values])

        metadata = _build_metadata(
            payload=payload,
            model_alias=embedding_model_alias,
            started_at=start,
            failure=None,
        )
        return vectors, metadata

    def _router_for_alias(self, alias_name: str) -> Any:
        """Builds or reuses a Router instance configured for one alias.

        Args:
            alias_name: Alias name used to resolve route and policy config.

        Returns:
            Any: LiteLLM Router object configured for this alias.
        """
        router = self._routers.get(alias_name)
        if router is not None:
            return router

        from litellm import Router

        alias = self._registry.get(alias_name)
        router = Router(
            model_list=alias.to_router_model_list(alias_name),
            num_retries=alias.fallback_policy.num_retries or self._max_retries,
            max_fallbacks=alias.fallback_policy.max_fallbacks,
            timeout=self._timeout_seconds,
        )
        self._routers[alias_name] = router
        return router


def _extract_text(response_payload: Mapping[str, Any]) -> str:
    """Extracts plain text content from completion payload variants.

    Supports string content and segmented-content block formats.
    """
    choices = response_payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LLMStructuredOutputError("Completion response does not contain choices")
    first_choice = choices[0]
    message = first_choice.get("message", {})
    content = message.get("content")

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        fragments: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                fragments.append(item["text"])
        if fragments:
            return "".join(fragments)

    raise LLMStructuredOutputError("Completion response message content is missing or unsupported")


def _coerce_mapping(response: Any) -> Mapping[str, Any]:
    """Converts LiteLLM response objects into mapping payloads."""
    if isinstance(response, Mapping):
        return response
    if hasattr(response, "model_dump"):
        return response.model_dump()
    raise LLMStructuredOutputError("Unsupported LiteLLM response object")


def _build_metadata(
    *,
    payload: Mapping[str, Any],
    model_alias: str,
    started_at: float,
    failure: BaseException | None,
) -> LLMCallMetadata:
    """Builds best-effort call metadata from Router responses.

    Metadata extraction is conservative: when Router internals do not expose
    attempt-level details, a minimal attempt summary is returned.
    """
    selected_model = payload.get("model")
    usage = _extract_usage(payload)
    attempts = _extract_attempts(payload, model=selected_model, failure=failure)
    return LLMCallMetadata(
        model_alias=model_alias,
        selected_model=selected_model if isinstance(selected_model, str) else None,
        attempts=attempts,
        fallback_used=len(attempts) > 1,
        latency_ms=(time.perf_counter() - started_at) * 1000.0,
        usage=usage,
    )


def _extract_usage(payload: Mapping[str, Any]) -> LLMUsage:
    """Extracts normalized usage fields from completion/embedding payloads."""
    usage = payload.get("usage")
    if not isinstance(usage, Mapping):
        return LLMUsage()
    prompt_tokens = usage.get("prompt_tokens")
    completion_tokens = usage.get("completion_tokens")
    total_tokens = usage.get("total_tokens")
    return LLMUsage(
        prompt_tokens=int(prompt_tokens) if isinstance(prompt_tokens, int) else None,
        completion_tokens=int(completion_tokens) if isinstance(completion_tokens, int) else None,
        total_tokens=int(total_tokens) if isinstance(total_tokens, int) else None,
        estimated_cost_usd=None,
    )


def _extract_attempts(
    payload: Mapping[str, Any],
    *,
    model: Any,
    failure: BaseException | None,
) -> list[LLMAttempt]:
    """Extracts a best-effort attempt summary for metadata payloads."""
    if failure is not None:
        return [
            LLMAttempt(
                attempt_index=0,
                model=str(model) if isinstance(model, str) else "unknown",
                succeeded=False,
                error_type=error_type_for_exception(failure),
            )
        ]

    selected = model if isinstance(model, str) else "unknown"
    return [
        LLMAttempt(
            attempt_index=0,
            model=selected,
            succeeded=True,
            error_type=None,
        )
    ]
