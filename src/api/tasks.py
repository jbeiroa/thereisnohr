"""Background task execution utilities."""

import logging
import traceback
from collections.abc import Callable
from typing import Any

from src.storage.db import get_session
from src.storage.repositories import TaskRepository

logger = logging.getLogger(__name__)


def execute_task(task_id: int, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
    """Executes a background task and updates its status in the database.

    Args:
        task_id (int): The ID of the task to update.
        func (Callable): The function to execute.
        args: Positional arguments for the function.
        kwargs: Keyword arguments for the function.
    """
    with get_session() as session:
        repo = TaskRepository(session)
        task = repo.update_task(task_id=task_id, status="RUNNING")
        session.commit()

        if not task:
            logger.error(f"Task {task_id} not found to start execution.")
            return

        logger.info(f"Starting task {task_id} of type {task.task_type}")

        try:
            result = func(*args, **kwargs)
            repo.update_task(
                task_id=task_id,
                status="COMPLETED",
                output_payload={"result": result} if result is not None else {},
            )
            logger.info(f"Task {task_id} completed successfully")
        except Exception as e:
            error_msg = f"{e}\n{traceback.format_exc()}"
            repo.update_task(
                task_id=task_id,
                status="FAILED",
                error_message=error_msg,
            )
            logger.exception(f"Task {task_id} failed: {e}")
        finally:
            session.commit()
