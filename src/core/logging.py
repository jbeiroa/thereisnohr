"""Application module `src.core.logging`."""

import logging
import uuid


def configure_logging(level: str = "INFO") -> None:
    """Run configure logging.

    Args:
        level: Input parameter.

    """
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s run_id=%(run_id)s %(name)s %(message)s",
    )


class RunLoggerAdapter(logging.LoggerAdapter):
    """Represents RunLoggerAdapter."""

    def process(self, msg, kwargs):
        """Run process.

        Args:
            msg: Input parameter.
            kwargs: Input parameter.

        Returns:
            object: Computed result.

        """
        extra = kwargs.setdefault("extra", {})
        extra.setdefault("run_id", self.extra.get("run_id"))
        return msg, kwargs


def get_run_logger(name: str) -> RunLoggerAdapter:
    """Get run logger.

    Args:
        name: Input parameter.

    Returns:
        object: Computed result.

    """
    run_id = uuid.uuid4().hex[:12]
    return RunLoggerAdapter(logging.getLogger(name), {"run_id": run_id})
