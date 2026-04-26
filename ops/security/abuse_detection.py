"""Heuristic abuse detection for malformed and bursty request patterns."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Dict, List


@dataclass
class AbuseEvent:
    """Single abuse-analysis event sample."""

    timestamp: float
    event_type: str
    success: bool
    malformed: bool
    oversized: bool


class AbuseDetector:
    """Tracks short-window behavior and emits heuristic suspicion summaries."""

    def __init__(
        self,
        burst_window_seconds: int = 120,
        malformed_threshold: int = 10,
        oversize_threshold: int = 5,
        request_rate_threshold: int = 300,
    ) -> None:
        self.burst_window_seconds = int(burst_window_seconds)
        self.malformed_threshold = int(malformed_threshold)
        self.oversize_threshold = int(oversize_threshold)
        self.request_rate_threshold = int(request_rate_threshold)
        self._events_by_client: Dict[str, Deque[AbuseEvent]] = defaultdict(deque)

    def _evict_old(self, client_id: str, now: float) -> None:
        bucket = self._events_by_client[client_id]
        cutoff = now - self.burst_window_seconds
        while bucket and bucket[0].timestamp < cutoff:
            bucket.popleft()

    def record(
        self,
        client_id: str,
        event_type: str,
        success: bool,
        malformed: bool = False,
        oversized: bool = False,
        timestamp: float | None = None,
    ) -> None:
        now = float(timestamp if timestamp is not None else time.time())
        self._evict_old(client_id, now)
        self._events_by_client[client_id].append(
            AbuseEvent(
                timestamp=now,
                event_type=str(event_type),
                success=bool(success),
                malformed=bool(malformed),
                oversized=bool(oversized),
            )
        )

    def summarize_client(self, client_id: str) -> Dict[str, object]:
        now = time.time()
        self._evict_old(client_id, now)
        events = list(self._events_by_client[client_id])

        total = len(events)
        failed = sum(1 for event in events if not event.success)
        malformed = sum(1 for event in events if event.malformed)
        oversized = sum(1 for event in events if event.oversized)

        suspicious_reasons: List[str] = []
        if malformed >= self.malformed_threshold:
            suspicious_reasons.append("malformed_burst")
        if oversized >= self.oversize_threshold:
            suspicious_reasons.append("oversized_burst")
        if total >= self.request_rate_threshold:
            suspicious_reasons.append("request_rate_spike")
        if failed > 0 and failed / max(1, total) > 0.6 and total >= 20:
            suspicious_reasons.append("high_failure_ratio")

        suspicion_score = min(1.0, (len(suspicious_reasons) * 0.3) + ((failed / max(1, total)) * 0.4))
        suspicious = len(suspicious_reasons) > 0

        return {
            "client_id": client_id,
            "window_seconds": self.burst_window_seconds,
            "total_events": total,
            "failed_events": failed,
            "malformed_events": malformed,
            "oversized_events": oversized,
            "suspicious": suspicious,
            "suspicion_score": round(suspicion_score, 6),
            "reasons": suspicious_reasons,
            "note": "Heuristic-based signal only; manual review required before enforcement.",
        }

    def summarize_all(self) -> Dict[str, object]:
        summaries = [self.summarize_client(client_id) for client_id in sorted(self._events_by_client.keys())]
        suspicious_clients = [summary for summary in summaries if bool(summary.get("suspicious", False))]
        return {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "clients_analyzed": len(summaries),
            "suspicious_clients": suspicious_clients,
            "summaries": summaries,
        }
