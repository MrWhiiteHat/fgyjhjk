"""Minimal telemetry counters and Prometheus-compatible text exporter."""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class EndpointMetric:
    """Per-endpoint aggregate metrics."""

    count: int = 0
    error_count: int = 0
    total_latency_ms: float = 0.0


class TelemetryStore:
    """In-memory telemetry store for request and error metrics."""

    def __init__(self) -> None:
        self.started_at = time.time()
        self.request_count = 0
        self.error_count = 0
        self.total_latency_ms = 0.0
        self.endpoint_stats: Dict[str, EndpointMetric] = defaultdict(EndpointMetric)
        self._lock = threading.Lock()

    def record(self, endpoint: str, status_code: int, duration_ms: float) -> None:
        """Record one request telemetry event."""
        key = str(endpoint)
        with self._lock:
            self.request_count += 1
            self.total_latency_ms += float(duration_ms)
            metric = self.endpoint_stats[key]
            metric.count += 1
            metric.total_latency_ms += float(duration_ms)
            if int(status_code) >= 400:
                self.error_count += 1
                metric.error_count += 1

    def snapshot(self) -> Dict[str, object]:
        """Return telemetry snapshot as serializable dictionary."""
        with self._lock:
            avg_latency = self.total_latency_ms / self.request_count if self.request_count else 0.0
            uptime = time.time() - self.started_at

            endpoints = {}
            for endpoint, metric in self.endpoint_stats.items():
                endpoint_avg = metric.total_latency_ms / metric.count if metric.count else 0.0
                endpoints[endpoint] = {
                    "count": metric.count,
                    "error_count": metric.error_count,
                    "avg_latency_ms": endpoint_avg,
                }

            return {
                "request_count": self.request_count,
                "error_count": self.error_count,
                "avg_latency_ms": avg_latency,
                "uptime_seconds": uptime,
                "endpoints": endpoints,
            }

    def prometheus_text(self) -> str:
        """Export telemetry in basic Prometheus text exposition format."""
        snap = self.snapshot()
        lines = [
            "# HELP app_requests_total Total number of API requests",
            "# TYPE app_requests_total counter",
            f"app_requests_total {snap['request_count']}",
            "# HELP app_errors_total Total number of API errors",
            "# TYPE app_errors_total counter",
            f"app_errors_total {snap['error_count']}",
            "# HELP app_latency_ms Average request latency in ms",
            "# TYPE app_latency_ms gauge",
            f"app_latency_ms {snap['avg_latency_ms']:.6f}",
        ]

        for endpoint, data in snap["endpoints"].items():
            safe_endpoint = endpoint.replace('"', "'")
            lines.append(f'app_endpoint_requests_total{{endpoint="{safe_endpoint}"}} {data["count"]}')
            lines.append(f'app_endpoint_errors_total{{endpoint="{safe_endpoint}"}} {data["error_count"]}')
            lines.append(f'app_endpoint_latency_ms{{endpoint="{safe_endpoint}"}} {data["avg_latency_ms"]:.6f}')

        return "\n".join(lines) + "\n"


_TELEMETRY = TelemetryStore()


def get_telemetry() -> TelemetryStore:
    """Return singleton telemetry store."""
    return _TELEMETRY
