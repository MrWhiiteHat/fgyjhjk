"""Simple lifecycle scheduler for periodic pipeline checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class ScheduledTask:
    """Registered scheduler task descriptor."""

    task_id: str
    interval_seconds: int
    last_run_epoch: int | None = None


class Scheduler:
    """Minimal periodic scheduler for lifecycle orchestration."""

    def __init__(self) -> None:
        self._tasks: dict[str, ScheduledTask] = {}

    def register(self, task_id: str, interval_seconds: int) -> ScheduledTask:
        """Register periodic task with execution interval."""

        task = ScheduledTask(task_id=str(task_id), interval_seconds=max(1, int(interval_seconds)))
        self._tasks[task.task_id] = task
        return task

    def due_tasks(self, now_iso: str) -> list[ScheduledTask]:
        """Return tasks due for execution at current timestamp."""

        now = datetime.fromisoformat(now_iso)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        now_epoch = int(now.timestamp())

        due: list[ScheduledTask] = []
        for task in self._tasks.values():
            if task.last_run_epoch is None:
                due.append(task)
                continue
            if now_epoch - task.last_run_epoch >= task.interval_seconds:
                due.append(task)
        return due

    def mark_executed(self, task_id: str, now_iso: str) -> None:
        """Mark task run timestamp."""

        if task_id not in self._tasks:
            raise KeyError(f"Unknown task: {task_id}")
        now = datetime.fromisoformat(now_iso)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        self._tasks[task_id].last_run_epoch = int(now.timestamp())
