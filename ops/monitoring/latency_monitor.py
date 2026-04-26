"""Latency monitor with rolling endpoint/stage percentiles and spike alerts."""

from __future__ import annotations

import json
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Deque, Dict, List


class LatencyMonitor:
    """Collects and analyzes latency dimensions across request lifecycle."""

    def __init__(
        self,
        p95_threshold_ms: float = 300.0,
        p99_threshold_ms: float = 600.0,
        window_size: int = 1000,
        report_dir: str = "app/backend/outputs/ops/monitoring/latency",
    ) -> None:
        self.p95_threshold_ms = float(p95_threshold_ms)
        self.p99_threshold_ms = float(p99_threshold_ms)
        self.window_size = int(window_size)
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)

        self._series: Dict[str, Dict[str, Deque[float]]] = defaultdict(
            lambda: {
                "upload": deque(maxlen=self.window_size),
                "preprocessing": deque(maxlen=self.window_size),
                "inference": deque(maxlen=self.window_size),
                "total": deque(maxlen=self.window_size),
            }
        )
        self._input_type_series: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=self.window_size))
        self.alert_events: List[Dict[str, object]] = []

    @staticmethod
    def _percentile(values: List[float], percentile_value: float) -> float:
        if not values:
            return 0.0
        sorted_values = sorted(values)
        if len(sorted_values) == 1:
            return float(sorted_values[0])
        rank = (float(percentile_value) / 100.0) * (len(sorted_values) - 1)
        lower = int(rank)
        upper = min(lower + 1, len(sorted_values) - 1)
        fraction = rank - lower
        return float(sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * fraction)

    def record(
        self,
        endpoint: str,
        input_type: str,
        upload_latency_ms: float,
        preprocessing_latency_ms: float,
        inference_latency_ms: float,
        total_latency_ms: float,
    ) -> None:
        endpoint_key = str(endpoint)
        self._series[endpoint_key]["upload"].append(float(upload_latency_ms))
        self._series[endpoint_key]["preprocessing"].append(float(preprocessing_latency_ms))
        self._series[endpoint_key]["inference"].append(float(inference_latency_ms))
        self._series[endpoint_key]["total"].append(float(total_latency_ms))

        self._input_type_series[str(input_type)].append(float(total_latency_ms))

    def endpoint_stats(self, endpoint: str) -> Dict[str, object]:
        endpoint_key = str(endpoint)
        stages = self._series.get(endpoint_key, {})
        payload: Dict[str, object] = {"endpoint": endpoint_key, "stages": {}}

        for stage, values in stages.items():
            sample = list(values)
            if not sample:
                payload["stages"][stage] = {
                    "count": 0,
                    "avg_ms": 0.0,
                    "median_ms": 0.0,
                    "p90_ms": 0.0,
                    "p95_ms": 0.0,
                    "p99_ms": 0.0,
                }
                continue

            payload["stages"][stage] = {
                "count": len(sample),
                "avg_ms": round(sum(sample) / len(sample), 3),
                "median_ms": round(self._percentile(sample, 50), 3),
                "p90_ms": round(self._percentile(sample, 90), 3),
                "p95_ms": round(self._percentile(sample, 95), 3),
                "p99_ms": round(self._percentile(sample, 99), 3),
            }

        return payload

    def input_type_stats(self) -> Dict[str, object]:
        payload: Dict[str, object] = {}
        for input_type, values in self._input_type_series.items():
            sample = list(values)
            payload[input_type] = {
                "count": len(sample),
                "avg_ms": round(sum(sample) / len(sample), 3) if sample else 0.0,
                "p95_ms": round(self._percentile(sample, 95), 3) if sample else 0.0,
                "p99_ms": round(self._percentile(sample, 99), 3) if sample else 0.0,
            }
        return payload

    def detect_spikes(self) -> List[Dict[str, object]]:
        """Detect threshold breaches and record alert events."""
        alerts: List[Dict[str, object]] = []
        for endpoint in self._series.keys():
            stats = self.endpoint_stats(endpoint)
            total_stage = stats["stages"].get("total", {})
            p95 = float(total_stage.get("p95_ms", 0.0))
            p99 = float(total_stage.get("p99_ms", 0.0))

            if p95 > self.p95_threshold_ms or p99 > self.p99_threshold_ms:
                alert = {
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "endpoint": endpoint,
                    "p95_ms": p95,
                    "p99_ms": p99,
                    "threshold_p95_ms": self.p95_threshold_ms,
                    "threshold_p99_ms": self.p99_threshold_ms,
                    "severity": "critical" if p99 > self.p99_threshold_ms else "warning",
                }
                alerts.append(alert)

        if alerts:
            self.alert_events.extend(alerts)
        return alerts

    def generate_report(self, save: bool = True) -> Dict[str, object]:
        report = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "endpoint_breakdown": [self.endpoint_stats(endpoint) for endpoint in sorted(self._series.keys())],
            "input_type_breakdown": self.input_type_stats(),
            "alerts": self.detect_spikes(),
        }

        if save:
            stamp = report["timestamp"].replace(":", "").replace("-", "")
            report_path = self.report_dir / f"latency_report_{stamp}.json"
            with report_path.open("w", encoding="utf-8") as handle:
                json.dump(report, handle, indent=2, sort_keys=True)
            report["report_path"] = str(report_path.as_posix())

        return report
