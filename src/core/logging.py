"""Core runtime utilities shared across CLI, API, and pipeline modules."""

import logging
import uuid


class RunIDFilter(logging.Filter):
    """Adds a default run_id to records if missing."""

    def filter(self, record):
        if not hasattr(record, "run_id"):
            record.run_id = "global"
        return True


def configure_logging(level: str = "INFO") -> None:
    """Runs configure logging logic.

    Args:
        level (str): Input value used by `level`.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s run_id=%(run_id)s %(name)s %(message)s")
    )
    handler.addFilter(RunIDFilter())

    root = logging.getLogger()
    root.setLevel(level.upper())
    # Clear existing handlers
    for h in root.handlers[:]:
        root.removeHandler(h)
    root.addHandler(handler)


class RunLoggerAdapter(logging.LoggerAdapter):
    """Data model for runloggeradapter values."""

    def process(self, msg, kwargs):
        """Runs process logic.

        Args:
            msg (Any): Input value used by `msg`.
            kwargs (Any): Input value used by `kwargs`.
        """
        extra = kwargs.setdefault("extra", {})
        extra.setdefault("run_id", self.extra.get("run_id"))
        return msg, kwargs


def get_run_logger(name: str) -> RunLoggerAdapter:
    """Fetches a record or value needed by downstream workflow steps.

    Args:
        name (str): Candidate name value to persist or score.

    Returns:
        RunLoggerAdapter: Return value for this function.
    """
    run_id = uuid.uuid4().hex[:12]
    return RunLoggerAdapter(logging.getLogger(name), {"run_id": run_id})
