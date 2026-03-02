"""Typed data models used for LLM alias configuration, routing, and call metadata."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ModelAlias:
    """Represents one configured model alias entry loaded from YAML.

    Attributes:
        model: Provider/model identifier understood by LiteLLM (for example,
            ``openai/gpt-4o-mini``).
        params: Optional provider-specific kwargs forwarded on each call, such
            as ``temperature`` or ``max_tokens``.
    """

    model: str
    params: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "ModelAlias":
        """Constructor that validates and converts raw dict-like config data into a safe ModelAlias instance.

        Args:
            data (Mapping[str, Any]): dict like config data for a single model alias, expected to contain at least a 'model' key with a non-empty string value, and optionally a 'params' key with a dict of additional parameters.

        Raises:
            ValueError: If the 'model' key is missing, not a string, or empty, or if the 'params' key is present but not a dict.
            ValueError: If the input data is not a mapping.

        Returns:
            ModelAlias: A validated ModelAlias instance created from the input data.
        """
        model = data.get("model")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("Model alias requires a non-empty 'model' value")

        raw_params = data.get("params", {})
        if raw_params is None:
            raw_params = {}
        if not isinstance(raw_params, dict):
            raise ValueError("Model alias 'params' must be a dictionary")

        return cls(model=model, params=raw_params)


@dataclass(frozen=True)
class ModelRoute:
    """Represents one concrete route used in a fallback chain for an alias.

    Attributes:
        model: Provider/model identifier used for this route attempt.
        params: Provider kwargs applied when this route is selected.
    """

    model: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FallbackPolicy:
    """Controls retry and failover behavior for multi-route LLM aliases.

    Attributes:
        per_route_retries: Number of retry attempts before switching to the
            next route in the chain.
        failover_on: Error categories that are allowed to trigger route
            failover.
    """

    per_route_retries: int = 0
    failover_on: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LLMUsage:
    """Normalized token and cost metrics captured from provider responses."""

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None


@dataclass(frozen=True)
class LLMAttempt:
    """Captures one retry/failover attempt within a single LLM call."""

    attempt_index: int
    model: str
    succeeded: bool
    error_type: str | None = None
    latency_ms: float | None = None


@dataclass(frozen=True)
class LLMCallMetadata:
    """Aggregates diagnostics for a completed LLM call execution."""

    model_alias: str
    selected_model: str | None = None
    attempts: list[LLMAttempt] = field(default_factory=list)
    fallback_used: bool = False
    latency_ms: float | None = None
    usage: LLMUsage = field(default_factory=LLMUsage)
