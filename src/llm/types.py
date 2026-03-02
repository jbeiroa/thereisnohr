"""LLM routing and metadata contracts.

This module defines the configuration and telemetry shapes used by the LLM
client layer. The key design is alias-first routing: each alias has one default
model route plus optional ordered fallback routes that are compiled into
LiteLLM Router `model_list` entries.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ModelRoute:
    """One concrete model target in an alias fallback chain.

    Attributes:
        model: Provider/model identifier understood by LiteLLM.
        litellm_params: Provider-specific kwargs applied when this route is
            selected.
    """

    model: str
    litellm_params: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "ModelRoute":
        """Parses one fallback route entry from alias config.

        Args:
            data: Mapping containing `model` and optional `litellm_params`.

        Raises:
            ValueError: If `model` is missing/empty or `litellm_params` is not a
                dictionary.

        Returns:
            ModelRoute: Validated route instance.
        """
        model = data.get("model")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("Fallback route requires a non-empty 'model' value")

        raw_params = data.get("litellm_params", {})
        if raw_params is None:
            raw_params = {}
        if not isinstance(raw_params, dict):
            raise ValueError("Fallback route 'litellm_params' must be a dictionary")

        return cls(model=model, litellm_params=dict(raw_params))


@dataclass(frozen=True)
class FallbackPolicy:
    """Router retry/fallback controls scoped to one alias.

    Attributes:
        num_retries: Number of retries Router should perform before attempting
            fallback. Defaults to 1.
        max_fallbacks: Maximum fallback hops Router may attempt. When omitted
            in config, defaults to the number of configured fallback routes.
    """

    num_retries: int = 1
    max_fallbacks: int | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any], *, fallback_count: int) -> "FallbackPolicy":
        """Parses fallback-policy values from alias config.

        Args:
            data: Mapping containing optional `num_retries` and
                `max_fallbacks`.
            fallback_count: Number of fallback routes configured for the alias.

        Raises:
            ValueError: If retry/fallback values are not non-negative integers.

        Returns:
            FallbackPolicy: Validated fallback policy for the alias.
        """
        num_retries = data.get("num_retries", cls.num_retries)
        if not isinstance(num_retries, int) or num_retries < 0:
            raise ValueError("'fallback_policy.num_retries' must be a non-negative integer")

        raw_max_fallbacks = data.get("max_fallbacks")
        if raw_max_fallbacks is None:
            max_fallbacks = fallback_count
        else:
            if not isinstance(raw_max_fallbacks, int) or raw_max_fallbacks < 0:
                raise ValueError("'fallback_policy.max_fallbacks' must be a non-negative integer")
            max_fallbacks = raw_max_fallbacks

        return cls(num_retries=num_retries, max_fallbacks=max_fallbacks)


@dataclass(frozen=True)
class ModelAlias:
    """Alias-level default route and ordered fallback routes.

    Attributes:
        default_model: Primary provider/model identifier attempted first.
        default_litellm_params: Provider kwargs applied to the default route.
        fallbacks: Ordered fallback route list attempted by Router.
        fallback_policy: Retry/fallback limits used when creating Router.
    """

    default_model: str
    default_litellm_params: dict[str, Any] = field(default_factory=dict)
    fallbacks: list[ModelRoute] = field(default_factory=list)
    fallback_policy: FallbackPolicy = field(default_factory=FallbackPolicy)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "ModelAlias":
        """Parses strict alias configuration from YAML mapping data.

        Expected schema:
            - `default_model` (required)
            - `default_litellm_params` (optional dict)
            - `fallbacks` (optional list of route mappings)
            - `fallback_policy` (optional mapping)

        Args:
            data: Raw alias mapping loaded from YAML.

        Raises:
            ValueError: If required fields are missing or typed incorrectly.

        Returns:
            ModelAlias: Validated alias definition.
        """
        default_model = data.get("default_model")
        if not isinstance(default_model, str) or not default_model.strip():
            raise ValueError("Model alias requires a non-empty 'default_model' value")

        raw_default_params = data.get("default_litellm_params", {})
        if raw_default_params is None:
            raw_default_params = {}
        if not isinstance(raw_default_params, dict):
            raise ValueError("'default_litellm_params' must be a dictionary")

        raw_fallbacks = data.get("fallbacks", [])
        if raw_fallbacks is None:
            raw_fallbacks = []
        if not isinstance(raw_fallbacks, list):
            raise ValueError("'fallbacks' must be a list")
        fallbacks: list[ModelRoute] = []
        for row in raw_fallbacks:
            if not isinstance(row, Mapping):
                raise ValueError("Each fallback route must be a mapping")
            fallbacks.append(ModelRoute.from_mapping(row))

        raw_policy = data.get("fallback_policy", {})
        if raw_policy is None:
            raw_policy = {}
        if not isinstance(raw_policy, Mapping):
            raise ValueError("'fallback_policy' must be a mapping")
        policy = FallbackPolicy.from_mapping(raw_policy, fallback_count=len(fallbacks))

        return cls(
            default_model=default_model,
            default_litellm_params=dict(raw_default_params),
            fallbacks=fallbacks,
            fallback_policy=policy,
        )

    def to_router_model_list(self, alias_name: str) -> list[dict[str, Any]]:
        """Compiles this alias into ordered LiteLLM Router `model_list` entries.

        Each route gets a unique `model_name` within the Router context to
        allow explicit fallback routing by group name.

        Args:
            alias_name: Base alias key used for the default route.

        Returns:
            list[dict[str, Any]]: Router-compatible model configuration list.
        """
        rows: list[dict[str, Any]] = [
            {
                "model_name": alias_name,
                "litellm_params": {
                    "model": self.default_model,
                    **self.default_litellm_params,
                },
            }
        ]
        for i, route in enumerate(self.fallbacks):
            rows.append(
                {
                    "model_name": f"{alias_name}_fallback_{i}",
                    "litellm_params": {
                        "model": route.model,
                        **route.litellm_params,
                    },
                }
            )
        return rows

    def get_fallback_names(self, alias_name: str) -> list[str]:
        """Returns the list of unique fallback group names for this alias.

        Args:
            alias_name: Base alias key.

        Returns:
            list[str]: Ordered list of fallback model group names.
        """
        return [f"{alias_name}_fallback_{i}" for i in range(len(self.fallbacks))]


@dataclass(frozen=True)
class LLMUsage:
    """Normalized token and cost metrics from provider responses."""

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None


@dataclass(frozen=True)
class LLMAttempt:
    """One recorded attempt in a structured or embedding LLM call."""

    attempt_index: int
    model: str
    succeeded: bool
    error_type: str | None = None
    latency_ms: float | None = None


@dataclass(frozen=True)
class LLMCallMetadata:
    """Aggregated diagnostics for a completed LLM call execution."""

    model_alias: str
    selected_model: str | None = None
    attempts: list[LLMAttempt] = field(default_factory=list)
    fallback_used: bool = False
    latency_ms: float | None = None
    usage: LLMUsage = field(default_factory=LLMUsage)
