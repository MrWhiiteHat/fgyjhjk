"""Attack monitor that tracks category-level event surges."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone

from security_hardening.monitoring.security_events import SecurityEvent


@dataclass
class AttackMonitorSummary:
    """Aggregated monitor snapshot output."""

    total_events: int
    by_category: dict[str, int]
    surge_categories: list[str]
    highest_severity: str


class AttackMonitor:
    """Maintains event history and identifies attack surges."""

    SEVERITY_ORDER = {"low": 1, "medium": 2, "high": 3, "critical": 4}

    def __init__(self, surge_threshold: int = 20, window_seconds: int = 300) -> None:
        self.surge_threshold = int(surge_threshold)
        self.window_seconds = int(window_seconds)
        self._events: list[SecurityEvent] = []

    def ingest(self, event: SecurityEvent) -> None:
        """Add event into monitor history."""

        self._events.append(event)

    def summarize(self, now_iso: str | None = None) -> AttackMonitorSummary:
        """Summarize recent events in rolling time window."""

        now = self._parse_time(now_iso) if now_iso else datetime.now(tz=timezone.utc)
        filtered = [
            event
            for event in self._events
            if (now - self._parse_time(event.timestamp)).total_seconds() <= self.window_seconds
        ]

        counter = Counter(event.category for event in filtered)
        surge = [category for category, count in counter.items() if count >= self.surge_threshold]

        highest = "low"
        for event in filtered:
            if self.SEVERITY_ORDER.get(event.severity, 0) > self.SEVERITY_ORDER.get(highest, 0):
                highest = event.severity

        return AttackMonitorSummary(
            total_events=len(filtered),
            by_category=dict(counter),
            surge_categories=sorted(surge),
            highest_severity=highest,
        )

    @staticmethod
    def _parse_time(value: str | None) -> datetime:
        """Parse ISO timestamp into timezone-aware datetime."""

        if not value:
            return datetime.now(tz=timezone.utc)
        parsed = datetime.fromisoformat(str(value))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
