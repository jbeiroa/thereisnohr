from pathlib import Path

import yaml

from src.llm.types import ModelAlias


class ModelAliasRegistry:
    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        self._aliases = self._load()

    def get(self, alias_name: str) -> ModelAlias:
        try:
            return self._aliases[alias_name]
        except KeyError as exc:
            known = ", ".join(sorted(self._aliases.keys()))
            raise KeyError(f"Unknown model alias '{alias_name}'. Known aliases: {known}") from exc

    def _load(self) -> dict[str, ModelAlias]:
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
            aliases[name] = ModelAlias.from_mapping(value)

        if not aliases:
            raise ValueError("Model alias config cannot be empty")
        return aliases
