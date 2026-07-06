from typer.testing import CliRunner

from knowledge_engine.cli import app


def test_cli_help() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Offline scientific paper ingestion and search" in result.output
