import logging
from src.core.logging import get_run_logger, RunLoggerAdapter

def test_get_run_logger_creates_adapter() -> None:
    """Verify get_run_logger returns the correct adapter with a run_id."""
    logger = get_run_logger("test_module")
    
    assert isinstance(logger, RunLoggerAdapter)
    assert "run_id" in logger.extra
    assert len(logger.extra["run_id"]) == 12

def test_run_logger_adapter_injects_run_id() -> None:
    """Verify the adapter correctly merges run_id into the log record's extra context."""
    base_logger = logging.getLogger("base")
    run_id = "test_id_123"
    adapter = RunLoggerAdapter(base_logger, {"run_id": run_id})
    
    # Simulate the logging process
    msg, kwargs = adapter.process("test message", {})
    
    assert msg == "test message"
    assert kwargs["extra"]["run_id"] == run_id

def test_run_logger_adapter_preserves_existing_extra() -> None:
    """Verify the adapter adds run_id without overwriting existing extra data."""
    base_logger = logging.getLogger("base")
    adapter = RunLoggerAdapter(base_logger, {"run_id": "123"})
    
    msg, kwargs = adapter.process("test", {"extra": {"user": "admin"}})
    
    assert kwargs["extra"]["user"] == "admin"
    assert kwargs["extra"]["run_id"] == "123"
