"""Timeout execution wrappers for bounded operation latency."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from typing import Callable, TypeVar


T = TypeVar("T")


@dataclass
class TimeoutResult:
    """Timeout execution metadata."""

    completed: bool
    timeout_seconds: float
    error: str | None = None


class TimeoutPolicy:
    """Executes callables under a wall-time timeout budget."""

    def __init__(self, timeout_seconds: float = 10.0) -> None:
        self.timeout_seconds = float(timeout_seconds)

    def execute(self, fn: Callable[..., T], *args, timeout_seconds: float | None = None, **kwargs) -> T:
        budget = float(timeout_seconds if timeout_seconds is not None else self.timeout_seconds)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(fn, *args, **kwargs)
            try:
                return future.result(timeout=budget)
            except FuturesTimeoutError as exc:
                future.cancel()
                raise TimeoutError(f"Operation exceeded timeout={budget:.3f}s") from exc

    def execute_with_result(self, fn: Callable[..., T], *args, timeout_seconds: float | None = None, **kwargs) -> tuple[T | None, TimeoutResult]:
        budget = float(timeout_seconds if timeout_seconds is not None else self.timeout_seconds)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(fn, *args, **kwargs)
            try:
                result = future.result(timeout=budget)
                return result, TimeoutResult(completed=True, timeout_seconds=budget)
            except FuturesTimeoutError:
                future.cancel()
                return None, TimeoutResult(completed=False, timeout_seconds=budget, error="operation_timeout")
