"""Core runtime utilities shared across CLI, API, and pipeline modules."""

import logging
import uuid


def configure_logging(level: str = "INFO") -> None:
    """Runs configure logging logic.

    Args:
        level (str): Input value used by `level`.
    """
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s run_id=%(run_id)s %(name)s %(message)s",
    )


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
