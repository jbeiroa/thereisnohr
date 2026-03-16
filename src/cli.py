"""Application module."""

from pathlib import Path

import typer

from src.core.config import get_settings
from src.core.logging import configure_logging, get_run_logger
from src.ingest.service import IngestionService
from src.storage.db import get_session

app = typer.Typer(help="thereisnohr ATS CLI")


@app.command()
def ingest(path: Path) -> None:
    """Runs ingest logic.

    Args:
        path (Path): Filesystem path of the file being parsed or ingested.
    """
    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_run_logger(__name__)
    log.info("ingest command received", extra={"path": str(path)})
    typer.echo(f"Ingestion placeholder for: {path}")


@app.command()
def index() -> None:
    """Runs index logic.
    """
    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_run_logger(__name__)
    log.info("index command received")
    typer.echo("Indexing placeholder")


@app.command("ingest-job")
def ingest_job_cmd(path: Path, title: str | None = typer.Option(None, help="Job title")) -> None:
    """Extracts requirements and persists a new job posting from a text file."""
    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_run_logger(__name__)

    if not path.exists():
        typer.secho(f"Error: File not found at {path}", fg=typer.colors.RED)
        raise typer.Exit(1)

    description = path.read_text(encoding="utf-8")
    job_title = title or path.stem.replace("_", " ").title()

    log.info("ingest-job command received", extra={"path": str(path), "title": job_title})

    with get_session() as session:
        service = IngestionService()
        job_id = service.ingest_job(title=job_title, description=description, session=session)
        session.commit()

    typer.secho(f"Successfully ingested job posting (ID: {job_id})", fg=typer.colors.GREEN)


from src.ranking.workflow import RankingWorkflow


@app.command()
def rank(job_id: int, top_k: int = 5) -> None:
    """Retrieves and ranks candidates for a specific job posting.

    Args:
        job_id (int): Database ID of the job posting to rank against.
        top_k (int): Number of top candidates to return.
    """
    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_run_logger(__name__)
    log.info("rank command received", extra={"job_id": job_id, "top_k": top_k})
    
    with get_session() as session:
        workflow = RankingWorkflow(session)
        ranked = workflow.run(job_id=job_id, top_k=top_k)
        session.commit()
        
    typer.secho(f"\nTop {len(ranked[:top_k])} Candidates for Job {job_id}:", fg=typer.colors.CYAN, bold=True)
    for r in ranked[:top_k]:
        color = typer.colors.GREEN if r.rank == 1 else typer.colors.WHITE
        typer.secho(f"{r.rank}. Candidate ID: {r.candidate_id} | Score: {r.scores.final_score:.2f}", fg=color)
        if r.explanation:
            typer.echo(f"   Rationale: {r.explanation.summary}")
        typer.echo("-" * 40)


@app.command("ingest-flow-help")
def ingest_flow_help() -> None:
    """Show how to run the Metaflow PDF ingestion pipeline."""
    typer.echo(
        "Run ingestion flow with: uv run python src/ingest/pdf_ingestion_flow.py run --input-dir data --pattern '*.pdf'"
    )


if __name__ == "__main__":
    app()
