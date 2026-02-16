# thereisnohr

A small, flexible ATS to ingest resumes, extract candidate signals, and rank applicants against job descriptions.

## Current scope

This branch introduces Stage 0 and Stage 1 of the reengineering plan:
- Stage 0: project scaffolding, typed config, CLI/API placeholders, and test baseline.
- Stage 1: durable ATS schema with PostgreSQL + pgvector and Alembic migrations.

## Development with uv

1. Install dependencies:

```bash
uv sync
```

2. Run tests:

```bash
uv run pytest -q
```

3. Run CLI:

```bash
uv run ats --help
```

4. Apply migrations:

```bash
uv run alembic upgrade head
```
