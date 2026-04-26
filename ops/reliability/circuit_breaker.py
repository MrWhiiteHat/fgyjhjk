"""Circuit breaker implementation for isolating unstable dependencies."""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, Generic, Optional, TypeVar


T = TypeVar("T")


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitSnapshot:
    """Current circuit status for monitoring and diagnostics."""

    state: CircuitState
    consecutive_failures: int
    consecutive_successes: int
    opened_at: float | None
    last_error: str | None


class CircuitBreaker(Generic[T]):
    """Stateful circuit breaker with half-open recovery probes."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 30.0,
        half_open_success_threshold: int = 2,
    ) -> None:
        self.failure_threshold = int(failure_threshold)
        self.recovery_timeout_seconds = float(recovery_timeout_seconds)
        self.half_open_success_threshold = int(half_open_success_threshold)

        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._opened_at: float | None = None
        self._last_error: str | None = None

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN and self._opened_at is not None:
            if (time.time() - self._opened_at) >= self.recovery_timeout_seconds:
                self._state = CircuitState.HALF_OPEN
                self._consecutive_successes = 0
        return self._state

    def _trip_open(self, error_message: str) -> None:
        self._state = CircuitState.OPEN
        self._opened_at = time.time()
        self._last_error = error_message

    def record_success(self) -> None:
        if self.state == CircuitState.HALF_OPEN:
            self._consecutive_successes += 1
            if self._consecutive_successes >= self.half_open_success_threshold:
                self._state = CircuitState.CLOSED
                self._consecutive_failures = 0
                self._consecutive_successes = 0
                self._opened_at = None
                self._last_error = None
        else:
            self._consecutive_failures = 0

    def record_failure(self, exc: Exception) -> None:
        message = f"{type(exc).__name__}: {exc}"
        self._last_error = message

        if self.state == CircuitState.HALF_OPEN:
            self._trip_open(message)
            return

        self._consecutive_failures += 1
        if self._consecutive_failures >= self.failure_threshold:
            self._trip_open(message)

    def allow_request(self) -> bool:
        return self.state != CircuitState.OPEN

    def call(self, fn: Callable[..., T], *args, **kwargs) -> T:
        if not self.allow_request():
            raise RuntimeError("Circuit breaker is OPEN; request blocked")
        try:
            result = fn(*args, **kwargs)
            self.record_success()
            return result
        except Exception as exc:  # noqa: BLE001
            self.record_failure(exc)
            raise

    def snapshot(self) -> CircuitSnapshot:
        return CircuitSnapshot(
            state=self.state,
            consecutive_failures=self._consecutive_failures,
            consecutive_successes=self._consecutive_successes,
            opened_at=self._opened_at,
            last_error=self._last_error,
        )

    def as_dict(self) -> Dict[str, object]:
        status = self.snapshot()
        return {
            "state": status.state.value,
            "consecutive_failures": status.consecutive_failures,
            "consecutive_successes": status.consecutive_successes,
            "opened_at": status.opened_at,
            "last_error": status.last_error,
        }
