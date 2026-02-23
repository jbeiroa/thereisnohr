"""Application module `src.llm.types`."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ModelAlias:
    """Represents ModelAlias."""

    model: str
    params: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "ModelAlias":
        """Run from mapping.

        Args:
            data: Input parameter.

        Returns:
            object: Computed result.

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
    """Represents a concrete provider/model route for an alias."""

    model: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FallbackPolicy:
    """Represents retry and failover settings for LLM route selection."""

    per_route_retries: int = 0
    failover_on: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LLMUsage:
    """Represents normalized usage metrics for a single LLM call."""

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None


@dataclass(frozen=True)
class LLMAttempt:
    """Represents one attempt in a call retry/fallback sequence."""

    attempt_index: int
    model: str
    succeeded: bool
    error_type: str | None = None
    latency_ms: float | None = None


@dataclass(frozen=True)
class LLMCallMetadata:
    """Represents aggregated metadata for a completed LLM call."""

    model_alias: str
    selected_model: str | None = None
    attempts: list[LLMAttempt] = field(default_factory=list)
    fallback_used: bool = False
    latency_ms: float | None = None
    usage: LLMUsage = field(default_factory=LLMUsage)
