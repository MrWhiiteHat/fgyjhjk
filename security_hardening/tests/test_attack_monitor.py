from __future__ import annotations

from datetime import datetime, timedelta, timezone

from security_hardening.monitoring.attack_monitor import AttackMonitor
from security_hardening.monitoring.security_events import SecurityEventEmitter


def test_attack_monitor_summarizes_recent_events() -> None:
    monitor = AttackMonitor(surge_threshold=2, window_seconds=120)
    emitter = SecurityEventEmitter()

    now = datetime.now(tz=timezone.utc)
    event1 = emitter.emit(
        event_id="e1",
        category="perturbation_suspected",
        severity="high",
        source="api",
        message="detected",
        timestamp=now.isoformat(),
    )
    event2 = emitter.emit(
        event_id="e2",
        category="perturbation_suspected",
        severity="critical",
        source="api",
        message="detected",
        timestamp=(now - timedelta(seconds=30)).isoformat(),
    )
    event_old = emitter.emit(
        event_id="e3",
        category="malformed_input",
        severity="medium",
        source="api",
        message="old",
        timestamp=(now - timedelta(seconds=500)).isoformat(),
    )

    monitor.ingest(event1)
    monitor.ingest(event2)
    monitor.ingest(event_old)

    summary = monitor.summarize(now_iso=now.isoformat())

    assert summary.total_events == 2
    assert summary.by_category["perturbation_suspected"] == 2
    assert "perturbation_suspected" in summary.surge_categories
    assert summary.highest_severity == "critical"
