from typer.testing import CliRunner

from src.cli import app

runner = CliRunner()


def test_cli_has_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "ingest" in result.output
    assert "index" in result.output
    assert "rank" in result.output
