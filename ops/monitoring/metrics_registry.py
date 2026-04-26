"""Central metrics registry for ops-layer observability."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from threading import RLock
from typing import Dict, Iterable, List, Literal, Tuple


MetricKind = Literal["counter", "gauge", "histogram"]
LabelKey = Tuple[Tuple[str, str], ...]


@dataclass(frozen=True)
class MetricSpec:
    """Definition of a metric in the central registry."""

    name: str
    kind: MetricKind
    description: str
    labels: Tuple[str, ...] = field(default_factory=tuple)


class RegisteredMetric:
    """In-memory metric state backing counters, gauges, and histograms."""

    def __init__(self, spec: MetricSpec) -> None:
        self.spec = spec
        self.values: Dict[LabelKey, float] = defaultdict(float)
        self.observations: Dict[LabelKey, List[float]] = defaultdict(list)

    @staticmethod
    def _normalize_labels(label_values: Dict[str, str], expected_labels: Tuple[str, ...]) -> LabelKey:
        normalized = {}
        for key in expected_labels:
            normalized[key] = str(label_values.get(key, ""))
        return tuple(sorted(normalized.items()))

    def inc(self, amount: float = 1.0, labels: Dict[str, str] | None = None) -> None:
        labels = labels or {}
        label_key = self._normalize_labels(labels, self.spec.labels)
        self.values[label_key] += float(amount)

    def set(self, value: float, labels: Dict[str, str] | None = None) -> None:
        labels = labels or {}
        label_key = self._normalize_labels(labels, self.spec.labels)
        self.values[label_key] = float(value)

    def observe(self, value: float, labels: Dict[str, str] | None = None) -> None:
        labels = labels or {}
        label_key = self._normalize_labels(labels, self.spec.labels)
        self.observations[label_key].append(float(value))

    def export(self) -> Dict[str, object]:
        payload: Dict[str, object] = {
            "spec": {
                "name": self.spec.name,
                "kind": self.spec.kind,
                "description": self.spec.description,
                "labels": list(self.spec.labels),
            },
            "values": [
                {
                    "labels": dict(label_key),
                    "value": value,
                }
                for label_key, value in self.values.items()
            ],
        }
        if self.spec.kind == "histogram":
            payload["observations"] = [
                {
                    "labels": dict(label_key),
                    "samples": samples,
                }
                for label_key, samples in self.observations.items()
            ]
        return payload


class MetricsRegistry:
    """Thread-safe singleton registry for operational metrics."""

    _instance: "MetricsRegistry | None" = None
    _instance_lock = RLock()

    def __init__(self) -> None:
        self._lock = RLock()
        self._metrics: Dict[str, RegisteredMetric] = {}
        self._register_defaults()

    @classmethod
    def get_instance(cls) -> "MetricsRegistry":
        """Return singleton metrics registry."""
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = MetricsRegistry()
        return cls._instance

    def register_metric(self, spec: MetricSpec) -> None:
        """Register a new metric definition unless already present."""
        with self._lock:
            if spec.name in self._metrics:
                existing = self._metrics[spec.name].spec
                if existing != spec:
                    raise ValueError(f"Metric '{spec.name}' already registered with different spec")
                return
            self._metrics[spec.name] = RegisteredMetric(spec)

    def has_metric(self, name: str) -> bool:
        with self._lock:
            return name in self._metrics

    def _require_metric(self, name: str, expected_kind: MetricKind) -> RegisteredMetric:
        with self._lock:
            metric = self._metrics.get(name)
            if metric is None:
                raise KeyError(f"Metric '{name}' is not registered")
            if metric.spec.kind != expected_kind:
                raise TypeError(f"Metric '{name}' is not a {expected_kind}")
            return metric

    def inc(self, name: str, amount: float = 1.0, labels: Dict[str, str] | None = None) -> None:
        metric = self._require_metric(name, "counter")
        with self._lock:
            metric.inc(amount=amount, labels=labels)

    def set(self, name: str, value: float, labels: Dict[str, str] | None = None) -> None:
        metric = self._require_metric(name, "gauge")
        with self._lock:
            metric.set(value=value, labels=labels)

    def observe(self, name: str, value: float, labels: Dict[str, str] | None = None) -> None:
        metric = self._require_metric(name, "histogram")
        with self._lock:
            metric.observe(value=value, labels=labels)

    def histogram_values(self, name: str, labels: Dict[str, str] | None = None) -> List[float]:
        metric = self._require_metric(name, "histogram")
        labels = labels or {}
        label_key = RegisteredMetric._normalize_labels(labels, metric.spec.labels)
        with self._lock:
            return list(metric.observations.get(label_key, []))

    def export(self) -> Dict[str, object]:
        with self._lock:
            return {
                "metrics": {
                    name: metric.export()
                    for name, metric in self._metrics.items()
                }
            }

    def percentile(self, name: str, percentile_value: float, labels: Dict[str, str] | None = None) -> float:
        samples = sorted(self.histogram_values(name, labels=labels))
        if not samples:
            return 0.0
        percentile = max(0.0, min(100.0, float(percentile_value)))
        if len(samples) == 1:
            return float(samples[0])
        rank = (percentile / 100.0) * (len(samples) - 1)
        lower = int(rank)
        upper = min(lower + 1, len(samples) - 1)
        fraction = rank - lower
        return float(samples[lower] + (samples[upper] - samples[lower]) * fraction)

    def update_latency_percentiles(self, labels: Dict[str, str] | None = None) -> None:
        labels = labels or {}
        p95 = self.percentile("request_latency_ms", 95.0, labels=labels)
        p99 = self.percentile("request_latency_ms", 99.0, labels=labels)
        self.set("p95_latency", p95, labels=labels)
        self.set("p99_latency", p99, labels=labels)

    def _register_defaults(self) -> None:
        standard_specs: Iterable[MetricSpec] = (
            MetricSpec("request_count", "counter", "Total number of requests", ("endpoint", "status_code", "environment")),
            MetricSpec("request_latency_ms", "histogram", "Request latency in milliseconds", ("endpoint", "model_version", "environment")),
            MetricSpec("prediction_count_real", "counter", "Total REAL predictions", ("model_version", "environment")),
            MetricSpec("prediction_count_fake", "counter", "Total FAKE predictions", ("model_version", "environment")),
            MetricSpec("error_count", "counter", "Total number of errors", ("endpoint", "status_code", "environment")),
            MetricSpec("model_load_count", "counter", "Model load events", ("model_version", "environment")),
            MetricSpec("model_reload_count", "counter", "Model reload events", ("model_version", "environment")),
            MetricSpec("queue_depth", "gauge", "Current queue depth", ("queue_name", "environment")),
            MetricSpec("upload_bytes_total", "counter", "Total uploaded bytes", ("endpoint", "environment")),
            MetricSpec("drift_score_feature", "gauge", "Feature drift score", ("model_version", "environment")),
            MetricSpec("drift_score_prediction", "gauge", "Prediction drift score", ("model_version", "environment")),
            MetricSpec("calibration_score", "gauge", "Calibration quality score", ("model_version", "environment")),
            MetricSpec("p95_latency", "gauge", "P95 request latency (ms)", ("endpoint", "environment")),
            MetricSpec("p99_latency", "gauge", "P99 request latency (ms)", ("endpoint", "environment")),
            MetricSpec("cpu_utilization", "gauge", "CPU utilization percent", ("host", "environment")),
            MetricSpec("gpu_utilization", "gauge", "GPU utilization percent", ("host", "environment")),
            MetricSpec("app_model_class_collapse", "gauge", "Model class collapse flag", ("model_version", "environment")),
            MetricSpec("app_latency_p99_ms", "gauge", "P99 latency duplicate metric for alerting", ("endpoint", "environment")),
        )
        for spec in standard_specs:
            self.register_metric(spec)


def get_metrics_registry() -> MetricsRegistry:
    """Helper to access singleton metrics registry."""
    return MetricsRegistry.get_instance()
