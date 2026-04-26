"""Retry policy with exponential backoff and optional jitter."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Callable, Iterable, Tuple, Type


@dataclass
class RetryResult:
    """Execution outcome with retry metadata."""

    attempts: int
    succeeded: bool
    last_error: str | None


class RetryPolicy:
    """Configurable retry policy for transient failures."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay_seconds: float = 0.2,
        max_delay_seconds: float = 5.0,
        jitter_ratio: float = 0.1,
        retry_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    ) -> None:
        self.max_attempts = max(1, int(max_attempts))
        self.base_delay_seconds = max(0.0, float(base_delay_seconds))
        self.max_delay_seconds = max(self.base_delay_seconds, float(max_delay_seconds))
        self.jitter_ratio = max(0.0, float(jitter_ratio))
        self.retry_exceptions = retry_exceptions

    def _sleep_duration(self, attempt_index: int) -> float:
        delay = min(self.max_delay_seconds, self.base_delay_seconds * (2 ** attempt_index))
        jitter = delay * self.jitter_ratio
        if jitter > 0:
            delay = delay + random.uniform(-jitter, jitter)
        return max(0.0, delay)

    def execute(self, fn: Callable, *args, **kwargs):
        last_exc: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                return fn(*args, **kwargs)
            except self.retry_exceptions as exc:  # type: ignore[misc]
                last_exc = exc
                if attempt >= self.max_attempts:
                    break
                time.sleep(self._sleep_duration(attempt - 1))
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("Retry policy failed without exception")

    def execute_with_result(self, fn: Callable, *args, **kwargs) -> tuple[object | None, RetryResult]:
        last_exc: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                result = fn(*args, **kwargs)
                return result, RetryResult(attempts=attempt, succeeded=True, last_error=None)
            except self.retry_exceptions as exc:  # type: ignore[misc]
                last_exc = exc
                if attempt >= self.max_attempts:
                    break
                time.sleep(self._sleep_duration(attempt - 1))

        return None, RetryResult(
            attempts=self.max_attempts,
            succeeded=False,
            last_error=f"{type(last_exc).__name__}: {last_exc}" if last_exc else "unknown_error",
        )
