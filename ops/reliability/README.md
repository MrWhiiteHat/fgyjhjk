# Reliability Guards

This directory contains runtime reliability controls used by production operations:

- `circuit_breaker.py`: isolates unstable dependencies.
- `retry_policy.py`: bounded retries for transient failures.
- `timeout_policy.py`: hard timeout wrappers.
- `queue_guard.py`: queue depth and staleness protection.
- `resource_guard.py`: CPU/memory/disk/GPU pressure checks.
- `graceful_degradation.py`: controlled service reduction decisions.

These modules are designed to be composable with API middleware, workers, and scheduled operations.
