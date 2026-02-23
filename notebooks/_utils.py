from pathlib import Path


def project_root() -> Path:
    """Return notebook execution root (expected repository root)."""
    return Path.cwd().parent


def data_dir() -> Path:
    """Return the standard data directory and validate it exists."""
    d = project_root() / "data"
    if not d.exists():
        raise FileNotFoundError(f"Missing data directory: {d}")
    return d


def list_pdfs(directory: Path | None = None) -> list[Path]:
    """List PDF files deterministically."""
    base = directory or data_dir()
    return sorted(base.glob("*.pdf"))


def print_checkpoint(label: str) -> None:
    print(f"[checkpoint] {label}")
