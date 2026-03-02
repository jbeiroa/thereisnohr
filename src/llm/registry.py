"""Model-alias registry backed by YAML configuration.

The registry is the boundary between raw YAML config and typed runtime alias
objects used by the LLM client layer.
"""

from pathlib import Path

import yaml

from src.llm.types import ModelAlias


class ModelAliasRegistry:
    """Loads, validates, and serves model aliases from configuration."""

    def __init__(self, config_path: Path) -> None:
        """Initializes the instance with its required runtime dependencies.

        Args:
            config_path (Path): Path to the YAML alias config file.
        """
        self.config_path = config_path
        self._aliases = self._load()

    def get(self, alias_name: str) -> ModelAlias:
        """Returns the configured alias definition for a given alias name.

        Args:
            alias_name (str): Alias key to resolve from the loaded registry.

        Returns:
            ModelAlias: Validated alias configuration for the requested key.

        Raises:
            KeyError: If the alias is unknown. The message includes known keys.
        """
        try:
            return self._aliases[alias_name]
        except KeyError as exc:
            known = ", ".join(sorted(self._aliases.keys()))
            raise KeyError(f"Unknown model alias '{alias_name}'. Known aliases: {known}") from exc

    def _load(self) -> dict[str, ModelAlias]:
        """Reads and validates alias mappings from the YAML config file.

        Returns:
            dict[str, ModelAlias]: Mapping from alias names to validated
                ``ModelAlias`` objects.

        Raises:
            FileNotFoundError: If the configured file does not exist.
            ValueError: If YAML content is malformed for the expected alias
                schema.
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Model alias config not found: {self.config_path}")

        with self.config_path.open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}

        if not isinstance(raw, dict):
            raise ValueError("Model alias config must be a mapping at top level")

        aliases: dict[str, ModelAlias] = {}
        for name, value in raw.items():
            if not isinstance(name, str):
                raise ValueError("Model alias names must be strings")
            if not isinstance(value, dict):
                raise ValueError(f"Model alias '{name}' must be a mapping")
            try:
                aliases[name] = ModelAlias.from_mapping(value)
            except ValueError as exc:
                raise ValueError(f"Invalid model alias '{name}': {exc}") from exc

        if not aliases:
            raise ValueError("Model alias config cannot be empty")
        return aliases
