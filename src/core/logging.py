import logging
import uuid


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s run_id=%(run_id)s %(name)s %(message)s",
    )


class RunLoggerAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        extra = kwargs.setdefault("extra", {})
        extra.setdefault("run_id", self.extra.get("run_id"))
        return msg, kwargs


def get_run_logger(name: str) -> RunLoggerAdapter:
    run_id = uuid.uuid4().hex[:12]
    return RunLoggerAdapter(logging.getLogger(name), {"run_id": run_id})
