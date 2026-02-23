"""Application module `src.cli`."""

from pathlib import Path

import typer

from src.core.config import get_settings
from src.core.logging import configure_logging, get_run_logger

app = typer.Typer(help="thereisnohr ATS CLI")


@app.command()
def ingest(path: Path) -> None:
    """Run ingest.

    Args:
        path: Input parameter.

    """
    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_run_logger(__name__)
    log.info("ingest command received", extra={"path": str(path)})
    typer.echo(f"Ingestion placeholder for: {path}")


@app.command()
def index() -> None:
    """Run index.

    """
    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_run_logger(__name__)
    log.info("index command received")
    typer.echo("Indexing placeholder")


@app.command()
def rank(job_id: int, top_k: int = 5) -> None:
    """Run rank.

    Args:
        job_id: Input parameter.
        top_k: Input parameter.

    """
    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_run_logger(__name__)
    log.info("rank command received", extra={"job_id": job_id, "top_k": top_k})
    typer.echo(f"Ranking placeholder for job_id={job_id}, top_k={top_k}")


@app.command("ingest-flow-help")
def ingest_flow_help() -> None:
    """Show how to run the Metaflow PDF ingestion pipeline."""
    typer.echo(
        "Run ingestion flow with: uv run python src/ingest/pdf_ingestion_flow.py run --input-dir data --pattern '*.pdf'"
    )


if __name__ == "__main__":
    app()
