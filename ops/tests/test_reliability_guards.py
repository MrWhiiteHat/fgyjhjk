import time

import pytest

from ops.reliability.circuit_breaker import CircuitBreaker, CircuitState
from ops.reliability.graceful_degradation import GracefulDegradationManager
from ops.reliability.queue_guard import QueueGuard
from ops.reliability.retry_policy import RetryPolicy
from ops.reliability.timeout_policy import TimeoutPolicy


def test_circuit_breaker_opens_after_threshold():
    breaker = CircuitBreaker(failure_threshold=2, recovery_timeout_seconds=0.1, half_open_success_threshold=1)

    def fail():
        raise ValueError("boom")

    with pytest.raises(ValueError):
        breaker.call(fail)
    with pytest.raises(ValueError):
        breaker.call(fail)

    assert breaker.state == CircuitState.OPEN
    with pytest.raises(RuntimeError):
        breaker.call(lambda: "ok")


def test_retry_policy_retries_until_success():
    attempts = {"count": 0}

    def flaky():
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("transient")
        return "ok"

    policy = RetryPolicy(max_attempts=3, base_delay_seconds=0.0, jitter_ratio=0.0)
    result = policy.execute(flaky)

    assert result == "ok"
    assert attempts["count"] == 3


def test_timeout_policy_times_out():
    timeout = TimeoutPolicy(timeout_seconds=0.05)

    def slow():
        time.sleep(0.2)
        return "done"

    with pytest.raises(TimeoutError):
        timeout.execute(slow)


def test_queue_guard_reject_new_overflow():
    guard = QueueGuard(max_queue_size=1, max_wait_seconds=10.0, overflow_policy="reject_new")

    assert guard.enqueue("first") is True
    assert guard.enqueue("second") is False
    assert guard.size() == 1


def test_graceful_degradation_safe_mode():
    manager = GracefulDegradationManager()
    decision = manager.decide(
        resource_pressure=False,
        circuit_open=True,
        queue_overflow=True,
        drift_alert=False,
    )

    assert decision.mode == "safe_mode"
    assert "dependency_circuit_open" in decision.reasons
