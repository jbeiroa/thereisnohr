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
