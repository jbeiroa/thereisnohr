"""Application module."""

from pathlib import Path

import typer

from src.core.config import get_settings
from src.core.logging import configure_logging, get_run_logger
from src.ingest.service import IngestionService
from src.ranking.workflow import RankingWorkflow
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
    """Runs index logic."""
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

    typer.secho(
        f"\nTop {len(ranked[:top_k])} Candidates for Job {job_id}:", fg=typer.colors.CYAN, bold=True
    )
    for r in ranked[:top_k]:
        color = typer.colors.GREEN if r.rank == 1 else typer.colors.WHITE
        typer.secho(
            f"{r.rank}. Candidate ID: {r.candidate_id} | Score: {r.scores.final_score:.2f}",
            fg=color,
        )
        if r.explanation:
            typer.echo(f"   Summary: {r.explanation.evidence_based_summary}")
            if r.explanation.gaps_and_risks:
                typer.echo("   Gaps/Risks:")
                for gap in r.explanation.gaps_and_risks:
                    typer.echo(f"    - {gap.missing_requirement}: {gap.impact}")
        typer.echo("-" * 40)


@app.command()
def prep(job_id: int, candidate_id: int) -> None:
    """Displays or generates an interview preparation pack for a candidate."""
    from src.storage import models
    from src.storage.repositories import MatchRepository, ResumeRepository
    from src.ranking.service import RankingService
    from src.extract.types import CandidateSignals, JobRequirements
    from src.ranking.types import InterviewPrepPack, RankExplanation, RankInput

    settings = get_settings()
    configure_logging(settings.log_level)

    with get_session() as session:
        match_repo = MatchRepository(session)
        match = match_repo.get_by_job_and_candidate(job_id, candidate_id)
        if not match:
            typer.secho(
                f"No match found for Job {job_id} and Candidate {candidate_id}.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(1)

        if match.interview_pack_json:
            pack = InterviewPrepPack.model_validate(match.interview_pack_json)
        else:
            typer.echo("Generating interview preparation pack...")
            job = session.get(models.JobPosting, job_id)
            requirements = JobRequirements.model_validate(job.requirements_json)

            resume_repo = ResumeRepository(session)
            latest_resume = resume_repo.get_latest_resume_by_candidate_id(candidate_id)
            if not latest_resume or not latest_resume.signals_json:
                typer.secho("Missing candidate signals.", fg=typer.colors.RED)
                raise typer.Exit(1)
            signals = CandidateSignals.model_validate(latest_resume.signals_json)

            rank_input = RankInput(
                candidate_id=candidate_id,
                retrieval_score=match.retrieval_score or 0.0,
                requirements=requirements,
                signals=signals,
            )

            explanation = None
            if (
                match.reasons_json
                and "explanation" in match.reasons_json
                and match.reasons_json["explanation"]
            ):
                explanation = RankExplanation.model_validate(match.reasons_json["explanation"])

            if not explanation:
                typer.secho(
                    "No ranking explanation found to base the prep pack on.", fg=typer.colors.RED
                )
                raise typer.Exit(1)

            ranking_service = RankingService()
            pack = ranking_service.generate_interview_pack(rank_input, explanation)
            if pack:
                match.interview_pack_json = pack.model_dump()
                session.commit()
                typer.secho("Interview pack generated and saved.", fg=typer.colors.GREEN)
            else:
                typer.secho("Failed to generate interview pack.", fg=typer.colors.RED)
                raise typer.Exit(1)

    typer.secho(
        f"\nInterview Preparation Pack (Job {job_id}, Candidate {candidate_id})",
        fg=typer.colors.CYAN,
        bold=True,
    )

    typer.secho("\nTechnical Questions:", fg=typer.colors.YELLOW, bold=True)
    for q in pack.technical_questions:
        typer.echo(f" - {q}")

    typer.secho("\nBehavioral Questions:", fg=typer.colors.YELLOW, bold=True)
    for q in pack.behavioral_questions:
        typer.echo(f" - {q}")

    typer.secho("\nClarification Questions (Gaps/Risks):", fg=typer.colors.YELLOW, bold=True)
    for q in pack.clarification_questions:
        typer.echo(f" - {q}")


@app.command("ingest-flow-help")
def ingest_flow_help() -> None:
    """Show how to run the Metaflow PDF ingestion pipeline."""
    typer.echo(
        "Run ingestion flow with: uv run python src/ingest/pdf_ingestion_flow.py run --input-dir data --pattern '*.pdf'"
    )


if __name__ == "__main__":
    app()
