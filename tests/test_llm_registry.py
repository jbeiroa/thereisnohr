from pathlib import Path

import pytest

from src.llm.registry import ModelAliasRegistry


def test_registry_loads_aliases(tmp_path: Path) -> None:
    config = tmp_path / "model_aliases.yaml"
    config.write_text(
        "summarizer_default:\n"
        "  model: openai/gpt-4o-mini\n"
        "  params:\n"
        "    temperature: 0.1\n",
        encoding="utf-8",
    )

    registry = ModelAliasRegistry(config)
    alias = registry.get("summarizer_default")
    assert alias.model == "openai/gpt-4o-mini"
    assert alias.params["temperature"] == 0.1


def test_registry_raises_for_unknown_alias(tmp_path: Path) -> None:
    config = tmp_path / "model_aliases.yaml"
    config.write_text("embedding_default:\n  model: text-embedding-3-small\n", encoding="utf-8")
    registry = ModelAliasRegistry(config)

    with pytest.raises(KeyError):
        registry.get("missing_alias")
