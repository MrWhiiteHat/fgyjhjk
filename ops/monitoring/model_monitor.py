"""Model behavior monitor for per-version reliability and collapse detection."""

from __future__ import annotations

import json
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Deque, Dict, List


@dataclass
class InferenceEvent:
    """Single inference event tracked by model monitor."""

    timestamp: float
    model_version: str
    predicted_label: str
    probability: float
    latency_ms: float


class ModelMonitor:
    """Tracks model version activity, prediction distribution, and reloads."""

    def __init__(
        self,
        collapse_ratio_threshold: float = 0.95,
        collapse_window_size: int = 200,
        min_samples_for_alert: int = 100,
        report_dir: str = "app/backend/outputs/ops/monitoring/model",
    ) -> None:
        self.collapse_ratio_threshold = float(collapse_ratio_threshold)
        self.collapse_window_size = int(collapse_window_size)
        self.min_samples_for_alert = int(min_samples_for_alert)
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)

        self.events_by_version: Dict[str, Deque[InferenceEvent]] = defaultdict(
            lambda: deque(maxlen=self.collapse_window_size)
        )
        self.reload_events: List[Dict[str, object]] = []
        self.rollback_recommendations: List[Dict[str, object]] = []

    def record_inference(
        self,
        model_version: str,
        predicted_label: str,
        probability: float,
        latency_ms: float,
        timestamp: float | None = None,
    ) -> None:
        event = InferenceEvent(
            timestamp=float(timestamp if timestamp is not None else time.time()),
            model_version=str(model_version),
            predicted_label=str(predicted_label).upper(),
            probability=float(probability),
            latency_ms=float(latency_ms),
        )
        self.events_by_version[event.model_version].append(event)

    def record_reload(self, model_version: str, actor: str, reason: str) -> None:
        self.reload_events.append(
            {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "model_version": str(model_version),
                "actor": str(actor),
                "reason": str(reason),
            }
        )

    def _version_stats(self, model_version: str) -> Dict[str, object]:
        events = list(self.events_by_version.get(model_version, []))
        total = len(events)
        if total == 0:
            return {
                "model_version": model_version,
                "total_inferences": 0,
                "fake_ratio": 0.0,
                "real_ratio": 0.0,
                "avg_latency_ms": 0.0,
                "median_latency_ms": 0.0,
                "p95_latency_ms": 0.0,
                "suspicious_class_collapse": False,
            }

        labels = [event.predicted_label for event in events]
        latencies = sorted(event.latency_ms for event in events)
        fake_count = sum(1 for label in labels if label == "FAKE")
        real_count = sum(1 for label in labels if label == "REAL")

        fake_ratio = fake_count / total
        real_ratio = real_count / total

        avg_latency = sum(latencies) / total
        median_latency = latencies[total // 2]
        p95_index = int(0.95 * (total - 1))
        p95 = latencies[p95_index]

        dominant_ratio = max(fake_ratio, real_ratio)
        collapse = total >= self.min_samples_for_alert and dominant_ratio >= self.collapse_ratio_threshold

        return {
            "model_version": model_version,
            "total_inferences": total,
            "fake_count": fake_count,
            "real_count": real_count,
            "fake_ratio": round(fake_ratio, 4),
            "real_ratio": round(real_ratio, 4),
            "avg_latency_ms": round(avg_latency, 3),
            "median_latency_ms": round(median_latency, 3),
            "p95_latency_ms": round(p95, 3),
            "suspicious_class_collapse": collapse,
            "dominant_ratio": round(dominant_ratio, 4),
        }

    def generate_report(self, active_model_version: str | None = None, save: bool = True) -> Dict[str, object]:
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        versions = sorted(self.events_by_version.keys())
        per_version = [self._version_stats(version) for version in versions]

        active = str(active_model_version or (versions[-1] if versions else ""))
        active_stats = self._version_stats(active) if active else {}

        rollback_signal = bool(active_stats.get("suspicious_class_collapse", False))
        if rollback_signal and active:
            recommendation = {
                "timestamp": timestamp,
                "model_version": active,
                "reason": "class_distribution_collapse",
                "dominant_ratio": active_stats.get("dominant_ratio", 0.0),
            }
            self.rollback_recommendations.append(recommendation)

        report = {
            "timestamp": timestamp,
            "active_model_version": active,
            "per_version": per_version,
            "reload_events": list(self.reload_events),
            "rollback_signal": rollback_signal,
            "rollback_recommendations": list(self.rollback_recommendations[-20:]),
        }

        if save:
            report_path = self.report_dir / f"model_monitor_{timestamp.replace(':', '').replace('-', '')}.json"
            with report_path.open("w", encoding="utf-8") as handle:
                json.dump(report, handle, indent=2, sort_keys=True)
            report["report_path"] = str(report_path.as_posix())

        return report

    def should_trigger_rollback(self, active_model_version: str) -> bool:
        stats = self._version_stats(str(active_model_version))
        return bool(stats.get("suspicious_class_collapse", False))
